
import unittest
from unittest.mock import MagicMock, patch
from trading.alpaca_client import AlpacaClient
from trading.trader import Trader
from alpaca.trading.enums import PositionSide
import config
import pandas as pd
import time

class TestResilience(unittest.TestCase):
    
    def test_retry_logic(self):
        """Test that client retries on connection error."""
        client = AlpacaClient()
        
        # Mock the trading_client.get_account method
        # First call raises ConnectionError, Second call succeeds
        client.trading_client.get_account = MagicMock(side_effect=[
            ConnectionError("Connection aborted."),
            MagicMock(equity="100000")
        ])
        
        # We need to mock time.sleep so the test doesn't actually wait
        with patch('time.sleep') as mock_sleep:
            account = client.get_account()
            
            # Should have called sleep once (after 1st failure)
            mock_sleep.assert_called_once() 
            # Should have called get_account twice
            self.assertEqual(client.trading_client.get_account.call_count, 2)
            self.assertEqual(account.equity, "100000")

    def test_atr_caching(self):
        """Test that ATR is requested once and then cached."""
        config.ENABLE_RISK_MANAGER = True
        config.USE_ATR_BASED_RISK = True
        
        trader = Trader()
        trader.client = MagicMock()
        
        # Fake Position
        p1 = MagicMock()
        p1.symbol = "TEST_CACHE"
        p1.current_price = "100"
        p1.avg_entry_price = "100"
        p1.side = PositionSide.LONG
        
        trader.client.get_positions.return_value = [p1]
        
        # Fake History
        df = pd.DataFrame({
            'high': [105]*20, 'low': [95]*20, 'close': [100]*20, 'open': [100]*20, 'volume': [100]*20
        })
        trader.client.get_historical_data.return_value = df
        
        # Run 1: Should fetch data
        trader.run_risk_management()
        self.assertEqual(trader.client.get_historical_data.call_count, 1)
        
        # Check if in cache
        self.assertIn("TEST_CACHE", trader.atr_cache)
        
        # Run 2: Should use cache (fetch count stays 1)
        trader.run_risk_management()
        self.assertEqual(trader.client.get_historical_data.call_count, 1)
        
        # Run 3: Clear cache to simulate expiry, should fetch again
        del trader.atr_cache["TEST_CACHE"]
        trader.run_risk_management()
        self.assertEqual(trader.client.get_historical_data.call_count, 2)

if __name__ == '__main__':
    unittest.main()
