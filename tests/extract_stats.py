"""
Simple data extractor for diagnosis
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient


def extract_stats():
    client = AlpacaClient()
    symbols = ['NVDA', 'PLTR', 'MARA', 'TSLA', 'UBER']
    
    results = []
    
    for symbol in symbols:
        try:
            df = client.get_historical_data(symbol, lookback_days=30)
            if df.empty:
                continue
            
            # Price stats
            price_change_pct = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
            
            # Returns
            returns = df['close'].pct_change().dropna()
            log_returns = np.log(1 + returns)
            
            # Drift and volatility
            drift = log_returns.mean() - (0.5 * log_returns.var())
            vol = log_returns.std()
            
            results.append({
                'symbol': symbol,
                'price_chg': price_change_pct,
                'drift': drift,
                'vol': vol,
                'sharpe': drift / vol if vol > 0 else 0
            })
            
            print(f"{symbol}: Price Chg={price_change_pct:.2f}%, Drift={drift:.6f}, Vol={vol:.6f}, Sharpe={drift/vol if vol > 0 else 0:.3f}")
            
        except Exception as e:
            print(f"{symbol}: ERROR - {str(e)[:50]}")
    
    print("\nSUMMARY:")
    avg_drift = np.mean([r['drift'] for r in results])
    avg_sharpe = np.mean([r['sharpe'] for r in results])
    print(f"Average Drift: {avg_drift:.6f}")
    print(f"Average Sharpe: {avg_sharpe:.3f}")
    
    print("\nDIAGNOSIS:")
    if abs(avg_drift) < 0.0005:
        print("- Drift near zero: Market has no directional bias")
        print("- MC will produce ~0.50 probabilities")
    
    print("\nRECOMMENDATIONS:")
    print("1. Lower thresholds to 0.52/0.48 to enable trading")
    print("2. Add more technical features for RF")
    print("3. Consider different time horizons")


if __name__ == "__main__":
    extract_stats()
