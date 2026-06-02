
from trading.alpaca_client import AlpacaClient
import pandas as pd

client = AlpacaClient()

print("Fetching SPY...")
spy = client.get_historical_data("SPY", lookback_days=10)
print("SPY Index:")
print(spy.index)
print(spy.head())

print("\nFetching MARA...")
mara = client.get_historical_data("MARA", lookback_days=10)
print("MARA Index:")
print(mara.index)
print(mara.head())

# Try alignment - Corrected
asset_ret = mara['close'].reset_index(level=0, drop=True).pct_change().dropna()
spy_ret = spy['close'].reset_index(level=0, drop=True).pct_change().dropna()

data = pd.DataFrame({'asset': asset_ret, 'spy': spy_ret}).dropna()
print(f"\nAligned Data Length: {len(data)}")
if len(data) > 0:
    print("Alignment SUCCESS!")
    print(data.head())
else:
    print("Alignment failed!")
