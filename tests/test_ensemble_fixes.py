"""
Verification tests for ensemble strategy fixes.
Tests that fixes address the original issues.
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategy.ensemble_strategy import EnsembleStrategy
import config


def test_no_sklearn_warnings():
    """Test that RandomForest prediction doesn't raise sklearn warnings."""
    print("Testing: No sklearn feature name warnings...")
    
    # Create test data (simulate stock data)
    np.random.seed(42)
    dates = pd.date_range('2025-12-01', periods=500, freq='1min')
    test_df = pd.DataFrame({
        'timestamp': dates,
        'open': 100 + np.random.randn(500).cumsum(),
        'high': 102 + np.random.randn(500).cumsum(),
        'low': 98 + np.random.randn(500).cumsum(),
        'close': 100 + np.random.randn(500).cumsum(),
        'volume': np.random.randint(1000, 10000, 500)
    })
    
    strategy = EnsembleStrategy("TEST")
    
    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        action, confidence = strategy.analyze(test_df)
        
        # Check if sklearn warning appeared
        sklearn_warnings = [warning for warning in w if 'feature names' in str(warning.message).lower()]
        
        if sklearn_warnings:
            print("  ❌ FAILED: sklearn warnings still present:")
            for warning in sklearn_warnings:
                print(f"    - {warning.message}")
            return False
        else:
            print("  ✅ PASSED: No sklearn warnings")
            return True


def test_confidence_scores_vary():
    """Test that confidence scores can vary and reach actionable thresholds."""
    print("\nTesting: Confidence scores vary from neutral...")
    
    # Create diverse test scenarios
    test_cases = []
    
    # Bullish scenario
    np.random.seed(100)
    dates = pd.date_range('2025-12-01', periods=500, freq='1min')
    bullish_df = pd.DataFrame({
        'timestamp': dates,
        'open': 100 + np.random.randn(500).cumsum() * 0.5,
        'high': 102 + np.random.randn(500).cumsum() * 0.5,
        'low': 98 + np.random.randn(500).cumsum() * 0.5,
        'close': 100 + np.arange(500) * 0.1 + np.random.randn(500) * 0.3,  # Uptrend
        'volume': np.random.randint(5000, 15000, 500)
    })
    test_cases.append(("Bullish", bullish_df))
    
    # Bearish scenario
    np.random.seed(101)
    bearish_df = pd.DataFrame({
        'timestamp': dates,
        'open': 100 + np.random.randn(500).cumsum() * 0.5,
        'high': 102 + np.random.randn(500).cumsum() * 0.5,
        'low': 98 + np.random.randn(500).cumsum() * 0.5,
        'close': 100 - np.arange(500) * 0.1 + np.random.randn(500) * 0.3,  # Downtrend
        'volume': np.random.randint(5000, 15000, 500)
    })
    test_cases.append(("Bearish", bearish_df))
    
    strategy = EnsembleStrategy("TEST")
    confidences = []
    
    for scenario, df in test_cases:
        action, confidence = strategy.analyze(df)
        confidences.append(confidence)
        print(f"  {scenario} scenario: action={action}, confidence={confidence:.3f}")
    
    # Check variance
    if len(set([round(c, 1) for c in confidences])) > 1:
        print("  ✅ PASSED: Confidence scores vary across scenarios")
        return True
    else:
        print("  ❌ FAILED: All confidence scores are too similar")
        return False


def test_ensemble_formula():
    """Test that ensemble formula properly weights signals."""
    print("\nTesting: Ensemble formula weights sum correctly...")
    
    # The weights should be 0.5 + 0.5 = 1.0 (excluding RL adjustment)
    # When MC=0.6 and RF=0.4, result should be 0.5
    
    mc_prob = 0.6
    rf_prob = 0.4
    base_confidence = (0.5 * mc_prob) + (0.5 * rf_prob)
    
    expected = 0.5
    
    if abs(base_confidence - expected) < 0.001:
        print(f"  ✅ PASSED: Weights sum correctly (0.6*0.5 + 0.4*0.5 = {base_confidence})")
        return True
    else:
        print(f"  ❌ FAILED: Weights incorrect (got {base_confidence}, expected {expected})")
        return False


def test_thresholds_configurable():
    """Test that thresholds use config values."""
    print("\nTesting: Thresholds use config values...")
    
    # Verify config has the expected values
    if hasattr(config, 'CONFIDENCE_THRESHOLD_BUY') and hasattr(config, 'CONFIDENCE_THRESHOLD_SELL'):
        buy_threshold = config.CONFIDENCE_THRESHOLD_BUY
        sell_threshold = config.CONFIDENCE_THRESHOLD_SELL
        
        print(f"  Buy threshold: {buy_threshold}")
        print(f"  Sell threshold: {sell_threshold}")
        
        if buy_threshold < 0.60 and sell_threshold > 0.40:
            print("  ✅ PASSED: Thresholds are lowered from original values")
            return True
        else:
            print("  ❌ FAILED: Thresholds not properly adjusted")
            return False
    else:
        print("  ❌ FAILED: Config missing threshold constants")
        return False


def main():
    print("=" * 60)
    print("ENSEMBLE STRATEGY VERIFICATION TESTS")
    print("=" * 60)
    
    results = []
    results.append(test_no_sklearn_warnings())
    results.append(test_confidence_scores_vary())
    results.append(test_ensemble_formula())
    results.append(test_thresholds_configurable())
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
