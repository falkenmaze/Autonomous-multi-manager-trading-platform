"""
Simplified diagnostic - focuses on key metrics.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient
from strategy.ensemble_strategy import EnsembleStrategy


def quick_diagnose():
    """Quick diagnosis of signal strength."""
    client = AlpacaClient()
    symbols = ['NVDA', 'PLTR', 'MARA', 'TSLA', 'UBER']
    
    print("Symbol Analysis")
    print("-" * 80)
    print(f"{'Symbol':<8} {'MC':<8} {'RF':<8} {'Final':<8} {'Drift':<12} {'RF_Acc':<10}")
    print("-" * 80)
    
    for symbol in symbols:
        try:
            df = client.get_historical_data(symbol, lookback_days=30)
            if df.empty:
                continue
            
            strategy = EnsembleStrategy(symbol)
            action, confidence = strategy.analyze(df)
            
            # Calculate drift
            log_returns = np.log(1 + df['close'].pct_change().dropna())
            drift = log_returns.mean() - (0.5 * log_returns.var())
            
            # Get RF training accuracy
            feature_df = strategy.prepare_features(df)
            if len(feature_df) >= 50:
                features = ['rsi', 'volatility', 'volume_ratio']
                X = feature_df[features]
                y = feature_df['target']
                strategy.rf.fit(X, y)
                rf_acc = (strategy.rf.predict(X) == y).mean()
            else:
                rf_acc = 0.0
            
            # Extract MC and RF probs from the analyze output
            mc_prob = strategy.mc.run_simulation(df)
            
            current_df = strategy.prepare_features(df.iloc[-100:].copy())
            if not current_df.empty:
                last_features = current_df.iloc[-1:][['rsi', 'volatility', 'volume_ratio']]
                rf_prob = strategy.rf.predict_proba(last_features)[0][1]
            else:
                rf_prob = 0.5
            
            print(f"{symbol:<8} {mc_prob:<8.3f} {rf_prob:<8.3f} {confidence:<8.3f} {drift:<12.6f} {rf_acc:<10.3f}")
            
        except Exception as e:
            print(f"{symbol:<8} ERROR: {e}")
    
    print("\n" + "="*80)
    print("FINDINGS:")
    print("="*80)
    print("1. MONTE CARLO: Near 0.50 means drift is ~0 (no directional trend)")
    print("2. RANDOM FOREST: Near 0.50 means low predictive power")
    print("3. RF Accuracy < 0.60: Features are weak predictors")
    print("\nRECOMMENDATIONS:")
    print("- Add more features (MACD, Bollinger Bands, momentum indicators)")
    print("- Use longer lookback for drift calculation")
    print("- Consider different target (e.g., return over next 5 bars)")
    print("- OR: Lower thresholds to 0.52/0.48 to start trading anyway")


if __name__ == "__main__":
    quick_diagnose()
