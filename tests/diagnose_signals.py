"""
Diagnostic script to investigate why signals are weak.
Analyzes Monte Carlo, Random Forest, and feature quality.
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient
from strategy.ensemble_strategy import EnsembleStrategy
from strategy.monte_carlo import MonteCarloStrategy
import ta


def analyze_monte_carlo(symbol, df):
    """Analyze Monte Carlo simulation in detail."""
    print(f"\n{'='*60}")
    print(f"MONTE CARLO ANALYSIS - {symbol}")
    print(f"{'='*60}")
    
    mc = MonteCarloStrategy(symbol)
    
    # Check data quality
    print(f"\nData Stats:")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    
    # Price statistics
    returns = df['close'].pct_change().dropna()
    print(f"\nPrice Movement:")
    print(f"  Current Price: ${df['close'].iloc[-1]:.2f}")
    print(f"  Price Range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print(f"  Price Change: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%")
    
    # Return statistics
    print(f"\nReturn Statistics:")
    print(f"  Mean Return: {returns.mean():.6f}")
    print(f"  Std Dev: {returns.std():.6f}")
    print(f"  Skewness: {returns.skew():.3f}")
    
    # Log returns for MC simulation
    log_returns = np.log(1 + returns)
    u = log_returns.mean()
    var = log_returns.var()
    drift = u - (0.5 * var)
    stdev = log_returns.std()
    
    print(f"\nMC Simulation Parameters:")
    print(f"  Drift: {drift:.6f}")
    print(f"  Volatility (stdev): {stdev:.6f}")
    if stdev > 0:
        print(f"  Drift/Vol Ratio (Sharpe-like): {drift/stdev:.3f}")
    
    # Run simulation
    mc_prob = mc.run_simulation(df)
    print(f"\n  → MC Probability: {mc_prob:.4f}")
    
    # Explain the result
    if abs(mc_prob - 0.5) < 0.05:
        print(f"\n⚠️ DIAGNOSIS: Very neutral signal!")
        if abs(drift) < 0.0001:
            print(f"   - Drift is near zero → no directional bias")
        if stdev > 0.02:
            print(f"   - High volatility → uncertain outcomes")
        else:
            print(f"   - Low volatility but no trend")
    
    return mc_prob


def analyze_random_forest(symbol, df):
    """Analyze Random Forest features and predictions."""
    print(f"\n{'='*60}")
    print(f"RANDOM FOREST ANALYSIS - {symbol}")
    print(f"{'='*60}")
    
    strategy = EnsembleStrategy(symbol)
    
    # Prepare features
    feature_df = strategy.prepare_features(df)
    
    if len(feature_df) < 50:
        print("⚠️ Not enough data for RF training")
        return 0.5
    
    # Train model
    features = ['rsi', 'volatility', 'volume_ratio']
    X = feature_df[features]
    y = feature_df['target']
    
    print(f"\nFeature Statistics:")
    print(X.describe())
    
    print(f"\nTarget Distribution:")
    print(f"  Up moves (1): {y.sum()} ({y.mean()*100:.1f}%)")
    print(f"  Down moves (0): {len(y) - y.sum()} ({(1-y.mean())*100:.1f}%)")
    
    # Train
    strategy.rf.fit(X, y)
    strategy.is_trained = True
    
    # Feature importance
    importances = strategy.rf.feature_importances_
    print(f"\nFeature Importance:")
    for feat, imp in zip(features, importances):
        print(f"  {feat}: {imp:.3f}")
    
    # Current features
    current_features = feature_df.iloc[-1:][features]
    print(f"\nCurrent Feature Values:")
    print(current_features.to_string())
    
    # Prediction
    rf_prob = strategy.rf.predict_proba(current_features)[0][1]
    print(f"\n  → RF Probability: {rf_prob:.4f}")
    
    # Training accuracy
    train_pred = strategy.rf.predict(X)
    accuracy = (train_pred == y).mean()
    print(f"\nTraining Accuracy: {accuracy:.3f}")
    
    if abs(rf_prob - 0.5) < 0.05:
        print(f"\n⚠️ DIAGNOSIS: Weak RF signal!")
        if accuracy < 0.6:
            print(f"   - Low training accuracy → features not predictive")
        if y.mean() > 0.45 and y.mean() < 0.55:
            print(f"   - Target is balanced → hard to predict direction")
    
    return rf_prob


def analyze_all_symbols():
    """Analyze all symbols in the current universe."""
    client = AlpacaClient()
    
    # Use same symbols from recent run
    symbols = ['NVDA', 'PLTR', 'MARA', 'TSLA', 'UBER']
    
    results = []
    
    for symbol in symbols:
        print(f"\n\n{'#'*60}")
        print(f"# ANALYZING: {symbol}")
        print(f"{'#'*60}")
        
        try:
            df = client.get_historical_data(symbol, lookback_days=30)
            
            if df.empty:
                print(f"No data for {symbol}")
                continue
            
            mc_prob = analyze_monte_carlo(symbol, df)
            rf_prob = analyze_random_forest(symbol, df)
            
            final_conf = (0.5 * mc_prob) + (0.5 * rf_prob)
            
            results.append({
                'symbol': symbol,
                'mc_prob': mc_prob,
                'rf_prob': rf_prob,
                'final': final_conf
            })
            
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Symbol':<8} {'MC':<8} {'RF':<8} {'Final':<8} {'Signal'}")
    print("-" * 50)
    for r in results:
        signal = 'BUY' if r['final'] > 0.55 else ('SELL' if r['final'] < 0.45 else 'HOLD')
        print(f"{r['symbol']:<8} {r['mc_prob']:<8.3f} {r['rf_prob']:<8.3f} {r['final']:<8.3f} {signal}")
    
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")
    
    avg_mc = np.mean([r['mc_prob'] for r in results])
    avg_rf = np.mean([r['rf_prob'] for r in results])
    
    print(f"\nAverage MC Probability: {avg_mc:.3f}")
    print(f"Average RF Probability: {avg_rf:.3f}")
    
    if avg_mc > 0.48 and avg_mc < 0.52:
        print("\n⚠️ Monte Carlo is very neutral across all symbols")
        print("   Possible causes:")
        print("   - Market is genuinely ranging (no clear trend)")
        print("   - Time horizon (30 min) may be too short")
        print("   - Need more sophisticated drift estimation")
    
    if avg_rf > 0.48 and avg_rf < 0.52:
        print("\n⚠️ Random Forest is very neutral across all symbols")
        print("   Possible causes:")
        print("   - Features (RSI, volatility, volume) are weak predictors")
        print("   - Need more/better features (MACD, Bollinger, momentum)")
        print("   - Target (next bar up/down) may be too noisy")


if __name__ == "__main__":
    analyze_all_symbols()
