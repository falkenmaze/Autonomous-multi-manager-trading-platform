
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.screener import MarketScreener
from strategy.sentiment_analyzer import SentimentAnalyzer
from trading.alpaca_client import AlpacaClient

class TestScreenerSentiment(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=AlpacaClient)
        self.mock_sentiment = MagicMock(spec=SentimentAnalyzer)
        
        # Setup Screener with mocks
        self.screener = MarketScreener(self.mock_client, self.mock_sentiment)
        
        # Mock Snapshot Data to return some dummy assets
        # We need to simulate the structure: snapshots -> dict{symbol: snapshot}
        # snapshot -> latest_trade.price, daily_bar.volume, previous_daily_bar.volume
        
        self.mock_snapshots = {}
        for sym in ['GOOD', 'BAD', 'UGLY']:
            snap = MagicMock()
            snap.latest_trade.price = 150.0
            snap.daily_bar.close = 155.0
            snap.daily_bar.open = 150.0 # +3% change
            snap.daily_bar.volume = 5_000_000
            snap.previous_daily_bar.volume = 5_000_000
            self.mock_snapshots[sym] = snap
            
        self.mock_client.data_client.get_stock_snapshot.return_value = self.mock_snapshots
        
    def test_market_sentiment_check(self):
        print("\n--- Testing Market Sentiment Check ---")
        # 1. Simulate Bullish Market
        self.mock_sentiment.analyze_market_sentiment.return_value = 0.50
        self.screener.get_active_assets(limit=2)
        self.mock_sentiment.analyze_market_sentiment.assert_called()
        print("✅ Called analyze_market_sentiment()")

    def test_candidate_validation(self):
        print("\n--- Testing Candidate Validation ---")
        # 1. Setup specific sentiment
        # GOOD -> +0.5 (Keep)
        # BAD -> -0.5 (Drop)
        # UGLY -> -0.8 (Drop)
        
        def side_effect(symbol):
            if symbol == 'GOOD': return 0.5
            if symbol == 'BAD': return -0.5
            return 0.0
            
        self.mock_sentiment.analyze_sentiment.side_effect = side_effect
        
        # 2. Run Screener
        picks = self.screener.get_active_assets(limit=3)
        
        # 3. Verify
        print(f"Final Picks: {picks}")
        self.assertIn('GOOD', picks)
        self.assertNotIn('BAD', picks)
        print("✅ Correctly rejected 'BAD' due to negative sentiment.")

if __name__ == "__main__":
    unittest.main()
