# IMC Prosperity 4 - Algorithmic Trading Competition

## Project Overview

This is our workspace for **IMC Prosperity 4** (2026), a multi-round algorithmic trading competition where we write Python trading bots that execute on a simulated exchange against bot counterparties. Goal: maximize profit (PnL) in XIRECs currency.

- **Competition**: April 14-30, 2026 (5 rounds)
- **Tutorial**: March 16 - April 13, 2026
- **Wiki**: https://imc-prosperity.notion.site/prosperity-4-wiki
- **Prize Pool**: $50,000 USD

## Directory Structure

```
IMC_trading_hack/
├── CLAUDE.md                          # This file - project context
├── PROSPERITY_4_WIKI_COMPLETE.md      # Full game reference
├── datamodel.py                       # Official Prosperity 4 data model
├── trader.py                          # Main trading algorithm (SUBMIT THIS)
├── analysis/                          # Data analysis notebooks and scripts
│   └── tutorial_eda.py                # Exploratory data analysis
├── strategies/                        # Strategy modules (imported by trader.py inline)
│   ├── market_making.py               # Market making for stationary products
│   └── adaptive_mm.py                 # Adaptive market making for drifting products
├── backtesting/                       # Backtesting scripts and results
├── TUTORIAL_ROUND_1/                  # Tutorial round data (CSV files)
│   ├── prices_round_0_day_-1.csv      # Order book snapshots
│   ├── prices_round_0_day_-2.csv
│   ├── trades_round_0_day_-1.csv      # Executed trades
│   └── trades_round_0_day_-2.csv
└── round_N/                           # Data for each competition round (added as released)
```

## Architecture & Constraints

### Submission Format
- **Single Python file** (`trader.py`) containing a `Trader` class with a `run()` method
- No external file access, no network, no pip installs at runtime
- Available: standard library + numpy + jsonpickle
- Memory limit: ~100 MB (AWS Lambda)
- State persists ONLY via `traderData` string (JSON serialized)
- All orders expire each timestep (no GTC orders)

### Run Method Signature
```python
def run(self, state: TradingState) -> tuple[dict[str, list[Order]], int, str]:
    return result, conversions, traderData
```
- `result`: Dict[Symbol, List[Order]] - orders per product
- `conversions`: int - cross-market conversions (0 unless applicable)
- `traderData`: str - serialized state for next iteration

### Position Limit CRITICAL Rule
If the sum of ALL your outstanding orders for a product could push your position past the limit (assuming worst-case all fill), **ALL orders for that product are cancelled**. Always calculate worst-case before submitting.

### Order Matching Sequence (per timestep)
1. Deep-liquidity market makers post orders
2. Bot takers act
3. YOUR algorithm runs (receives TradingState, returns orders)
4. Your orders matched against order book
5. Remaining bots may trade on your quotes
6. All unfilled orders expire

## Tutorial Products (Round 0)

| Product | Position Limit | Behavior | Strategy |
|---------|---------------|----------|----------|
| EMERALDS | 80 | Stationary ~10,000 | Fixed fair-value market making |
| TOMATOES | 80 | Drifting (non-stationary) | Adaptive market making with EMA/VWAP |

### Data Format (CSV, semicolon-delimited)
- **prices**: day;timestamp;product;bid_price_1-3;bid_volume_1-3;ask_price_1-3;ask_volume_1-3;mid_price;profit_and_loss
- **trades**: timestamp;buyer;seller;symbol;currency;price;quantity
- Currency: XIRECs
- Timestamps: increment by 100 (0, 100, 200, ...)
- ~10,000 timesteps per day

## Key Observations from Tutorial Data

### EMERALDS
- Mid-price locked at ~10,000 every timestep
- Spread: best bid ~9992, best ask ~10008 (spread = 16)
- 2 price levels typically visible
- Extremely stable - pure market making opportunity

### TOMATOES
- Mid-price drifts over time (starts ~5000-5006, varies day to day)
- More volatile than EMERALDS
- Occasionally shows 3 levels of depth
- Spread varies: typically ~13-15 but tightens/widens
- Shows directional trends within a day

## Expected Round Types (Based on Prosperity 3 Pattern)

| Round | Type | Products Expected | Core Strategy |
|-------|------|-------------------|---------------|
| 1 | Market Making | Stationary + drifting assets | MM + adaptive MM |
| 2 | Basket Arbitrage | Basket ETF + constituents | Statistical arb, z-score |
| 3 | Options | Underlying + vouchers/options | Black-Scholes, IV trading |
| 4 | Cross-Market | Product tradeable across exchanges | Conversion arb with fees |
| 5 | Information | All products + trader IDs revealed | Copy-trading informed bots |

## Strategy Framework

### 1. Alpha Engine (Fair Value Estimation)
- Stationary: fixed value (e.g., EMERALDS = 10,000)
- Drifting: EMA of mid-price, VWAP, or weighted regression
- Volatile: Bollinger bands, z-score mean-reversion

### 2. Risk Engine
- Soft position limits (e.g., start tightening at 60% of hard limit)
- Skew quotes based on inventory (bid tighter when long, ask tighter when short)
- Max drawdown checks via traderData

### 3. Inventory Management
- Track position in traderData
- Reduce spread asymmetrically to shed inventory
- Never let worst-case fills breach position limits

### 4. Execution
- Aggressive: take mispriced orders from the book immediately
- Passive: place limit orders at fair_value +/- spread
- Hybrid: take extreme mispricings, quote passively otherwise

### 5. Per-Product Config (expand as rounds unlock)
```python
PRODUCT_CONFIG = {
    "EMERALDS": {"fair_value": 10000, "spread": 2, "limit": 80, "strategy": "fixed_mm"},
    "TOMATOES": {"ema_window": 20, "spread": 3, "limit": 80, "strategy": "adaptive_mm"},
}
```

## Python Version

Use **Python 3.13** via `py -3.13`. For console output with unicode, set `PYTHONIOENCODING=utf-8`.

## Backtesting

### Community Backtester (Prosperity 4)
```bash
py -3.13 -m prosperity4bt trader.py 0      # Run tutorial round
py -3.13 -m prosperity4bt trader.py 0--2   # Run specific day
```

### Baseline Results (2026-03-24)
```
Round 0 day -2: 6,458 XIRECs (EMERALDS: 1,919 | TOMATOES: 4,540)
Round 0 day -1: 5,267 XIRECs (EMERALDS: 2,104 | TOMATOES: 3,163)
Total:         11,726 XIRECs
```

### Visualization
- IMC Prosperity Visualizer: https://jmerle.github.io/imc-prosperity-visualizer/

## Coding Conventions

- All trading logic in a single `trader.py` (submission constraint)
- Use `json.dumps()`/`json.loads()` for traderData serialization
- Keep strategies modular within the single file using helper methods
- Price is always `int`, quantity is `int` (positive = buy, negative = sell)
- sell_orders in OrderDepth have **negative** quantities
- Always log key state with `print()` for debugging (visible in activity logs)
- Test locally with backtester before every submission

## Common Pitfalls

- Forgetting sell_orders quantities are negative
- Not accounting for worst-case position limit check (ALL orders, not individual)
- Hardcoding values that change between rounds
- Not persisting state properly in traderData (init called once, run called per tick)
- Placing orders that cross your own orders (unnecessary self-trade)
- Ignoring market_trades data (contains valuable signal about bot behavior)

## Reference Repos (Top Teams from Prior Years)

- 2nd Place P3: https://github.com/TimoDiehm/imc-prosperity-3
- 9th Place P3: https://github.com/CarterT27/imc-prosperity-3
- 7th Place P3: https://github.com/chrispyroberts/imc-prosperity-3
- 2nd Place P2: https://github.com/ericcccsliu/imc-prosperity-2
- Strategy Guide: https://github.com/MarkBrezina/Ctrl-Alt-DefeatTheMarket
