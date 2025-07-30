# Mean reversion

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
import uuid
from order import Order
from oms import OrderManagementSystem
from order_book import LimitOrderBook
from position_tracker import PositionTracker
from market_data_loader import MarketDataLoader

def run_backtest(symbol, market_loader, risk_params, bollinger_win=20, num_std=2.0):
    history = market_loader.get_history(symbol)
    signals_df = pd.DataFrame(index=history.index)
    signals_df["timestamp"] = history.index

    # Compute Bollinger Bands
    rolling_mean = history["last_price"].rolling(bollinger_win).mean()
    rolling_std  = history["last_price"].rolling(bollinger_win).std()
    history["upper"] = rolling_mean + num_std * rolling_std
    history["lower"] = rolling_mean - num_std * rolling_std
    history["mid"]   = rolling_mean

    # Generate Signals
    prev_price = history["last_price"].shift(1)
    prev_upper = history["upper"].shift(1)
    prev_lower = history["lower"].shift(1)
    prev_mid   = history["mid"].shift(1)
    
    signals_df["signal"] = 0

    # Long Entry: crossed below lower band
    long_entry = (prev_price > prev_lower) & (history["last_price"] < history["lower"])
    # Short Entry: crossed above upper band
    short_entry = (prev_price < prev_upper) & (history["last_price"] > history["upper"])
    # Exit to Mid
    exit_pos = (prev_price < prev_mid) & (history["last_price"] > history["mid"]) | \
               (prev_price > prev_mid) & (history["last_price"] < history["mid"])

    signals_df.loc[long_entry, "signal"]  = 1
    signals_df.loc[short_entry, "signal"] = -1
    signals_df.loc[exit_pos, "signal"]    = 0

    oms     = OrderManagementSystem()
    book    = LimitOrderBook(symbol)
    tracker = PositionTracker(starting_cash=1_000_000.0)
    trades_list = []

    for _, row in signals_df.iterrows():
        sig = row["signal"]
        if sig == 0:
            continue

        price = None if risk_params.order_type == "market" else float(history.loc[row["timestamp"], "last_price"])

        order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side="buy" if sig > 0 else "sell",
            quantity=risk_params.order_size,
            type=risk_params.order_type,
            price=price,
            timestamp=row["timestamp"]
        )

        # Add fake counterparty to ensure execution
        counter_order = Order(
            id=f"FAKE-{uuid.uuid4()}",
            symbol=symbol,
            side="buy" if sig < 0 else "sell",
            quantity=risk_params.order_size,
            type="limit",
            price=float(history.loc[row["timestamp"], "last_price"]),
            timestamp=row["timestamp"]
        )

        oms.new_order(counter_order)
        oms.new_order(order)

        book.add_order(counter_order)
        reports = book.add_order(order)

        for rpt in reports:
            if str(rpt["order_id"]).startswith("FAKE"):
                continue
            tracker.update(rpt)
            trades_list.append(rpt.copy())

    last_price = history["last_price"].iloc[-1]
    summary = tracker.get_pnl_summary(current_prices={symbol: last_price})
    blotter_df = tracker.get_blotter()
    equity_curve = blotter_df["cash_flow"].cumsum() + tracker.cash
    returns = equity_curve.diff().fillna(0)
    sharpe  = returns.mean() / (returns.std() + 1e-9) * (252**0.5)
    max_dd  = (equity_curve - equity_curve.cummax()).min()

    metrics_dict = {
        "total_return": summary["total_pnl"] / 1_000_000.0,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe
    }

    return signals_df, trades_list, metrics_dict
