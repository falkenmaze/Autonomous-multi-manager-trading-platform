
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from trading.trader import Trader

class TestDynamicTP(unittest.TestCase):
    def setUp(self):
        # Patch where they are USED (in trading.trader)
        with patch('trading.trader.AlpacaClient'), \
             patch('trading.trader.SectorManager'), \
             patch('trading.trader.MarketRegimeManager'), \
             patch('trading.trader.SentimentAnalyzer'), \
             patch('trading.trader.SmartMoneyAnalyzer'), \
             patch('trading.trader.MarketScreener'), \
             patch('trading.trader.PortfolioManager'), \
             patch('trading.trader.DataLogger'), \
             patch('trading.trader.HWMManager'):
            self.trader = Trader()

    def test_dynamic_tp_low_vix(self):
        # Mock VIX = 10 (Low) -> Should sell 30%
        self.trader.regime_manager.get_vix.return_value = 10.0
        
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = "100"
        mock_pos.current_price = "110"
        mock_pos.avg_entry_price = "100"
        from alpaca.trading.enums import PositionSide
        mock_pos.side = PositionSide.LONG

        self.trader.client.get_positions.return_value = [mock_pos]
        self.trader.client.get_account.return_value = MagicMock(equity=100000.0)
        self.trader.hwm.get_portfolio_peak.return_value = 100000.0
        
        with patch('config.ENABLE_PARTIAL_TP', True), \
             patch('config.TAKE_PROFIT_PCT', 0.05):
            
            self.trader.run_risk_management()
            # 30% of 100 = 30
            self.trader.client.trading_client.close_position.assert_called_with("AAPL", close_options={'qty': '30'})

    def test_dynamic_tp_high_vix(self):
        # Mock VIX = 30 (High) -> Should sell 75%
        self.trader.regime_manager.get_vix.return_value = 30.0
        
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = "100"
        mock_pos.current_price = "110"
        mock_pos.avg_entry_price = "100"
        from alpaca.trading.enums import PositionSide
        mock_pos.side = PositionSide.LONG

        self.trader.client.get_positions.return_value = [mock_pos]
        self.trader.client.get_account.return_value = MagicMock(equity=100000.0)
        self.trader.hwm.get_portfolio_peak.return_value = 100000.0
        
        with patch('config.ENABLE_PARTIAL_TP', True), \
             patch('config.TAKE_PROFIT_PCT', 0.05):
            
            self.trader.run_risk_management()
            # 75% of 100 = 75
            self.trader.client.trading_client.close_position.assert_called_with("AAPL", close_options={'qty': '75'})

if __name__ == "__main__":
    unittest.main()
