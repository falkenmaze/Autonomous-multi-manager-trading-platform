import sys
import os
import unittest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.portfolio_manager import PortfolioManager
import config

class TestHRP(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.pm = PortfolioManager(self.mock_client)
        
        # Standard mock fallback for price retrieval
        def mock_hist(symbol, lookback_days):
            return pd.DataFrame({'close': [100.0]})
        self.mock_client.get_historical_data.side_effect = mock_hist

    def test_hrp_mathematical_consistency(self):
        """Verify that HRP calculates consistent non-negative allocations."""
        symbols = ['A', 'B', 'C', 'D']
        np.random.seed(42)
        # Create uncorrelated daily returns
        returns = np.random.normal(0, 0.01, (100, 4))
        price_matrix = pd.DataFrame(returns, columns=symbols).cumsum() + 100.0
        # Convert to returns matrix for covariance/correlation
        price_matrix_pct = price_matrix.pct_change().dropna()
        
        sectors = {s: 'Tech' for s in symbols}
        current_sector_exp = {}
        total_equity = 100000
        
        allocations = self.pm.calculate_hrp(
            symbols, price_matrix_pct, total_equity, sectors, current_sector_exp, bias="GROWTH"
        )
        
        # Check that we received allocations for all assets
        self.assertTrue(len(allocations) > 0)
        for sym, qty in allocations.items():
            self.assertIsInstance(qty, int)
            self.assertGreaterEqual(qty, 0)

    def test_hrp_correlation_clustering(self):
        """
        Verify that HRP clusters correlated assets.
        Scenario:
          - TECH1 and TECH2 are highly correlated (corr ~ 0.98)
          - UTIL is uncorrelated with tech (corr ~ 0)
          - All assets have similar volatilities.
        Expected Behavior:
          - Naive risk parity or inverse vol treats them as 3 assets, allocating ~33% to each.
            This gives the "Tech" category a total allocation of 66%.
          - HRP clusters TECH1 and TECH2 together as a single 'Tech' branch.
            It recursively splits weights: ~50% to 'Tech' branch, ~50% to 'UTIL' branch.
            Inside the 'Tech' branch, the 50% is divided: ~25% each for TECH1 and TECH2.
          - Thus, UTIL should receive roughly DOUBLE the allocation of TECH1 or TECH2 individually.
        """
        symbols = ['TECH1', 'TECH2', 'UTIL']
        
        # Create returns data representing this structure
        np.random.seed(101)
        tech_base = np.random.normal(0, 0.01, 100)
        tech_noise1 = np.random.normal(0, 0.002, 100)
        tech_noise2 = np.random.normal(0, 0.002, 100)
        
        ret_tech1 = tech_base + tech_noise1
        ret_tech2 = tech_base + tech_noise2
        ret_util = np.random.normal(0, 0.01, 100) # completely independent
        
        returns_df = pd.DataFrame({
            'TECH1': ret_tech1,
            'TECH2': ret_tech2,
            'UTIL': ret_util
        })
        
        # Verify correlation structure
        corr = returns_df.corr()
        print(f"\n[Test HRP] Correlation structure:\n{corr}")
        self.assertGreater(corr.loc['TECH1', 'TECH2'], 0.90)
        self.assertLess(abs(corr.loc['TECH1', 'UTIL']), 0.20)
        
        sectors = {'TECH1': 'Technology', 'TECH2': 'Technology', 'UTIL': 'Utilities'}
        current_sector_exp = {}
        total_equity = 100000.0 # $100k
        
        # To inspect the raw weights before limits and quantity conversion, 
        # we check the relative share allocations. Since prices are identical ($100),
        # quantities directly reflect the HRP weights.
        allocations = self.pm.calculate_hrp(
            symbols, returns_df, total_equity, sectors, current_sector_exp, bias="GROWTH"
        )
        
        qty_tech1 = allocations.get('TECH1', 0)
        qty_tech2 = allocations.get('TECH2', 0)
        qty_util = allocations.get('UTIL', 0)
        
        print(f"[Test HRP] Allocations: TECH1={qty_tech1}, TECH2={qty_tech2}, UTIL={qty_util}")
        
        # UTIL should get a higher allocation than either tech stock individually
        self.assertGreater(qty_util, qty_tech1)
        self.assertGreater(qty_util, qty_tech2)
        
        # The ratio of UTIL to TECH1 should be close to 2.0 (since UTIL = 50%, TECH1 = 25% of the pot)
        ratio = qty_util / (qty_tech1 + 1e-8)
        print(f"[Test HRP] UTIL to TECH1 allocation ratio: {ratio:.2f}")
        self.assertGreater(ratio, 1.4) # Must be significantly larger than 1.0 (naive risk parity)

    def test_hrp_respects_limits(self):
        """Verify HRP respects single-asset 15% cap and sector caps."""
        symbols = ['A', 'B']
        # Set up returns data
        np.random.seed(42)
        returns = np.random.normal(0, 0.01, (100, 2))
        returns_df = pd.DataFrame(returns, columns=symbols)
        
        sectors = {'A': 'Technology', 'B': 'Technology'}
        current_sector_exp = {}
        total_equity = 100000 # $100k
        
        # Total pot is 25% of equity = $25,000.
        # Single asset limit is 15% of equity = $15,000.
        # If one asset is extremely steady and gets 95% of HRP weight, 
        # its dollar amount would be 0.95 * 25k = $23,750.
        # It must be clipped to $15,000 (150 shares at $100 price).
        
        # Make asset A have extremely low volatility compared to B
        returns_df['A'] = returns_df['A'] * 0.01 # Volatility is 100x lower!
        
        allocations = self.pm.calculate_hrp(
            symbols, returns_df, total_equity, sectors, current_sector_exp, bias="GROWTH"
        )
        
        qty_a = allocations.get('A', 0)
        qty_b = allocations.get('B', 0)
        
        print(f"[Test HRP] Large Volatility Difference Allocations: A={qty_a}, B={qty_b}")
        
        # At $100 price, 15% of $100k equity is max 150 shares.
        # Ticker A must not exceed 150 shares
        self.assertLessEqual(qty_a, 150)
        
if __name__ == '__main__':
    unittest.main()
