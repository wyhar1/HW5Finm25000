#Trend Following
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


import pandas as pd
import uuid
from datetime import datetime

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from order import Order
from order import risk_params
from oms import OrderManagementSystem
from order_book import LimitOrderBook
from position_tracker import PositionTracker
from market_data_loader import MarketDataLoader


def run_backtest(symbol, market_loader, risk_params, short_win=5, long_win=25):
    """
    There is some funky business going on here, but I'm not sure what.
    """
    
    history = market_loader.get_history(symbol)
    signals_df = pd.DataFrame(index=history.index)
    signals_df['timestamp'] = history.index
    
    history["ma_short"] = history["last_price"].rolling(short_win).mean()
    history["ma_long"]  = history["last_price"].rolling(long_win).mean()
    signals_df['signal'] = 0

    ma_short = history["ma_short"]
    ma_long = history["ma_long"]
    
    for i in range(1, len(ma_short)):
        if ma_short[i-1] <  ma_long[i-1] and ma_short[i] > ma_long[i]:
            signals_df.loc[signals_df.index[i], "signal"] = 1
        elif ma_short[i-1] > ma_long[i-1] and ma_short[i] < ma_long[i]:
            signals_df.loc[signals_df.index[i], "signal"] = -1
        else:
            signals_df.loc[signals_df.index[i], "signal"] = 0

    oms = OrderManagementSystem()
    book = LimitOrderBook(symbol)
    ###
    starting_cash_var = 1000000.0
    ###
    tracker = PositionTracker(starting_cash = starting_cash_var)
    trades_list = []

    
    for _, row in signals_df.iterrows():
        sig = row['signal']
        if sig == 0:
            continue

        order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side="buy" if sig > 0 else "sell",
            quantity=risk_params.order_size,
            type=risk_params.order_type,
            price=None if risk_params.order_type == "market" else float(history.loc[row['timestamp'], 'last_price'].squeeze()),
            timestamp=row['timestamp']
        )
        

        """
        WE MUST CREATE A COUNTERPARTY TO EVERY ORDER WE MAKE OR WE JUST SET UP A BUNCH OF UNFULFILLED ORDERS
        Ignore the order details though, it's just trash imaginary trades based on the historic price.
        """
        counter_order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side="buy" if sig < 0 else "sell",
            quantity=risk_params.order_size,
            type="limit",
            price= float(history.loc[row['timestamp'], 'last_price'].squeeze()),
            timestamp=row['timestamp']
        )
        ###CHAT GPT SUGGESTED, CORRECTING COUNTER ORDERS GETTING PROCESSED IN TRACKER###
        counter_order.id = f"FAKE-{uuid.uuid4()}"
        ##########
        
        ack2 = oms.new_order(counter_order)
        ack = oms.new_order(order)
        book.add_order(counter_order)
        reports = book.add_order(order)

        
        for rpt in reports:
            #PART 2 OF CORRECTING COUNTER ORDERS
            if str(rpt["order_id"]).startswith("FAKE"):
                continue 
            #####
            tracker.update(rpt)
            trades_list.append(rpt)
    last_price = history["last_price"].squeeze() 
    summary = tracker.get_pnl_summary(current_prices={symbol: last_price.iloc[-1]})
    blotter_df = tracker.get_blotter()
    equity_curve = blotter_df["cash_flow"].cumsum() + starting_cash_var
    returns = equity_curve.diff().fillna(0)
    sharpe  = returns.mean() / returns.std() * (252**0.5)
    max_dd  = (equity_curve - equity_curve.cummax()).min()
    metrics_dict = {
        "total_return": (summary["total_pnl"] / starting_cash_var),
        "max_drawdown": max_dd,    # compute from tracker.blotter or equity curve
        "sharpe_ratio": sharpe     # compute returns.std() etc.
    }
    return signals_df, trades_list, metrics_dict

rp = risk_params()
loader = MarketDataLoader(interval="1h", period="1y")
signals, trades, metrics = run_backtest("CMPS", loader, rp)
print(metrics)
