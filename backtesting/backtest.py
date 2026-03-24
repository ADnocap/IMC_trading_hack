#!/usr/bin/env python3
"""
Realistic backtester for IMC Prosperity 4.
Simulates step-5 passive fills with calibrated probability.

The community backtester (prosperity4bt) has three modes:
  --match-trades all:   fills against all market trades → WAY too optimistic
  --match-trades worse: fills at strictly better prices → still too high
  --match-trades none:  book-only → too pessimistic (no passive fills)

This backtester sits between 'none' and 'all' by using a probabilistic
fill model for passive (non-crossing) orders, calibrated to portal results.

Usage:
    py -3.13 backtesting/backtest.py                        # defaults
    py -3.13 backtesting/backtest.py --fill-rate 0.05       # tune fill rate
    py -3.13 backtesting/backtest.py --no-passive           # same as 'none' mode
"""
import sys
import os
import csv
import random
import importlib.util

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from datamodel import (
    OrderDepth, TradingState, Order, Listing, Trade, Observation,
)

# ── Limits (must match portal) ──────────────────────────────────────
LIMITS = {"EMERALDS": 80, "TOMATOES": 80}

# ── Passive fill parameters ─────────────────────────────────────────
# Calibrated to portal submission 18425:
#   TOMATOES: 44 fills / ~600 market trades ≈ 7% per-trade fill probability
#   Average fill qty ≈ 3.5 out of market trade qty ≈ 5 → ~50% capture
DEFAULT_FILL_RATE = 0.05
DEFAULT_QTY_FRAC = 0.50

ROUND_DIR = os.path.join(ROOT, "TUTORIAL_ROUND_1")
DAYS = [-2, -1]


def load_trader():
    spec = importlib.util.spec_from_file_location(
        "trader", os.path.join(ROOT, "trader.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Trader()


def load_prices(day):
    """Returns {timestamp: {product: (OrderDepth, mid_price)}}"""
    path = os.path.join(ROUND_DIR, f"prices_round_0_day_{day}.csv")
    data = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            ts = int(row["timestamp"])
            product = row["product"].strip()
            if ts not in data:
                data[ts] = {}
            od = OrderDepth()
            for i in range(1, 4):
                bp, bv = row.get(f"bid_price_{i}", "").strip(), row.get(f"bid_volume_{i}", "").strip()
                if bp and bv:
                    od.buy_orders[int(float(bp))] = int(float(bv))
                ap, av = row.get(f"ask_price_{i}", "").strip(), row.get(f"ask_volume_{i}", "").strip()
                if ap and av:
                    od.sell_orders[int(float(ap))] = -int(float(av))
            mid = float(row.get("mid_price", 0))
            data[ts][product] = (od, mid)
    return data


def load_trades(day):
    """Returns {timestamp: [(symbol, price, quantity), ...]}"""
    path = os.path.join(ROUND_DIR, f"trades_round_0_day_{day}.csv")
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            ts = int(row["timestamp"])
            if ts not in data:
                data[ts] = []
            data[ts].append((
                row["symbol"].strip(),
                int(float(row["price"])),
                int(row["quantity"]),
            ))
    return data


def enforce_limits(pos, orders, product):
    """Cancel ALL orders for a product if worst-case breaches limit."""
    limit = LIMITS.get(product, 0)
    p = pos.get(product, 0)
    total_buy = sum(o.quantity for o in orders if o.quantity > 0)
    total_sell = sum(-o.quantity for o in orders if o.quantity < 0)
    if p + total_buy > limit or p - total_sell < -limit:
        return []
    return orders


def match_orders(orders, book, mkt_trades, product, pos, fill_rate, qty_frac):
    """
    Two-phase matching:
      1. Aggressive: orders crossing the book fill at book price
      2. Passive: resting orders filled probabilistically from market trade flow
    Returns list of (price, signed_qty) fills.
    """
    fills = []
    cur_pos = pos.get(product, 0)
    limit = LIMITS.get(product, 0)

    # Mutable copy of the book
    sells = dict(book.sell_orders)  # price -> neg vol
    buys = dict(book.buy_orders)   # price -> pos vol

    resting = []

    for order in orders:
        matched = False

        if order.quantity > 0:  # Buy
            for ap in sorted(sells):
                if sells[ap] >= 0:
                    continue
                if order.price >= ap:
                    fq = min(order.quantity, -sells[ap])
                    if abs(cur_pos + fq) <= limit:
                        fills.append((ap, fq))
                        cur_pos += fq
                        sells[ap] += fq
                        matched = True
                    break

        else:  # Sell
            for bp in sorted(buys, reverse=True):
                if buys[bp] <= 0:
                    continue
                if order.price <= bp:
                    fq = min(-order.quantity, buys[bp])
                    if abs(cur_pos - fq) <= limit:
                        fills.append((bp, -fq))
                        cur_pos -= fq
                        buys[bp] -= fq
                        matched = True
                    break

        if not matched:
            resting.append(order)

    # Phase 2: passive fills from step-5 bots
    if fill_rate > 0:
        prod_trades = [(p, q) for sym, p, q in mkt_trades if sym == product]
        for trade_price, trade_qty in prod_trades:
            for order in resting:
                if order.quantity > 0:  # Resting buy
                    if order.price >= trade_price and random.random() < fill_rate:
                        fq = min(order.quantity, max(1, int(trade_qty * qty_frac)))
                        if abs(cur_pos + fq) <= limit:
                            fills.append((order.price, fq))
                            cur_pos += fq
                            order.quantity -= fq
                elif order.quantity < 0:  # Resting sell
                    if order.price <= trade_price and random.random() < fill_rate:
                        fq = min(-order.quantity, max(1, int(trade_qty * qty_frac)))
                        if abs(cur_pos - fq) <= limit:
                            fills.append((order.price, -fq))
                            cur_pos -= fq
                            order.quantity += fq

    pos[product] = cur_pos
    return fills


def run_day(day, fill_rate, qty_frac, seed=42):
    random.seed(seed + abs(day))
    prices = load_prices(day)
    trades = load_trades(day)
    trader = load_trader()

    timestamps = sorted(prices.keys())
    products = sorted({p for ts_data in prices.values() for p in ts_data})

    pos = {p: 0 for p in products}
    cash = {p: 0.0 for p in products}
    mid = {p: 0.0 for p in products}
    trader_data = ""
    total_fills = {p: 0 for p in products}

    for ts in timestamps:
        # Build order depths
        order_depths = {}
        for product in products:
            if product in prices[ts]:
                od, m = prices[ts][product]
                order_depths[product] = od
                mid[product] = m

        state = TradingState(
            traderData=trader_data,
            timestamp=ts,
            listings={p: Listing(p, p, 1) for p in products},
            order_depths=order_depths,
            own_trades={p: [] for p in products},
            market_trades={p: [] for p in products},
            position=dict(pos),
            observations=Observation({}, {}),
        )

        result, _, trader_data = trader.run(state)

        mkt = trades.get(ts, [])
        for product in products:
            product_orders = result.get(product, [])
            if not product_orders:
                continue
            product_orders = enforce_limits(pos, product_orders, product)
            if not product_orders or product not in order_depths:
                continue

            fills = match_orders(
                product_orders, order_depths[product], mkt,
                product, pos, fill_rate, qty_frac,
            )
            for price, qty in fills:
                total_fills[product] += 1
                if qty > 0:
                    cash[product] -= price * qty
                else:
                    cash[product] += price * abs(qty)

    # Final PnL: cash + mark-to-market
    pnl = {p: cash[p] + pos[p] * mid[p] for p in products}
    return pnl, pos, total_fills


def main():
    fill_rate = DEFAULT_FILL_RATE
    qty_frac = DEFAULT_QTY_FRAC

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--fill-rate" and i + 1 < len(args):
            fill_rate = float(args[i + 1])
            i += 2
        elif args[i] == "--qty-frac" and i + 1 < len(args):
            qty_frac = float(args[i + 1])
            i += 2
        elif args[i] == "--no-passive":
            fill_rate = 0.0
            i += 1
        else:
            i += 1

    mode = "passive fills OFF" if fill_rate == 0 else f"fill_rate={fill_rate}, qty_frac={qty_frac}"
    print(f"Realistic Backtester ({mode})")
    print("=" * 60)

    grand_total = 0
    for day in DAYS:
        pnl, pos, nfills = run_day(day, fill_rate, qty_frac)
        day_total = sum(pnl.values())
        grand_total += day_total
        print(f"\nDay {day}:")
        for p in sorted(pnl):
            print(f"  {p:>10}: {pnl[p]:>10,.0f}  (pos={pos[p]:>4}, fills={nfills[p]})")
        print(f"  {'Total':>10}: {day_total:>10,.0f}")

    print(f"\n{'=' * 60}")
    print(f"Grand total: {grand_total:>10,.0f}")
    print(f"\nPortal ref (submission 18425): 979")


if __name__ == "__main__":
    main()
