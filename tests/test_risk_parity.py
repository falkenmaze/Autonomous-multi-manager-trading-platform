import sys
import os
import unittest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.portfolio_manager import PortfolioManager

class TestRiskParity(unittest.TestCase):
    
    def test_risk_parity_weights(self):
        """Verify weights are inversely proportional to volatility."""
        client = MagicMock()
        pm = PortfolioManager(client)
        
        # Setup test data
        symbols = ['LOW_VOL', 'HIGH_VOL']
        # HIGH_VOL is twice as volatile
        data = {
            'LOW_VOL':  [0.01, -0.01, 0.01, -0.01],
            'HIGH_VOL': [0.02, -0.02, 0.02, -0.02]
        }
        price_matrix = pd.DataFrame(data)
        
        total_equity = 100000
        sectors = {'LOW_VOL': 'Tech', 'HIGH_VOL': 'Finance'}
        current_sector_exp = {}
        
        # Mock client to return current prices
        def mock_hist(symbol, lookback_days):
            return pd.DataFrame({'close': [100]})
        client.get_historical_data.side_effect = mock_hist
        
        # Run Risk Parity
        allocations = pm.calculate_risk_parity(symbols, price_matrix, total_equity, sectors, current_sector_exp)
        
        # Check that LOW_VOL got more shares than HIGH_VOL
        # Since volatility is 1:2, weights should be 2:1
        # LOW_VOL weight ~ 0.66, HIGH_VOL weight ~ 0.33
        self.assertIn('LOW_VOL', allocations)
        self.assertIn('HIGH_VOL', allocations)
        self.assertGreater(allocations['LOW_VOL'], allocations['HIGH_VOL'])

if __name__ == '__main__':
    unittest.main()
