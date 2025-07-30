import yfinance as yf
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas as pd

# Download historical data
data = yf.download("AAPL", start="2020-01-01", end="2024-01-01")

# Format to match Backtesting.py expectations
data = data.rename(columns={
    'Open': 'Open', 'High': 'High', 'Low': 'Low',
    'Close': 'Close', 'Volume': 'Volume'
})
data = data[['Open', 'High', 'Low', 'Close', 'Volume']]

# Define SMA Crossover Strategy
class SmaCross(Strategy):
    short_window = 20
    long_window = 50

    def init(self):
        self.ma_short = self.I(pd.Series.rolling, self.data.Close, self.short_window).mean()
        self.ma_long = self.I(pd.Series.rolling, self.data.Close, self.long_window).mean()

    def next(self):
        if crossover(self.ma_short, self.ma_long):
            self.buy()
        elif crossover(self.ma_long, self.ma_short):
            self.sell()

# Run backtest
bt = Backtest(data, SmaCross, cash=10000, commission=.002)
results = bt.run()
bt.plot()
print(results)

