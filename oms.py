from order import Order
from datetime import datetime
from typing import Dict, Optional

class OrderManagementSystem:
    """
    Validates, tracks, and optionally routes orders.
    """
    def __init__(self, matching_engine=None):
        # store orders (Order objects) and statuses by order ID
        self._orders: Dict[str, Order]  = {}
        self._statuses: Dict[str, str]  = {}
        # optional matching engine to forward orders
        self.matching_engine = matching_engine
    
    def new_order(self, order: Order) -> dict:
        # 1) Basic field checks
        if order.side not in ("buy", "sell"):
            raise ValueError("Side must be 'buy' or 'sell'")
        if order.quantity <= 0:
            raise ValueError("Quantity must be > 0")
        if order.type not in ("market", "limit", "stop"):
            raise ValueError("Type must be 'market', 'limit', or 'stop'")
        if order.type in ("limit", "stop") and order.price is None:
            raise ValueError("Limit/stop orders require a price")

        # 2) Timestamp if missing
        now = datetime.utcnow()
        order.timestamp = order.timestamp or now

        # 3) Save order & status
        self._orders[order.id]   = order
        self._statuses[order.id] = "accepted"

        # 4) Forward to matching engine
        if self.matching_engine:
            self.matching_engine.add_order(order)

        # 5) Acknowledge
        return {
            "order_id": order.id,
            "status":   "accepted",
            "timestamp": order.timestamp
        }
    def cancel_order(self, order_id: str) -> dict:
        if order_id not in self._orders:
            raise KeyError(f"Order {order_id} not found")
        current = self._statuses[order_id]
        if current in ("canceled", "filled"):
            raise ValueError(f"Cannot cancel order in status {current}")
        self._statuses[order_id] = "canceled"
        return {
            "order_id": order_id,
            "status":   "canceled",
            "timestamp": datetime.utcnow()
        }
    def amend_order(
        self,
        order_id:   str,
        new_qty:    Optional[int]   = None,
        new_price:  Optional[float] = None
    ) -> dict:
        if order_id not in self._orders:
            raise KeyError(f"Order {order_id} not found")
        if self._statuses[order_id] != "accepted":
            raise ValueError("Only accepted orders can be amended")

        order = self._orders[order_id]
        if new_qty is not None:
            if new_qty <= 0:
                raise ValueError("Quantity must be > 0")
            order.quantity = new_qty
        if new_price is not None:
            if order.type not in ("limit", "stop"):
                raise ValueError("Only limit/stop orders can change price")
            order.price = new_price

        order.timestamp = datetime.utcnow()
        return {
            "order_id": order_id,
            "status":   "amended",
            "timestamp": order.timestamp
        } 
