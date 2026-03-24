---
name: prosperity
description: Helper for the IMC Prosperity 4 algorithmic trading competition. Use this skill whenever the user wants to backtest their trading algorithm, analyze market data, validate their submission, optimize strategy parameters, or check their competition status. Trigger on mentions of prosperity, backtesting trader.py, trading strategy optimization, submission validation, or EDA on round data. Also trigger when the user says things like "run the bot", "test my algo", "check my PnL", "how's my strategy doing", or "prepare for submission".
---

# Prosperity - IMC Trading Competition Helper

You are helping with the IMC Prosperity 4 algorithmic trading competition. The project lives at `C:\Users\alexa\OneDrive\Documents\IMC_trading_hack`.

## Setup

- **Python**: Use `py -3.13` (Python 3.13)
- **Backtester**: `prosperity4btx` package (run via `py -3.13 -m prosperity4bt`)
- **Main algo file**: `trader.py` (single-file submission with `Trader` class)
- **Data**: `TUTORIAL_ROUND_1/` and subsequent `round_N/` folders
- **Analysis**: `analysis/tutorial_eda.py`
- **Unicode output**: Prefix commands with `PYTHONIOENCODING=utf-8` when needed

## Subcommands

Parse the user's input to determine which subcommand to run. If no subcommand is given, default to **status**.

---

### `/prosperity` or `/prosperity status`

Show a status overview:

1. Read `trader.py` and extract the `PARAMS` dict to list all products, their strategies, and key parameters
2. Find the most recent `.log` file in `backtests/` directory (sorted by filename which is a timestamp)
3. If a recent backtest exists, report the PnL breakdown from it. If not, suggest running a backtest.
4. List all available data directories (TUTORIAL_ROUND_1, round_N, etc.)

Format output as a concise dashboard:

```
## Prosperity Status
**Products**: EMERALDS (fixed_mm, fair=10000), TOMATOES (adaptive_mm, ema=0.15)
**Last Backtest**: 2026-03-24 - Total: 11,726 XIRECs
  Day -2: 6,458 (EMERALDS: 1,919 | TOMATOES: 4,540)
  Day -1: 5,267 (EMERALDS: 2,104 | TOMATOES: 3,163)
**Available Data**: TUTORIAL_ROUND_1
```

---

### `/prosperity backtest` or `/prosperity backtest [round]`

Run the backtester and report results:

1. Default round is `0` (tutorial). If the user specifies a round number, use that.
2. Run: `cd "C:/Users/alexa/OneDrive/Documents/IMC_trading_hack" && py -3.13 -m prosperity4bt trader.py <round>`
3. Parse the output for per-product PnL and total profit
4. Compare against previous backtest results if available (check `backtests/` for the previous log)
5. Report results with a clear comparison showing improvement or regression per product

If the backtest fails, read the error carefully and diagnose it. Common issues:
- Import errors (missing modules)
- Position limit violations
- Syntax errors in trader.py

---

### `/prosperity analyze` or `/prosperity analyze [round]`

Run exploratory data analysis:

1. Run: `cd "C:/Users/alexa/OneDrive/Documents/IMC_trading_hack" && PYTHONIOENCODING=utf-8 py -3.13 analysis/tutorial_eda.py`
2. Parse the output and present key findings in a structured summary
3. Highlight actionable insights:
   - Is the fair value estimate correct for each product?
   - Are spreads tight enough to capture edge?
   - What's the trade frequency and typical volume?
   - Any drift patterns that need attention?

If analyzing a new round's data, check if the EDA script needs updating first (it may only handle tutorial data).

---

### `/prosperity submit`

Validate `trader.py` for submission readiness:

1. **Read `trader.py`** and check:
   - Has a `Trader` class
   - Has a `run(self, state: TradingState)` method
   - Returns a 3-tuple `(result, conversions, traderData)`
   - `result` is `Dict[str, List[Order]]`
   - `conversions` is `int`
   - `traderData` is `str`
   - All imports are from allowed modules (standard library, numpy, jsonpickle, datamodel)
   - No file I/O, no network calls, no subprocess usage
   - No environment variable reads that won't exist in the sandbox
   - Position limits are respected (check that worst-case fills don't exceed limits)

2. **Run a backtest** to confirm no runtime errors:
   `cd "C:/Users/alexa/OneDrive/Documents/IMC_trading_hack" && py -3.13 -m prosperity4bt trader.py 0`

3. **Report**:
   - Green/pass for each check
   - Warnings for any issues
   - Final verdict: "Ready to submit" or "Fix issues before submitting"
   - Remind the user to upload the single `trader.py` file on the Prosperity platform

---

### `/prosperity optimize [product]`

Analyze and suggest parameter improvements for a specific product:

1. **Read `trader.py`** to get current parameters for the product
2. **Read the relevant price/trade CSVs** for that product
3. **Analyze**:
   - Is the fair value correct? Compare against actual mid-price distribution
   - Is the spread optimal? Too wide = missing fills, too narrow = adverse selection
   - Is the EMA alpha tuned well? Compare different alpha values against the price series
   - Are take_width thresholds capturing enough edge?
   - Is the soft_limit/hard_limit balance right for inventory management?
4. **Suggest specific parameter changes** with reasoning
5. **Optionally run a backtest** with the suggested changes to show projected improvement

If no product is specified, analyze all products.

---

## General Guidelines

- Always `cd` to the project directory before running commands
- Use `py -3.13` for all Python execution
- Set `PYTHONIOENCODING=utf-8` when output may contain unicode
- When showing PnL changes, use clear +/- formatting and highlight improvements
- Reference the CLAUDE.md for project context when needed
- The competition adds new products each round - check what products exist in trader.py's PARAMS before making assumptions
