"""
Test the enhanced ensemble strategy with all new indicators.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient
from strategy.ensemble_strategy import EnsembleStrategy
import config


def test_enhanced_strategy():
    """Test that enhanced strategy produces stronger signals."""
    print("=" * 70)
    print("ENHANCED STRATEGY TEST")
    print("=" * 70)
    
    client = AlpacaClient()
    symbols = ['NVDA', 'PLTR', 'MARA']
    
    print(f"\nThresholds: BUY >= {config.CONFIDENCE_THRESHOLD_BUY}, SELL <= {config.CONFIDENCE_THRESHOLD_SELL}")
    print("\n" + "-" * 70)
    
    signals_generated = 0
    
    for symbol in symbols:
        try:
            df = client.get_historical_data(symbol, lookback_days=30)
            if df.empty:
                continue
            
            strategy = EnsembleStrategy(symbol)
            # Test with calm VIX
            action, confidence, reason, news = strategy.analyze(df, vix_level=15.0) 
            print(f"[{symbol}] CALM VIX (15.0) -> Action: {action.upper()} | Conf: {confidence:.2f}")
            print(f"Reason: {reason}")
            
            if action != 'hold':
                signals_generated += 1

            # Test with high VIX
            action_h, conf_h, reason_h, news_h = strategy.analyze(df, vix_level=35.0)
            print(f"[{symbol}] HIGH VIX (35.0) -> Action: {action_h.upper()} | Conf: {conf_h:.2f}")
            print(f"Reason: {reason_h}")
            print("-" * 70)
            
        except Exception as e:
            print(f"{symbol}: ERROR - {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    if signals_generated > 0:
        print(f"[SUCCESS] {signals_generated} actionable signals generated!")
        print("   Enhanced strategy is producing buy/sell signals.")
    else:
        print(f"[WARNING] No actionable signals generated.")
        print("   Market may still be very neutral, but confidence should be closer to thresholds.")
    
    print("\nExpected improvements:")
    print("- Regime detection shows TREND/RANGE/MIXED")
    print("- Mean Reversion (MR) signal appears in ranging markets")
    print("- More varied confidence scores (not all ~0.50)")
    print("- Some symbols should trigger BUY or SELL")


if __name__ == "__main__":
    test_enhanced_strategy()
