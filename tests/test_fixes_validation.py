"""
Quick validation tests for the trade logging fix and sentiment hard veto.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
import config

def test_trade_logging_pipeline():
    """Test that DataLogger.log_trade creates trades.json and updates metrics."""
    print("Test 1: Trade logging pipeline...")
    
    from trading.data_logger import DataLogger
    
    # Use a temp directory to avoid writing to real logs
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the AlpacaClient to avoid API calls
        mock_client = MagicMock()
        logger = DataLogger(log_dir=tmpdir, client=mock_client)
        
        # Log a winning trade
        logger.log_trade("AAPL", entry_price=150.0, exit_price=160.0, qty=10, side='long')
        
        # Log a losing trade
        logger.log_trade("MSFT", entry_price=300.0, exit_price=290.0, qty=5, side='long')
        
        # Check trades.json was created
        trades_path = os.path.join(tmpdir, "trades.json")
        assert os.path.exists(trades_path), "trades.json should be created"
        
        import json
        with open(trades_path) as f:
            trades = json.load(f)
        
        assert len(trades) == 2, f"Expected 2 trades, got {len(trades)}"
        
        # Check win rate
        stats = logger.perf_calc.calculate_win_rate()
        assert stats['total_trades'] == 2, f"Expected 2 total trades, got {stats['total_trades']}"
        assert stats['wins'] == 1, f"Expected 1 win, got {stats['wins']}"
        assert stats['losses'] == 1, f"Expected 1 loss, got {stats['losses']}"
        assert stats['win_rate'] == 50.0, f"Expected 50% win rate, got {stats['win_rate']}"
        
        # Check PnL values
        assert trades[0]['pnl'] == 100.0, f"AAPL PnL should be 100, got {trades[0]['pnl']}"  # (160-150)*10
        assert trades[1]['pnl'] == -50.0, f"MSFT PnL should be -50, got {trades[1]['pnl']}"  # (290-300)*5
        
        print("  ✅ PASSED: trades.json created, win rate computed correctly")
        return True

def test_sentiment_hard_veto():
    """Test that extreme negative sentiment forces a hold."""
    print("\nTest 2: Sentiment hard veto...")
    
    from strategy.ensemble_strategy import EnsembleStrategy
    
    # Create a mock sentiment analyzer that returns extreme negative sentiment
    mock_sentiment = MagicMock()
    mock_sentiment.analyze_sentiment.return_value = (-0.95, {
        'source': 'Test',
        'headline': 'Stock crashes badly',
        'url': 'http://test.com',
        'score': -0.95,
        'tier': 1
    })
    
    strategy = EnsembleStrategy("TEST", sentiment_analyzer=mock_sentiment)
    
    # Create bullish price data (normally would generate a buy signal)
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        'open':   100 + np.arange(n) * 0.2 + np.random.randn(n) * 0.3,
        'high':   102 + np.arange(n) * 0.2 + np.random.randn(n) * 0.3,
        'low':    98 + np.arange(n) * 0.2 + np.random.randn(n) * 0.3,
        'close':  100 + np.arange(n) * 0.2 + np.random.randn(n) * 0.3,  # Strong uptrend
        'volume': np.random.randint(5000, 15000, n)
    })
    
    action, confidence, reason, news_meta = strategy.analyze(df, vix_level=15.0)
    
    print(f"  Action: {action}, Confidence: {confidence:.3f}")
    print(f"  Reason: {reason}")
    
    assert action == 'hold', f"Expected 'hold' on hard veto, got '{action}'"
    assert 'HARD VETO' in reason, f"Expected 'HARD VETO' in reason, got: {reason}"
    
    print("  ✅ PASSED: Extreme negative sentiment forces hold (hard veto)")
    return True

def test_sentiment_proportional_penalty():
    """Test that moderate negative sentiment applies proportional penalty."""
    print("\nTest 3: Sentiment proportional penalty...")
    
    from strategy.ensemble_strategy import EnsembleStrategy
    
    # Score of -0.3 is below VETO_THRESHOLD (-0.2) but above HARD_VETO (-0.6)
    # Should get proportional penalty: abs(-0.3) * 0.5 = 0.15
    mock_sentiment = MagicMock()
    mock_sentiment.analyze_sentiment.return_value = (-0.3, {
        'source': 'Test',
        'headline': 'Mild concern',
        'url': 'http://test.com',
        'score': -0.3,
        'tier': 2
    })
    
    strategy = EnsembleStrategy("TEST2", sentiment_analyzer=mock_sentiment)
    
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        'open':   100 + np.random.randn(n) * 0.5,
        'high':   102 + np.random.randn(n) * 0.5,
        'low':    98 + np.random.randn(n) * 0.5,
        'close':  100 + np.random.randn(n) * 0.5,
        'volume': np.random.randint(5000, 15000, n)
    })
    
    action, confidence, reason, news_meta = strategy.analyze(df, vix_level=15.0)
    
    print(f"  Action: {action}, Confidence: {confidence:.3f}")
    print(f"  Reason: {reason}")
    
    # Check that the proportional penalty is logged
    assert 'NEG -0.15' in reason, f"Expected proportional penalty logged as 'NEG -0.15', got: {reason}"
    
    print("  ✅ PASSED: Moderate negative sentiment applies proportional penalty")
    return True

def test_config_thresholds():
    """Test that new config values are accessible."""
    print("\nTest 4: Config thresholds...")
    
    assert hasattr(config, 'SENTIMENT_HARD_VETO_THRESHOLD'), "Missing SENTIMENT_HARD_VETO_THRESHOLD"
    assert hasattr(config, 'SENTIMENT_PENALTY_SCALE'), "Missing SENTIMENT_PENALTY_SCALE"
    assert config.SENTIMENT_HARD_VETO_THRESHOLD == -0.6, f"Expected -0.6, got {config.SENTIMENT_HARD_VETO_THRESHOLD}"
    assert config.SENTIMENT_PENALTY_SCALE == 0.5, f"Expected 0.5, got {config.SENTIMENT_PENALTY_SCALE}"
    
    print(f"  SENTIMENT_HARD_VETO_THRESHOLD = {config.SENTIMENT_HARD_VETO_THRESHOLD}")
    print(f"  SENTIMENT_PENALTY_SCALE = {config.SENTIMENT_PENALTY_SCALE}")
    print("  ✅ PASSED: New config values present and correct")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATION TESTS: Trade Logging + Sentiment Hardening")
    print("=" * 60)
    
    results = []
    results.append(test_trade_logging_pipeline())
    results.append(test_sentiment_hard_veto())
    results.append(test_sentiment_proportional_penalty())
    results.append(test_config_thresholds())
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All validation tests passed!")
    else:
        print("\n❌ Some tests failed")
    
    exit(0 if all(results) else 1)
