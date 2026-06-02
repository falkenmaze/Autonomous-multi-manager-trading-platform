
import unittest
from unittest.mock import MagicMock
from trading.screener import MarketScreener
from trading.alpaca_client import AlpacaClient

class MockSnapshot:
    def __init__(self, price, volume, open_price=100, close_price=101):
        self.latest_trade = MagicMock()
        self.latest_trade.price = price
        self.daily_bar = MagicMock()
        self.daily_bar.volume = volume
        self.daily_bar.open = open_price
        self.daily_bar.close = close_price

class TestScreenerFilter(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock(spec=AlpacaClient)
        self.client.data_client = MagicMock()
        self.screener = MarketScreener(self.client)

    def test_quality_filters(self):
        """Verify that penny stocks and low volume stocks are filtered out."""
        
        # Mock Data
        snapshots = {
            'GOOD': MockSnapshot(price=150, volume=5_000_000),      # Should Pass
            'PENNY': MockSnapshot(price=2.0, volume=5_000_000),     # Fail: Price < 10
            'ILLIQUID': MockSnapshot(price=150, volume=50_000),     # Fail: Vol < 1M
            'ZOMBIE': MockSnapshot(price=150, volume=0, open_price=150, close_price=150) # Fail: Zombie
        }
        
        self.client.data_client.get_stock_snapshot.return_value = snapshots
        
        # We need to ensure the universe logic doesn't crash, so let's mock the universe to match keys
        self.screener.universe = list(snapshots.keys())
        
        # Run
        active_assets = self.screener.get_active_assets()
        
        print(f"Active Assets passed filter: {active_assets}")
        
        self.assertIn('GOOD', active_assets)
        self.assertNotIn('PENNY', active_assets)
        self.assertNotIn('ILLIQUID', active_assets)
        self.assertNotIn('ZOMBIE', active_assets)

if __name__ == '__main__':
    unittest.main()
