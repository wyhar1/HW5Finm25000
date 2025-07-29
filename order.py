from dataclasses import dataclass
from datetime import datetime

@dataclass
class Order:
    """
    Represents a single trade instruction.
    """
    id:        str        # unique identifier (e.g. UUID or string)
    symbol:    str        # ticker or asset code (e.g. "AAPL", "EURUSD=X")
    side:      str        # "buy" or "sell"
    quantity:  int        # must be > 0
    type:      str        # "market", "limit", or "stop"
    price:     float = None   # limit/stop price, None for market orders
    timestamp: datetime = None  # when the order was created

@dataclass
class risk_params:
    """
    General risk parameters.
    """
    max_pos:        int = None    # max number of shares to be held
    order_size:     int = 50000        # number of shares to buy/sell at each order
    order_type:      str = "market" # "buy" or "sell"
