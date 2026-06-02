import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

class EventManager:
    """
    Manages market events like earnings calendars.
    """
    def __init__(self):
        self.earnings_cache = {} # symbol -> earnings_datetime
        
    def get_upcoming_earnings(self, symbol):
        """
        Fetches the next earnings date for a symbol.
        Returns datetime object or None.
        """
        # Return cached value if it's from today
        if symbol in self.earnings_cache:
            cached_date, fetch_time = self.earnings_cache[symbol]
            if datetime.now() - fetch_time < timedelta(days=1):
                return cached_date
        
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            
            earnings_date = None
            
            if cal is not None:
                # Some yfinance versions return a dictionary
                if isinstance(cal, dict):
                    earnings_date = cal.get('Earnings Date')
                
                # Some return a DataFrame
                elif isinstance(cal, pd.DataFrame) and not cal.empty:
                    if 'Earnings Date' in cal.index:
                        earnings_date = cal.loc['Earnings Date'].iloc[0]
                
                # Some return a list
                elif isinstance(cal, list) and len(cal) > 0:
                    earnings_date = cal[0]

                # If we have a list of dates, take the first one
                if isinstance(earnings_date, (list, pd.Series)) and len(earnings_date) > 0:
                    earnings_date = earnings_date[0]
                
                if earnings_date:
                    self.earnings_cache[symbol] = (earnings_date, datetime.now())
                    return earnings_date
                
        except Exception as e:
            print(f"  [Event] Error fetching earnings for {symbol}: {e}")
            
        return None

    def is_near_earnings(self, symbol, window_days=3):
        """
        Checks if earnings are within ± window_days.
        """
        earnings_date = self.get_upcoming_earnings(symbol)
        if earnings_date is None:
            return False, None
            
        # Ensure it's a naive or UTC-compatible datetime
        if hasattr(earnings_date, 'to_pydatetime'):
            earnings_date = earnings_date.to_pydatetime()
            
        # Some yfinance dates come back with timezones, others don't.
        # datetime.date objects don't have tzinfo, so check first.
        if hasattr(earnings_date, 'tzinfo') and earnings_date.tzinfo is not None:
            earnings_date = earnings_date.replace(tzinfo=None)
            
        # If it's a date object, convert to datetime for arithmetic
        if not isinstance(earnings_date, datetime):
            earnings_date = datetime.combine(earnings_date, datetime.min.time())
            
        now = datetime.now()
        diff = earnings_date - now
        
        is_near = abs(diff.days) <= window_days
        return is_near, earnings_date
