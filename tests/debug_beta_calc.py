import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.portfolio_manager import PortfolioManager
from trading.alpaca_client import AlpacaClient

# Mock Client if needed, or use real one
# We will use real one to see real data issues
client = AlpacaClient()
pm = PortfolioManager(client)

def debug_beta(symbol):
    print(f"\n--- Debugging Beta for {symbol} ---")
    try:
        # 2. Fetch Data
        asset_df = client.get_historical_data(symbol, lookback_days=180)
        spy_df = client.get_historical_data('SPY', lookback_days=180)
        
        print(f"Asset Rows: {len(asset_df)}, SPY Rows: {len(spy_df)}")
        
        if asset_df.empty or spy_df.empty:
            print("EMPTY DATAFRAME")
            return

        # Log first few prices to check scale
        print(f"Asset Price Head: {asset_df['close'].head(3).values}")
        print(f"SPY Price Head: {spy_df['close'].head(3).values}")

        # 3. Align Data
        asset_ret = asset_df['close'].reset_index(level=0, drop=True).pct_change().dropna()
        spy_ret = spy_df['close'].reset_index(level=0, drop=True).pct_change().dropna()
        
        data = pd.DataFrame({'asset': asset_ret, 'spy': spy_ret}).dropna()
        print(f"Aligned Returns Rows: {len(data)}")
        
        if len(data) < 30:
            print("Insufficient Data")
            return

        # 4. Calc
        cov_matrix = np.cov(data['asset'], data['spy'], rowvar=False)
        covariance = cov_matrix[0, 1]
        variance_spy = cov_matrix[1, 1]
        variance_asset = cov_matrix[0, 0]
        
        beta = covariance / variance_spy
        
        print(f"Covariance: {covariance:.6f}")
        print(f"Var(SPY):   {variance_spy:.6f}")
        print(f"Var(Asset): {variance_asset:.6f}")
        print(f"Calculated BETA: {beta:.4f}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Test a few high profile tech stocks + a defensive one
for s in ['NVDA', 'TSLA', 'AAPL', 'KO']:
    debug_beta(s)
