
from datetime import datetime
import pandas as pd
import pytz

class ConfigMock:
    MARKET_OPEN_START_HOUR = 9
    MARKET_OPEN_START_MIN = 30
    MARKET_OPEN_DURATION_MINS = 30

config = ConfigMock()

def is_market_open_window(dt, market_tz):
    # This is the logic from Trader.py
    open_time = dt.replace(hour=config.MARKET_OPEN_START_HOUR, 
                            minute=config.MARKET_OPEN_START_MIN, 
                            second=0, microsecond=0)
    window_end = open_time + pd.Timedelta(minutes=config.MARKET_OPEN_DURATION_MINS)
    return open_time <= dt <= window_end

# Test cases
market_tz = pytz.timezone("US/Eastern")
tests = [
    (datetime(2026, 2, 18, 9, 30, tzinfo=market_tz), True),
    (datetime(2026, 2, 18, 9, 45, tzinfo=market_tz), True),
    (datetime(2026, 2, 18, 10, 0, tzinfo=market_tz), True),
    (datetime(2026, 2, 18, 10, 1, tzinfo=market_tz), False),
    (datetime(2026, 2, 18, 9, 29, tzinfo=market_tz), False),
    (datetime(2026, 2, 18, 12, 0, tzinfo=market_tz), False),
]

for dt, expected in tests:
    res = is_market_open_window(dt, market_tz)
    print(f"Time: {dt.strftime('%H:%M')} | Expected: {expected} | Result: {res}")
    assert res == expected

print("\n--- Logic Test Passed! ---")
