from datetime import datetime
from typing import List, Dict
from order import Order

class LimitOrderBook:
    """
    A simple price–time priority limit order book.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        # bids: list of resting buy orders, highest price first
        self.bids: List[Order] = []
        # asks: list of resting sell orders, lowest price first
        self.asks: List[Order] = []
    
    def add_order(self, order: Order) -> List[Dict]:
        """
        Handle a new incoming order (market, limit, or stop).
        Returns a list of execution report dicts.
        """
        reports = []

        if order.type == "market":
            reports += self._execute_market(order)

        elif order.type == "limit":
            # try to match immediately
            reports += self._match_limit(order)
            # if there’s leftover quantity, add to book
            if order.quantity > 0:
                self._insert_resting(order)

        else:
            # for now, treat stop orders as plain limit orders 
            # once triggered by strategy logic
            reports += self._match_limit(order)
            if order.quantity > 0:
                self._insert_resting(order)

        return reports
    
    def _match_limit(self, order: Order) -> List[Dict]:
        """
        Match a limit order against the book.
        Fill as much as possible at prices satisfying the limit.
        """
        reports = []
        # choose opposite side
        opposite = self.asks if order.side == "buy" else self.bids

        # continue matching while we still have quantity
        # and there is a resting order that satisfies the price
        while order.quantity > 0 and opposite:
            best = opposite[0]
            # buy order matches if best ask <= order.price
            if order.side == "buy" and best.price > order.price:
                break
            # sell order matches if best bid >= order.price
            if order.side == "sell" and best.price < order.price:
                break

            # a fill occurs: trade quantity = min(incoming, resting)
            fill_qty   = min(order.quantity, best.quantity)
            trade_price = best.price
            timestamp   = datetime.utcnow()

            # build execution report for the incoming order
            reports.append({
                "order_id":      order.id,
                "symbol":        order.symbol,
                "side":          order.side,
                "filled_qty":    fill_qty,
                "price":         trade_price,
                "timestamp":     timestamp,
                "status":        "filled" if fill_qty == order.quantity else "partial_fill"
            })

            # also build report for the resting order
            reports.append({
                "order_id":      best.id,
                "symbol":        best.symbol,
                "side":          best.side,
                "filled_qty":    fill_qty,
                "price":         trade_price,
                "timestamp":     timestamp,
                "status":        "filled" if fill_qty == best.quantity else "partial_fill"
            })

            # decrement quantities
            order.quantity -= fill_qty
            best.quantity  -= fill_qty

            # remove resting order if fully filled
            if best.quantity == 0:
                opposite.pop(0)

        return reports
    
    def _execute_market(self, order: Order) -> List[Dict]:
        """
        Fill a market order against the full depth of the book.
        """
        reports = []
        # opposite side = asks if buy; bids if sell
        opposite = self.asks if order.side == "buy" else self.bids

        while order.quantity > 0 and opposite:
            best = opposite[0]
            fill_qty    = min(order.quantity, best.quantity)
            trade_price = best.price
            timestamp   = datetime.utcnow()

            reports.append({
                "order_id":   order.id,
                "symbol":     order.symbol,
                "side":       order.side,
                "filled_qty": fill_qty,
                "price":      trade_price,
                "timestamp":  timestamp,
                "status":     "filled" if fill_qty == order.quantity else "partial_fill"
            })

            reports.append({
                "order_id":   best.id,
                "symbol":     best.symbol,
                "side":       best.side,
                "filled_qty": fill_qty,
                "price":      trade_price,
                "timestamp":  timestamp,
                "status":     "filled" if fill_qty == best.quantity else "partial_fill"
            })

            order.quantity -= fill_qty
            best.quantity  -= fill_qty

            if best.quantity == 0:
                opposite.pop(0)

        return reports
    def _insert_resting(self, order: Order):
        """
        Place a remainder limit order into bids or asks,
        maintaining sorted order.
        """
        book = self.bids if order.side == "buy" else self.asks

        # find insertion index
        idx = 0
        while idx < len(book):
            # for bids: descending price; for asks: ascending price
            better_price = (book[idx].price > order.price) if order.side == "buy" \
                            else (book[idx].price < order.price)
            if better_price:
                idx += 1
            else:
                break

        # insert at idx
        book.insert(idx, order)
