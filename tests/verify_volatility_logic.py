import sys
import os
sys.path.insert(0, os.getcwd())
import pandas as pd
import numpy as np
from strategy.ensemble_strategy import EnsembleStrategy
import config

def verify_logic():
    print("=== VOLATILITY LOGIC VERIFICATION ===")
    
    # 1. Create dummy data (Price always 100)
    dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
    df = pd.DataFrame({
        'open': [100.0] * 200,
        'high': [100.0] * 200,
        'low': [100.0] * 200,
        'close': [100.0] * 200,
        'volume': [1000] * 200
    }, index=dates)
    
    strategy = EnsembleStrategy("TEST_TICKER")
    
    # Mock some basic values to avoid NaN
    df['close'] = 100 + np.sin(np.linspace(0, 10, 200)) # Add some movement
    
    # Scenario A: CALM VIX (15.0)
    print("\nScenario A: Calm Market (VIX 15.0)")
    action, conf, reason, _ = strategy.analyze(df, vix_level=15.0)
    print(f"Action: {action} | Conf: {conf:.4f}")
    print(f"Reason: {reason}")
    
    # Scenario B: HIGH VIX (35.0)
    print("\nScenario B: High Volatility (VIX 35.0)")
    action_h, conf_h, reason_h, _ = strategy.analyze(df, vix_level=35.0)
    print(f"Action: {action_h} | Conf: {conf_h:.4f}")
    print(f"Reason: {reason_h}")
    
    # Verify Gap Protection
    base_gap = config.MIN_CONFIDENCE_GAP
    dynamic_gap = base_gap * config.DYNAMIC_GAP_MULTIPLIER
    print(f"\nProtection Check: Base Gap {base_gap}, Dynamic Gap {dynamic_gap}")
    
    if "VIX Protected" in reason_h:
        print("✅ SUCCESS: VIX Protection logic detected and logged.")
    else:
        print("❌ FAILURE: VIX Protection log missing.")

if __name__ == "__main__":
    verify_logic()
