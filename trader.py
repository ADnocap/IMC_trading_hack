from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    """
    IMC Prosperity 4 Trading Algorithm
    Tutorial Round: EMERALDS (stationary MM) + TOMATOES (adaptive MM)
    """

    # ── Product Configuration ──────────────────────────────────────────
    PARAMS = {
        "EMERALDS": {
            "strategy": "fixed_mm",
            "fair_value": 10000,
            "take_width": 1,       # take orders within this distance of fair value
            "spread": 2,           # passive quote half-spread
            "limit": 80,
            "soft_limit": 60,      # start skewing inventory beyond this
        },
        "TOMATOES": {
            "strategy": "adaptive_mm",
            "ema_alpha": 0.15,     # EMA smoothing (higher = more responsive)
            "take_width": 2,       # take orders within this distance of fair value
            "spread": 3,           # passive quote half-spread
            "limit": 80,
            "soft_limit": 60,
        },
    }

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        conversions = 0

        # ── Restore persistent state ──────────────────────────────────
        trader_data = {}
        if state.traderData:
            try:
                trader_data = json.loads(state.traderData)
            except json.JSONDecodeError:
                trader_data = {}

        # ── Trade each product ────────────────────────────────────────
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            params = self.PARAMS.get(product)
            if not params:
                result[product] = []
                continue

            position = state.position.get(product, 0)

            if params["strategy"] == "fixed_mm":
                orders, trader_data = self.fixed_market_making(
                    product, order_depth, position, params, trader_data
                )
            elif params["strategy"] == "adaptive_mm":
                orders, trader_data = self.adaptive_market_making(
                    product, order_depth, position, params, trader_data, state
                )
            else:
                orders = []

            result[product] = orders

        traderData = json.dumps(trader_data)
        return result, conversions, traderData

    # ── Strategy: Fixed Fair-Value Market Making ──────────────────────
    def fixed_market_making(
        self, product: str, od: OrderDepth, position: int,
        params: dict, trader_data: dict
    ) -> tuple[List[Order], dict]:
        orders: List[Order] = []
        fair = params["fair_value"]
        limit = params["limit"]
        take_w = params["take_width"]
        spread = params["spread"]
        soft = params["soft_limit"]

        # ── Phase 1: Aggressive takes (cross mispriced orders) ────────
        # Take cheap asks (buy)
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price > fair - take_w:
                break
            ask_vol = od.sell_orders[ask_price]  # negative
            can_buy = limit - position
            if can_buy <= 0:
                break
            qty = min(-ask_vol, can_buy)
            orders.append(Order(product, ask_price, qty))
            position += qty

        # Take expensive bids (sell)
        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price < fair + take_w:
                break
            bid_vol = od.buy_orders[bid_price]  # positive
            can_sell = limit + position
            if can_sell <= 0:
                break
            qty = min(bid_vol, can_sell)
            orders.append(Order(product, bid_price, -qty))
            position -= qty

        # ── Phase 2: Passive quotes with inventory skew ───────────────
        skew = self._inventory_skew(position, soft, limit)

        bid_price = int(fair - spread + skew)
        ask_price = int(fair + spread + skew)

        bid_qty = limit - position
        ask_qty = limit + position

        if bid_qty > 0:
            orders.append(Order(product, bid_price, bid_qty))
        if ask_qty > 0:
            orders.append(Order(product, ask_price, -ask_qty))

        return orders, trader_data

    # ── Strategy: Adaptive (EMA) Market Making ────────────────────────
    def adaptive_market_making(
        self, product: str, od: OrderDepth, position: int,
        params: dict, trader_data: dict, state: TradingState
    ) -> tuple[List[Order], dict]:
        orders: List[Order] = []
        limit = params["limit"]
        take_w = params["take_width"]
        spread = params["spread"]
        soft = params["soft_limit"]
        alpha = params["ema_alpha"]

        # Calculate current mid-price
        if not od.buy_orders or not od.sell_orders:
            return orders, trader_data

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        # Update EMA fair value
        ema_key = f"{product}_ema"
        if ema_key in trader_data:
            ema = trader_data[ema_key] * (1 - alpha) + mid * alpha
        else:
            ema = mid
        trader_data[ema_key] = ema

        fair = round(ema)

        # ── Phase 1: Aggressive takes ─────────────────────────────────
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price > fair - take_w:
                break
            ask_vol = od.sell_orders[ask_price]
            can_buy = limit - position
            if can_buy <= 0:
                break
            qty = min(-ask_vol, can_buy)
            orders.append(Order(product, ask_price, qty))
            position += qty

        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price < fair + take_w:
                break
            bid_vol = od.buy_orders[bid_price]
            can_sell = limit + position
            if can_sell <= 0:
                break
            qty = min(bid_vol, can_sell)
            orders.append(Order(product, bid_price, -qty))
            position -= qty

        # ── Phase 2: Passive quotes with inventory skew ───────────────
        skew = self._inventory_skew(position, soft, limit)

        bid_price = int(fair - spread + skew)
        ask_price = int(fair + spread + skew)

        bid_qty = limit - position
        ask_qty = limit + position

        if bid_qty > 0:
            orders.append(Order(product, bid_price, bid_qty))
        if ask_qty > 0:
            orders.append(Order(product, ask_price, -ask_qty))

        return orders, trader_data

    # ── Helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _inventory_skew(position: int, soft_limit: int, hard_limit: int) -> float:
        """
        Returns a price skew to discourage accumulating more inventory.
        Positive skew = shift quotes up (discourages buying, encourages selling).
        Negative skew = shift quotes down (discourages selling, encourages buying).
        """
        if abs(position) <= soft_limit:
            return 0
        # Linear skew that grows from 0 at soft_limit to -1 at hard_limit
        excess = abs(position) - soft_limit
        max_excess = hard_limit - soft_limit
        skew_magnitude = (excess / max_excess) * 1.0
        return -skew_magnitude if position > 0 else skew_magnitude
