
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytz
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from trading.trader import Trader

class TestMarketOpenLogic(unittest.TestCase):
    def setUp(self):
        # Mock dependencies to avoid network calls
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

    def test_is_market_open_window(self):
        tz = pytz.timezone("US/Eastern")
        
        # Case 1: Exactly at 9:30 AM
        open_time = datetime(2026, 2, 18, 9, 30, 0, tzinfo=tz)
        with patch('trading.trader.datetime') as mock_date:
            mock_date.now.return_value = open_time
            self.assertTrue(self.trader._is_market_open_window())

        # Case 2: At 9:45 AM (Inside)
        mid_time = datetime(2026, 2, 18, 9, 45, 0, tzinfo=tz)
        with patch('trading.trader.datetime') as mock_date:
            mock_date.now.return_value = mid_time
            self.assertTrue(self.trader._is_market_open_window())

        # Case 3: At 10:01 AM (Outside)
        late_time = datetime(2026, 2, 18, 10, 1, 0, tzinfo=tz)
        with patch('trading.trader.datetime') as mock_date:
            mock_date.now.return_value = late_time
            self.assertFalse(self.trader._is_market_open_window())

        # Case 4: At 9:00 AM (Before)
        early_time = datetime(2026, 2, 18, 9, 0, 0, tzinfo=tz)
        with patch('trading.trader.datetime') as mock_date:
            mock_date.now.return_value = early_time
            self.assertFalse(self.trader._is_market_open_window())

    def test_get_dynamic_risk_widens_at_open(self):
        tz = pytz.timezone("US/Eastern")
        open_time = datetime(2026, 2, 18, 9, 35, 0, tzinfo=tz)
        
        # ATR logic needs to be mocked or bypassed
        # Default stop loss is usually 0.05
        # With multiplier 2.0, should be 0.10
        with patch('trading.trader.datetime') as mock_date:
            mock_date.now.return_value = open_time
            # Keep ATR based risk FALSE to test base logic
            with patch('config.USE_ATR_BASED_RISK', False):
                sl, tp = self.trader._get_dynamic_risk("AAPL", 150.0)
                # config.STOP_LOSS_PCT is 0.05
                # Multiply by config.OPEN_STOP_LOSS_MULTIPLIER
                self.assertAlmostEqual(sl, 0.05 * config.OPEN_STOP_LOSS_MULTIPLIER)

    def test_normal_risk_outside_open(self):
        tz = pytz.timezone("US/Eastern")
        noon_time = datetime(2026, 2, 18, 12, 0, 0, tzinfo=tz)
        
        with patch('trading.trader.datetime') as mock_date:
            mock_date.now.return_value = noon_time
            with patch('config.USE_ATR_BASED_RISK', False):
                sl, tp = self.trader._get_dynamic_risk("AAPL", 150.0)
                self.assertAlmostEqual(sl, 0.05)

if __name__ == "__main__":
    unittest.main()
