import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.trader import Trader
import config

class TestCircuitBreaker(unittest.TestCase):
    
    @patch('trading.trader.AlpacaClient')
    @patch('trading.trader.DataLogger')
    @patch('trading.trader.HWMManager')
    def test_circuit_breaker_trigger(self, mock_hwm_class, mock_logger_class, mock_client_class):
        """Verify that a 6% drawdown triggers lockdown and liquidates."""
        
        # Setup mocks
        mock_client = mock_client_class.return_value
        mock_hwm = mock_hwm_class.return_value
        
        # Mock account with $100k equity
        mock_account = MagicMock()
        mock_account.equity = "100000"
        mock_client.get_account.return_value = mock_account
        
        # Mock HWM to return $110k (peak), making current $100k a >5% drawdown
        # (100 - 110) / 110 = -9.09%
        mock_hwm.get_portfolio_peak.return_value = 110000
        
        # Mock positions
        p1 = MagicMock(symbol="AAPL")
        mock_client.get_positions.return_value = [p1]
        
        # Initialize Trader
        trader = Trader()
        trader.hwm = mock_hwm
        trader.client = mock_client
        
        # Run risk management
        closed_symbols = trader.run_risk_management()
        
        # Assertions
        self.assertTrue(trader.lockdown)
        self.assertIn("AAPL", closed_symbols)
        mock_client.close_position.assert_called_with("AAPL")
        
    @patch('trading.trader.AlpacaClient')
    @patch('trading.trader.DataLogger')
    @patch('trading.trader.HWMManager')
    def test_lockdown_skips_cycle(self, mock_hwm_class, mock_logger_class, mock_client_class):
        """Verify that trading cycle is skipped when in lockdown."""
        trader = Trader()
        trader.lockdown = True
        
        # Mock analyze method to ensure it's NOT called
        trader.run_daily_scan = MagicMock()
        
        with patch('builtins.print') as mock_print:
            trader.run_trading_cycle()
            # Look for the lockdown message
            has_lockdown_msg = any("LOCKDOWN MODE" in str(call) for call in mock_print.call_args_list)
            self.assertTrue(has_lockdown_msg)
            
        trader.run_daily_scan.assert_not_called()

if __name__ == '__main__':
    unittest.main()
