
import sys
import os
import pandas as pd
import time

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient
from strategy.ensemble_strategy import EnsembleStrategy
import config

def verify_reasoning():
    print("=== Verifying Trade Reasoning Logic ===")
    
    # 1. Setup
    client = AlpacaClient()
    symbol = 'SPY' # Liquid stuff ensures data
    
    print(f"Fetching data for {symbol}...")
    df = client.get_historical_data(symbol, lookback_days=100)
    
    if df.empty:
        print("❌ Error: No data fetched.")
        return
        
    # 2. Initialize Strategy
    print("Initializing Strategy...")
    strategy = EnsembleStrategy(symbol)
    
    # 3. Run Analyze
    print("Running Analyze...")
    try:
        # This is where we verify the signature change
        action, confidence, reason = strategy.analyze(df)
        
        print("\n✅ SUCCESS! Method returned 3 values.")
        print(f"  Action: {action}")
        print(f"  Confidence: {confidence:.4f}")
        print(f"  Reason: {reason}")
        
        # 4. output validation
        if "Regime:" in reason and "MC:" in reason:
             print("\n✅ Reason string contains expected components.")
        else:
             print("\n❌ Reason string format looks wrong.")
             
    except ValueError as e:
        print(f"\n❌ FAILED: ValueError unpacking return. Likely signature mismatch. {e}")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")

if __name__ == "__main__":
    verify_reasoning()
