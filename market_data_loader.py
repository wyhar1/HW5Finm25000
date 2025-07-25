"""
Market data loader class and methods
"""
import yfinance as yf
import pandas as pd
import pytz
class MarketDataLoader:
    def __init__(self, interval, period):
        self.interval = interval
        self.period = period
        #Cache..? ChatGPT suggested
        self._period_cache = {}
        self._range_cache = {}
    
    def _rename_and_tx(self, df):
        #Handle bad call
        if df.empty:
             return df
        #Rename columns
        df = df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'last_price',
            'Volume': 'volume'
        })
        if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None).tz_localize('UTC')
        return df

    def _load_period(self, symbol):
        data = yf.download(symbol, period=self.period, interval=self.interval, auto_adjust=True)
        data = self._rename_and_tx(data)
        self._period_cache[symbol] = data
        return data
    
    def get_history(self, symbol, start=None, end=None): 
        if start or end:
            data = yf.download(symbol, start=start, end=end, interval=self.interval, auto_adjust=True)
        else:
            data = self._load_period(symbol)
        return data

    def _locate_timestamp(self, df, ts):
        ts = pd.to_datetime(ts).tz_localize('UTC')
        if ts in df.index:
            return ts
        #Not found, use ffill
        idx = df.index.get_indexer([ts], method='ffill')[0]
        return df.index[idx]
        
    def _scalar_to_float(self, x):
        return float(x)
    def _scalar_to_int(self, x):
        return int(x)

    def get_price(self, symbol, timestamp):
        ##############
        #Only returns the close price of the ticker for one day
        ##############
        #Convert timestamp to be a date
        date_str = timestamp.strftime("%Y-%m-%d")
        data = yf.download(symbol, start=date_str, interval="1d", auto_adjust=True)
        return self._scalar_to_float(data.iloc[0,0])
    
    def get_bid_ask(self,symbol, timestamp):
        """
        yfinance doesn't provide historic bid ask spreads.
        This function just guesses what it might have been using the current bid ask spread.
        """
        #Convert timestamp to be a date
        date_str = timestamp.strftime("%Y-%m-%d")
        price = self.get_price(symbol, timestamp)
        ticker = yf.Ticker(symbol)
        quote = ticker.info
        bid = quote.get("bid")
        ask = quote.get("ask")
        spread = ask-bid
        assumed_bid = price-spread
        assumed_ask = price+spread
        return (self._scalar_to_float(assumed_bid), self._scalar_to_float(assumed_ask))
    
    def get_volume(self, symbol, start, end):
        data = self.get_history(symbol, start, end)
        volume_sum = data['Volume'].sum()
        return self._scalar_to_int(volume_sum.iloc[0])
    
    def get_option_chain(self, symbol, expiry=None):
        ticker = yf.Ticker(symbol)
        if expiry: 
            option_chain = ticker.option_chian(expiry)
        else:
            expiration_dates = ticker.options
            option_chain = ticker.option_chain(expiration_dates[0])
        call_chain = option_chain.calls
        put_chain = option_chain.puts
        return call_chain, put_chain
