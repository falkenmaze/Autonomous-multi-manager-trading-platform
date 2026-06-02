
import unittest
from unittest.mock import MagicMock
from trading.trader import Trader
from alpaca.trading.enums import PositionSide
import config
import pandas as pd
import numpy as np

# Fake Position Object
class MockPosition:
    def __init__(self, symbol, current_price, avg_entry_price, side=PositionSide.LONG):
        self.symbol = symbol
        self.current_price = str(current_price) 
        self.avg_entry_price = str(avg_entry_price)
        self.qty = "10" if side == PositionSide.LONG else "-10"
        self.side = side

class TestRiskManagement(unittest.TestCase):
    def setUp(self):
        # Ensure it is enabled
        config.ENABLE_RISK_MANAGER = True
        config.STOP_LOSS_PCT = 0.05
        config.TAKE_PROFIT_PCT = 0.10
        config.USE_ATR_BASED_RISK = True # Enable ATR
        config.ATR_MULTIPLIER_SL = 1.0 # Simple multiplier for easy math
        
        self.trader = Trader()
        self.trader.client = MagicMock()

    def create_mock_history(self, volatility_factor=1.0):
        # Create 30 days of data
        dates = pd.date_range(end=pd.Timestamp.now(), periods=30)
        # Base price 100
        # If High Vol, we want High-Low range to be large.
        # ATR ~ Average(High - Low)
        
        # Low Vol: High=101, Low=99 -> Range=2 -> ATR~2. (2% of 100)
        # High Vol: High=110, Low=90 -> Range=20 -> ATR~20. (20% of 100)
        
        spread = 2.0 * volatility_factor
        
        data = {
            'open': [100] * 30,
            'high': [100 + (spread/2)] * 30,
            'low': [100 - (spread/2)] * 30,
            'close': [100] * 30,
            'volume': [1000] * 30
        }
        df = pd.DataFrame(data, index=dates)
        return df

    def test_dynamic_stop_tight(self):
        # LOW VOLATILITY STOCK (ATR ~ 2%)
        # Config: SL Multiplier = 1.0 -> Dynamic SL = 2%.
        # Position is down 3%.
        # Static SL is 5%.
        # Expected: CLOSE (Dynamic 2% < 3% Loss)
        
        p1 = MockPosition("CALM_STOCK", 97, 100, PositionSide.LONG) # Down 3%
        self.trader.client.get_positions.return_value = [p1]
        
        # Mock History: Range=2 -> ATR=2
        df_low_vol = self.create_mock_history(volatility_factor=1.0) 
        self.trader.client.get_historical_data.return_value = df_low_vol
        
        closed = self.trader.run_risk_management()
        
        self.assertIn("CALM_STOCK", closed)

    def test_dynamic_stop_wide(self):
        # HIGH VOLATILITY STOCK (ATR ~ 10%)
        # Config: SL Multiplier = 1.0 -> Dynamic SL = 10%. (Capped at Max 10% in code, let's say 8%)
        # Let's set volatility factor = 3.0 -> Range=6 -> ATR=6.
        # Position is down 5.5%.
        # Static SL is 5%.
        # Expected: HOLD (Dynamic 6% > 5.5% Loss). The risk manager gives it room.
        
        p1 = MockPosition("WILD_STOCK", 94.5, 100, PositionSide.LONG) # Down 5.5%
        self.trader.client.get_positions.return_value = [p1]
        
        # Mock History: Range=6 -> ATR=6
        df_high_vol = self.create_mock_history(volatility_factor=3.0)
        self.trader.client.get_historical_data.return_value = df_high_vol
        
        closed = self.trader.run_risk_management()
        
        self.assertEqual(len(closed), 0) # Should hold

if __name__ == '__main__':
    unittest.main()
