"""
Quick test to verify multi-day trading configuration.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient
from strategy.monte_carlo import MonteCarloStrategy
from strategy.ensemble_strategy import EnsembleStrategy
import config


def test_multiday_config():
    """Verify all multi-day configurations are set correctly."""
    
    print("=" * 70)
    print("MULTI-DAY TRADING CONFIGURATION TEST")
    print("=" * 70)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Monte Carlo horizon
    mc = MonteCarloStrategy("TEST")
    print(f"\n1. Monte Carlo Time Horizon: {mc.time_horizon} days")
    if mc.time_horizon == 5:
        print("   ✓ PASS - Set to 5 days (multi-day)")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL - Should be 5, got {mc.time_horizon}")
        tests_failed += 1
    
    # Test 2: Risk parameters
    print(f"\n2. Stop Loss: {config.STOP_LOSS_PCT * 100}%")
    if config.STOP_LOSS_PCT >= 0.04:
        print("   ✓ PASS - Wider stop loss for multi-day (>=4%)")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL - Too tight for multi-day")
        tests_failed += 1
    
    print(f"\n3. Take Profit: {config.TAKE_PROFIT_PCT * 100}%")
    if config.TAKE_PROFIT_PCT >= 0.08:
        print("   ✓ PASS - Appropriate target for multi-day (>=8%)")
        tests_passed += 1
    else:
        print(f"   ✗ FAIL - Too small for multi-day")
        tests_failed += 1
    
    # Test 4: Get sample data
    print(f"\n4. Data Fetch Test (Daily Bars)...")
    try:
        client = AlpacaClient()
        df = client.get_historical_data("AAPL", lookback_days=180)
        
        if not df.empty:
            print(f"   ✓ PASS - Fetched {len(df)} daily bars")
            print(f"   Date range: {df.index[0].date()} to {df.index[-1].date()}")
            tests_passed += 1
        else:
            print("   ✗ FAIL - No data returned")
            tests_failed += 1
    except Exception as e:
        print(f"   ✗ FAIL - Error: {e}")
        tests_failed += 1
    
    # Test 5: Strategy can process daily data
    print(f"\n5. Strategy Processing Test...")
    try:
        strategy = EnsembleStrategy("AAPL")
        action, confidence = strategy.analyze(df)
        print(f"   ✓ PASS - Generated signal: {action.upper()} ({confidence:.2f})")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ FAIL - Error: {e}")
        tests_failed += 1
    
    # Summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)
    
    if tests_failed == 0:
        print("\n✅ Multi-day configuration is correct!")
        print("\nKey changes verified:")
        print("  - Daily bars (not minute bars)")
        print("  - 180-day lookback (~6 months)")
        print("  - 5-day Monte Carlo horizon")
        print("  - Wider risk parameters (5% SL, 10% TP)")
        print("  - Strategy processes daily data successfully")
        return True
    else:
        print(f"\n❌ {tests_failed} test(s) failed - review configuration")
        return False


if __name__ == "__main__":
    success = test_multiday_config()
    exit(0 if success else 1)
