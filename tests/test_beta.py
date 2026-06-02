
import unittest
from unittest.mock import MagicMock
import pandas as pd
import numpy as np
from trading.portfolio_manager import PortfolioManager
from trading.alpaca_client import AlpacaClient

class TestDynamicBeta(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=AlpacaClient)
        self.pm = PortfolioManager(self.mock_client)
        
    def create_mock_history(self, start_price, volatility, trend, length=100):
        """Generates random price history"""
        prices = [start_price]
        for i in range(1, length):
            change = np.random.normal(trend, volatility)
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
            
        # Create timestamps
        dates = pd.date_range(end=pd.Timestamp.now(), periods=length)
        
        return pd.DataFrame({
            'close': prices,
            'open': prices,
            'high': prices,
            'low': prices,
            'volume': [1000]*length
        }, index=dates)

    def test_real_time_beta_calculation(self):
        # Helper to create MultiIndex DF
        def to_multi_index(df, symbol):
            df['symbol'] = symbol
            return df.set_index(['symbol', df.index])

        # 1. Create SPY Data (The Market)
        np.random.seed(42)
        spy_returns = np.random.normal(0.01, 0.01, 100)
        spy_prices = 100 * (1 + spy_returns).cumprod()
        spy_df = pd.DataFrame({'close': spy_prices}, index=pd.date_range(end=pd.Timestamp.now(), periods=100))
        spy_df = to_multi_index(spy_df, 'SPY')
        
        # 2. Create High Beta Data (2x SPY)
        high_beta_returns = (2.0 * spy_returns) + np.random.normal(0, 0.001, 100)
        high_beta_prices = 100 * (1 + high_beta_returns).cumprod()
        high_beta_df = pd.DataFrame({'close': high_beta_prices}, index=pd.date_range(end=pd.Timestamp.now(), periods=100))
        high_beta_df = to_multi_index(high_beta_df, 'HIGH_BETA')
        
        # 3. Create Negative Beta Data (-1x SPY)
        inverse_returns = (-1.0 * spy_returns) + np.random.normal(0, 0.001, 100)
        inverse_prices = 100 * (1 + inverse_returns).cumprod()
        inverse_df = pd.DataFrame({'close': inverse_prices}, index=pd.date_range(end=pd.Timestamp.now(), periods=100))
        inverse_df = to_multi_index(inverse_df, 'NEG_BETA')
        
        # Mock the client returns
        def get_hist_side_effect(symbol, lookback_days=180):
            if symbol == 'SPY': return spy_df
            if symbol == 'HIGH_BETA': return high_beta_df
            if symbol == 'NEG_BETA': return inverse_df
            return pd.DataFrame()
            
        self.mock_client.get_historical_data.side_effect = get_hist_side_effect
        
        # Test High Beta
        beta_high = self.pm.get_real_time_beta("HIGH_BETA")
        print(f"Calculated High Beta: {beta_high}")
        self.assertAlmostEqual(beta_high, 2.0, delta=0.2)
        
        # Test Negative Beta
        beta_neg = self.pm.get_real_time_beta("NEG_BETA")
        print(f"Calculated Negative Beta: {beta_neg}")
        self.assertAlmostEqual(beta_neg, -1.0, delta=0.2)
        
        # Test Caching: Client should not be called again for HIGH_BETA
        self.mock_client.get_historical_data.reset_mock()
        self.pm.get_real_time_beta("HIGH_BETA")
        self.mock_client.get_historical_data.assert_not_called()

    def test_portfolio_beta_aggregation(self):
        # Mock get_real_time_beta to return static values for testing aggregation
        self.pm.get_real_time_beta = MagicMock()
        self.pm.get_real_time_beta.side_effect = lambda sym: 2.0 if sym == 'A' else 1.0
        
        # Portfolio:
        # Asset A: $1000, Beta 2.0 -> Weighted: 2000
        # Asset B: $1000, Beta 1.0 -> Weighted: 1000
        # Total Value: 2000
        # Expected Portfolio Beta: 3000 / 2000 = 1.5
        
        p1 = MagicMock(symbol='A', qty=10, current_price=100)
        p2 = MagicMock(symbol='B', qty=10, current_price=100)
        
        beta, value = self.pm.calculate_portfolio_beta([p1, p2])
        
        self.assertEqual(value, 2000)
        self.assertEqual(beta, 1.5)

if __name__ == '__main__':
    unittest.main()
