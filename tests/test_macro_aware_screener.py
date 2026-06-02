import unittest
from unittest.mock import MagicMock, patch
from trading.screener import MarketScreener
from trading.alpaca_client import AlpacaClient
import pandas as pd

class TestMacroAwareScreener(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock(spec=AlpacaClient)
        self.macro = MagicMock()
        self.screener = MarketScreener(self.client, macro_manager=self.macro)

    @patch('trading.sector_manager.SectorManager.get_sector')
    def test_screener_boosts_defensive_sectors(self, mock_get_sector):
        # 1. Mock Macro Bias to be DEFENSIVE
        self.macro.get_market_bias.return_value = "DEFENSIVE"
        
        # 2. Mock Sector Mapping
        # Healthcare (Defensive) vs Technology (Cyclical)
        mock_get_sector.side_effect = lambda sym: "Healthcare" if sym == "JNJ" else "Technology"
        
        # 3. Mock Alpaca Snapshots
        # Give them identical performance/volume to see if multiplier breaks the tie
        mock_snapshot = MagicMock()
        mock_snapshot.latest_trade.price = 100.0
        mock_snapshot.daily_bar.open = 100.0
        mock_snapshot.daily_bar.close = 101.0
        mock_snapshot.daily_bar.volume = 1000000
        mock_snapshot.previous_daily_bar.volume = 1000000
        
        self.client.get_snapshots.return_value = {
            'JNJ': mock_snapshot,
            'AAPL': mock_snapshot
        }
        
        # 4. Run Screener
        picks = self.screener.get_active_assets(limit=2)
        
        # JNJ should be #1 due to the 1.5x Multiplier
        self.assertEqual(picks[0], "JNJ")
        self.assertEqual(picks[1], "AAPL")

if __name__ == '__main__':
    unittest.main()
