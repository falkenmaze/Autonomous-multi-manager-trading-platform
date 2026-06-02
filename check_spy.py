import os
import sys
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from trading.alpaca_client import AlpacaClient

def check_spy():
    client = AlpacaClient()
    
    # Let's get 5 minute data for the last 3 days
    print("Fetching SPY data...")
    df = client.get_historical_data('SPY', lookback_days=5)
    
    if df.empty:
        print("Could not fetch SPY data.")
        return
        
    df = df.reset_index()
    mask = (df['timestamp'] >= '2026-03-24') & (df['timestamp'] <= '2026-03-27')
    df = df.loc[mask]
    
    print("Market Context (SPY):")
    # Let's print the daily open/close or specific timestamps
    
    important_times = [
        '2026-03-24 09:30:00-04:00',
        '2026-03-24 16:00:00-04:00',
        '2026-03-25 09:30:00-04:00',
        '2026-03-25 10:00:00-04:00',
        '2026-03-25 16:00:00-04:00',
        '2026-03-26 09:30:00-04:00',
        '2026-03-26 15:30:00-04:00'
    ]
    
    # We just print every 30 minutes to see the trend
    for idx, row in df.iterrows():
        ts_str = str(row['timestamp'])
        if ':00:00' in ts_str or ':30:00' in ts_str or '15:55:00' in ts_str:
            print(f"{ts_str} | SPY Close: {row['close']}")

if __name__ == '__main__':
    check_spy()
