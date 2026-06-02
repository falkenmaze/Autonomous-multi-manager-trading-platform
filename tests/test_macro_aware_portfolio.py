import unittest
from unittest.mock import MagicMock, patch
from trading.portfolio_manager import PortfolioManager
from trading.alpaca_client import AlpacaClient
import pandas as pd
import numpy as np

class TestMacroAwarePortfolio(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock(spec=AlpacaClient)
        self.sector_manager = MagicMock()
        self.macro = MagicMock()
        self.pm = PortfolioManager(self.client, self.sector_manager, self.macro)

    def test_dynamic_sector_limits_defensive(self):
        # Defensive bias should boost Healthcare to 45% and limit Tech to 15%
        limit_hc = self.pm._get_dynamic_sector_limits("Healthcare", "DEFENSIVE")
        limit_tech = self.pm._get_dynamic_sector_limits("Technology", "DEFENSIVE")
        
        self.assertEqual(limit_hc, 0.45)
        self.assertEqual(limit_tech, 0.15)

    def test_dynamic_sector_limits_growth(self):
        # Growth bias should use default 30% for both
        limit_hc = self.pm._get_dynamic_sector_limits("Healthcare", "GROWTH")
        limit_tech = self.pm._get_dynamic_sector_limits("Technology", "GROWTH")
        
        self.assertEqual(limit_hc, 0.30)
        self.assertEqual(limit_tech, 0.30)

    @patch('trading.portfolio_manager.minimize')
    def test_optimize_allocations_respects_macro_limits(self, mock_minimize):
        # Mocking the optimizer result to focus on constraint setup
        mock_minimize.return_value.x = np.array([0.5, 0.5])
        
        self.macro.get_market_bias.return_value = "DEFENSIVE"
        self.client.get_positions.return_value = [] # No existing positions
        
        # Two mock assets
        potential_buys = ['JNJ', 'AAPL']
        self.sector_manager.get_sector.side_effect = lambda sym: "Healthcare" if sym == 'JNJ' else "Technology"
        
        # Mock historical data for returns matrix
        df = pd.DataFrame({'close': [100]*90})
        self.client.get_historical_data.return_value = df
        
        self.pm.optimize_allocations(potential_buys, 100000)
        
        # Verify that constraints were added
        args, kwargs = mock_minimize.call_args
        constraints = kwargs['constraints']
        
        # We expect 1 equality (sum weights = 1) and 2 inequality (sector limits)
        self.assertEqual(len(constraints), 3)

if __name__ == '__main__':
    unittest.main()
