
import unittest
from unittest.mock import MagicMock
from trading.screener import MarketScreener
from trading.alpaca_client import AlpacaClient
import config_tickers

class TestUniverse(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock(spec=AlpacaClient)
        self.client.data_client = MagicMock()
        self.screener = MarketScreener(self.client)

    def test_universe_loading(self):
        """Verify that the screener loaded the full S&P 100 list."""
        self.assertEqual(len(self.screener.universe), len(config_tickers.SP100_TICKERS))
        self.assertIn('AAPL', self.screener.universe)
        self.assertIn('XOM', self.screener.universe)
        print(f"✅ Universe loaded successfully: {len(self.screener.universe)} tickers.")

    def test_snapshot_chunking(self):
        """Verify that we can request snapshots for the whole universe."""
        # Alpaca's get_stock_snapshot can handle list of symbols. 
        # We just want to ensure we pass the list correctly.
        
        # Mock Response
        mock_response = {
            'AAPL': MagicMock(latest_trade=MagicMock(price=150), daily_bar=MagicMock(close=150, open=149, volume=10000000)),
            'MSFT': MagicMock(latest_trade=MagicMock(price=300), daily_bar=MagicMock(close=300, open=299, volume=5000000))
        }
        self.client.data_client.get_stock_snapshot.return_value = mock_response
        
        active = self.screener.get_active_assets()
        
        # Verify call arguments
        call_args = self.client.data_client.get_stock_snapshot.call_args
        request = call_args[0][0] # First arg is request object
        
        self.assertEqual(request.symbol_or_symbols, config_tickers.SP100_TICKERS)
        print("✅ Correctly requested snapshot for entire S&P 100 list.")

if __name__ == '__main__':
    unittest.main()
