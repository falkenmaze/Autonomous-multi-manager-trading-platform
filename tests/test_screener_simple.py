
import sys
import os
from unittest.mock import MagicMock

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.screener import MarketScreener
from strategy.sentiment_analyzer import SentimentAnalyzer
from trading.alpaca_client import AlpacaClient

def test_screener_logic():
    print("=== Testing Screener Sentiment Logic ===")
    
    # 1. Setup Mocks
    mock_client = MagicMock(spec=AlpacaClient)
    # Explicitly attach data_client since spec might not cover instance attribs created in init
    mock_client.data_client = MagicMock() 
    
    mock_sentiment = MagicMock(spec=SentimentAnalyzer)
    
    # 2. Mock Data
    mock_snapshots = {}
    for sym in ['GOOD', 'BAD', 'NEUTRAL']:
        snap = MagicMock()
        snap.latest_trade.price = 100.0
        snap.daily_bar.close = 105.0
        snap.daily_bar.open = 100.0 # +5%
        snap.daily_bar.volume = 5_000_000
        snap.previous_daily_bar.volume = 5_000_000
        mock_snapshots[sym] = snap
        
    mock_client.data_client.get_stock_snapshot.return_value = mock_snapshots
    
    # 3. Initialize Screener
    screener = MarketScreener(mock_client, mock_sentiment)
    screener.universe = ['GOOD', 'BAD', 'NEUTRAL'] # Override universe
    
    # 4. Define Sentiment Behavior
    def analyze_sentiment_side_effect(symbol):
        if symbol == 'GOOD': 
            return 0.8
        if symbol == 'BAD': 
            return -0.5 # Should be dropped
        return 0.1
        
    mock_sentiment.analyze_sentiment.side_effect = analyze_sentiment_side_effect
    mock_sentiment.analyze_market_sentiment.return_value = -0.3 # Bearish Market
    
    # 5. Run it
    print("Running get_active_assets...")
    picks = screener.get_active_assets(limit=3)
    
    print(f"\nFinal Picks: {picks}")
    
    # 6. Verify
    if 'BAD' not in picks:
        print("✅ SUCCESS: 'BAD' stock was dropped due to negative sentiment.")
    else:
        print("❌ FAILURE: 'BAD' stock was NOT dropped.")
        
    if 'GOOD' in picks:
        print("✅ SUCCESS: 'GOOD' stock was kept.")

    market_calls = mock_sentiment.analyze_market_sentiment.call_count
    if market_calls > 0:
        print("✅ SUCCESS: Market Sentiment was checked.")
    else:
         print("❌ FAILURE: Market Sentiment was NOT checked.")

    print("=== Test Complete ===")

if __name__ == "__main__":
    test_screener_logic()
