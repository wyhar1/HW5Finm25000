# Arbitrage
import pandas as pd
import numpy as np
import uuid
from datetime import datetime
from order import Order
from oms import OrderManagementSystem
from order_book import LimitOrderBook
from position_tracker import PositionTracker

def run_backtest(symbol1, symbol2, loader, risk_params, threshold=2.0):
    # Load price history
    hist1 = loader.get_history(symbol1)
    hist2 = loader.get_history(symbol2)
    sqz1 = hist1["last_price"].squeeze()
    sqz2 = hist2["last_price"].squeeze()

    # Align timestamps
    df = pd.DataFrame({
        "p1": sqz1,
        "p2": sqz2
    }).dropna()

    # Hedge ratio via linear regression
    beta = np.polyfit(df["p2"], df["p1"], 1)[0]
    df["spread"] = df["p1"] - beta * df["p2"]
    df["timestamp"] = df.index

    # Generate trading signals
    df["signal"] = 0
    for i in range(1, len(df)):
        prev_spread = df["spread"].iloc[i - 1]
        curr_spread = df["spread"].iloc[i]

        if prev_spread < threshold and curr_spread > threshold:
            df.loc[df.index[i], "signal"] = -1  # short spread
        elif prev_spread > -threshold and curr_spread < -threshold:
            df.loc[df.index[i], "signal"] = 1   # long spread
        elif abs(prev_spread) > threshold and abs(curr_spread) < threshold:
            df.loc[df.index[i], "signal"] = 0   # close position

    # Initialize systems
    oms = OrderManagementSystem()
    book1 = LimitOrderBook(symbol1)
    book2 = LimitOrderBook(symbol2)
    starting_cash = 1_000_000
    tracker = PositionTracker(starting_cash=starting_cash)
    trades_list = []

    # Loop over signals
    for i, row in df.iterrows():
        sig = row["signal"]
        if sig == 0:
            continue

        ts = row["timestamp"]
        price1 = row["p1"]
        price2 = row["p2"]
        qty = risk_params.order_size

        # Create orders: asset1 = p1, asset2 = p2
        order1 = Order(
            id=str(uuid.uuid4()),
            symbol=symbol1,
            side="buy" if sig > 0 else "sell",
            quantity=qty,
            type=risk_params.order_type,
            price=None if risk_params.order_type == "market" else float(price1),
            timestamp=ts
        )

        order2 = Order(
            id=str(uuid.uuid4()),
            symbol=symbol2,
            side="sell" if sig > 0 else "buy",  # opposite of order1
            quantity=qty,
            type=risk_params.order_type,
            price=None if risk_params.order_type == "market" else float(price2),
            timestamp=ts
        )

        # Insert counterparties to absorb orders (fake)
        counter1 = Order(
            id=f"FAKE-{uuid.uuid4()}",
            symbol=symbol1,
            side="sell" if sig > 0 else "buy",
            quantity=qty,
            type="limit",
            price=price1,
            timestamp=ts
        )
        counter2 = Order(
            id=f"FAKE-{uuid.uuid4()}",
            symbol=symbol2,
            side="buy" if sig > 0 else "sell",
            quantity=qty,
            type="limit",
            price=price2,
            timestamp=ts
        )

        oms.new_order(counter1)
        oms.new_order(counter2)
        oms.new_order(order1)
        oms.new_order(order2)

        book1.add_order(counter1)
        book2.add_order(counter2)
        reports1 = book1.add_order(order1)
        reports2 = book2.add_order(order2)

        for rpt in reports1 + reports2:
            if str(rpt["order_id"]).startswith("FAKE"):
                continue
            tracker.update(rpt)
            trades_list.append(rpt)

    # P&L
    last1 = df["p1"].iloc[-1]
    last2 = df["p2"].iloc[-1]
    summary = tracker.get_pnl_summary(current_prices={
        symbol1: last1,
        symbol2: last2
    })

    blotter_df = tracker.get_blotter()
    equity_curve = blotter_df["cash_flow"].cumsum() + starting_cash
    returns = equity_curve.diff().fillna(0)
    sharpe = returns.mean() / returns.std() * (252**0.5)
    max_dd = (equity_curve - equity_curve.cummax()).min()

    metrics_dict = {
        "total_return": summary["total_pnl"] / starting_cash,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe
    }

    return df, trades_list, metrics_dict


