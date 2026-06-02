import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.ensemble_strategy import EnsembleStrategy
import pandas as pd

class TestEarningsAwareness(unittest.TestCase):
    
    @patch('strategy.ensemble_strategy.EventManager')
    @patch('strategy.ensemble_strategy.MonteCarloStrategy')
    @patch('strategy.ensemble_strategy.SafeRLAgent')
    def test_earnings_veto(self, mock_rl_class, mock_mc_class, mock_event_class):
        """Verify that being near earnings triggers a 'hold' veto."""
        
        # Setup mocks
        mock_event = mock_event_class.return_value
        # Simulate earnings tomorrow
        earnings_date = datetime.now() + timedelta(days=1)
        mock_event.is_near_earnings.return_value = (True, earnings_date)
        
        # Strategy setup
        strategy = EnsembleStrategy("AAPL")
        strategy.events = mock_event # Ensure it uses our mock
        strategy.mc.run_simulation = MagicMock(return_value=0.5)
        strategy.is_trained = True
        strategy.rf.predict_proba = MagicMock(return_value=[[0.5, 0.5]])
        strategy.rl.get_adjustment = MagicMock(return_value=0.0)
        
        # Create dummy DF
        df = pd.DataFrame({'close': [100.0]*50, 'high': [101.0]*50, 'low': [99.0]*50, 'volume': [1000]*50})
        
        # Run analysis (VIX doesn't matter for the veto)
        action, prob, reason, news = strategy.analyze(df)
        
        # Assertions
        self.assertEqual(action, 'hold')
        self.assertIn("EARNINGS", reason)
        self.assertIn("VETO", reason)

if __name__ == '__main__':
    unittest.main()
