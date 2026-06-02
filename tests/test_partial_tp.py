
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from trading.trader import Trader

class TestPartialTP(unittest.TestCase):
    def setUp(self):
        with patch('trading.alpaca_client.AlpacaClient'), \
             patch('trading.sector_manager.SectorManager'), \
             patch('trading.market_regime.MarketRegimeManager'), \
             patch('strategy.sentiment_analyzer.SentimentAnalyzer'), \
             patch('strategy.smart_money_analyzer.SmartMoneyAnalyzer'), \
             patch('trading.screener.MarketScreener'), \
             patch('trading.portfolio_manager.PortfolioManager'), \
             patch('trading.data_logger.DataLogger'), \
             patch('trading.hwm_manager.HWMManager'):
            self.trader = Trader()

    def test_partial_tp_logic(self):
        # Mock position
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = "100"
        mock_pos.current_price = "110" # 10% gain
        mock_pos.avg_entry_price = "100"
        mock_pos.side = MagicMock()
        from alpaca.trading.enums import PositionSide
        mock_pos.side = PositionSide.LONG

        self.trader.client.get_positions.return_value = [mock_pos]
        self.trader.client.get_account.return_value = MagicMock(equity=100000)
        
        # Test: If PnL > TP limit and Partial TP is enabled
        with patch('config.ENABLE_PARTIAL_TP', True), \
             patch('config.PARTIAL_TP_PCT', 0.5), \
             patch('config.TAKE_PROFIT_PCT', 0.05): # Target reached
            
            # This should call close_position with 50 shares
            self.trader.run_risk_management()
            
            # Check if partial close was attempted
            # Note: Trader calls self.client.trading_client.close_position(symbol, close_options={'qty': str(qty_to_close)})
            self.trader.client.trading_client.close_position.assert_called_with("AAPL", close_options={'qty': '50'})

if __name__ == "__main__":
    unittest.main()
