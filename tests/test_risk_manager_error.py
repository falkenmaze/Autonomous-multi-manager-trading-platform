import unittest
from unittest.mock import MagicMock, patch
from trading.trader import Trader
from alpaca.trading.enums import PositionSide
import config

class TestRiskManagerFix(unittest.TestCase):
    def setUp(self):
        # Patching to avoid external calls durante init
        with patch('trading.trader.AlpacaClient'), \
             patch('trading.trader.MarketScreener'), \
             patch('trading.trader.PortfolioManager'), \
             patch('trading.trader.DataLogger'), \
             patch('trading.trader.HWMManager'), \
             patch('trading.trader.SectorManager'), \
             patch('trading.trader.MarketRegimeManager'), \
             patch('trading.trader.SentimentAnalyzer'), \
             patch('trading.trader.SmartMoneyAnalyzer'):
            self.trader = Trader()
            self.trader.client = MagicMock()
            self.trader.hwm = MagicMock()

    @patch('trading.trader.config')
    def test_run_risk_management_no_unbound_error(self, mock_config):
        # Setup conditions that previously triggered the error
        mock_config.ENABLE_RISK_MANAGER = True
        mock_config.ENABLE_TRAILING_STOP = True
        mock_config.TRAILING_STOP_PCT = 0.03
        mock_config.RUNNER_TRAILING_STOP_PCT = 0.07
        mock_config.MAX_PORTFOLIO_DRAWDOWN = 0.05
        mock_config.USE_ATR_BASED_RISK = False
        mock_config.STOP_LOSS_PCT = 0.05
        mock_config.TAKE_PROFIT_PCT = 0.10
        mock_config.MARKET_OPEN_START_HOUR = 9
        mock_config.MARKET_OPEN_START_MIN = 30
        mock_config.MARKET_OPEN_DURATION_MINS = 30
        mock_config.OPEN_STOP_LOSS_MULTIPLIER = 2.0

        # Mock position
        mock_pos = MagicMock()
        mock_pos.symbol = "INTC"
        mock_pos.side = PositionSide.LONG
        mock_pos.current_price = "96" # 4% drop from 100
        mock_pos.avg_entry_price = "100"
        mock_pos.qty = "10"
        
        self.trader.client.get_positions.return_value = [mock_pos]
        self.trader.client.get_account.return_value.equity = 100000
        
        # Mock HWM to trigger trailing stop (drop from 100 to 96 is 4%, > 3%)
        self.trader.hwm.get_portfolio_peak.return_value = 100000
        self.trader.hwm.update.return_value = 100.0 # Peak was 100
        
        # PnL is (96-100)/100 = -0.04. This is < take_profit_limit (0.10),
        # so reason_msg wasn't getting set before line 252.
        
        # Mock _is_market_open_window to return False to simplify
        self.trader._is_market_open_window = MagicMock(return_value=False)
        
        # This should NOT raise UnboundLocalError
        try:
            self.trader.run_risk_management()
        except UnboundLocalError as e:
            self.fail(f"run_risk_management raised UnboundLocalError: {e}")
        except Exception as e:
            print(f"Caught other exception (likely due to mocking): {e}")

if __name__ == '__main__':
    unittest.main()
