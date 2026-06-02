import unittest
from unittest.mock import MagicMock, patch
from trading.macro_manager import MacroManager
import pandas as pd

class TestMacroExpansionLogic(unittest.TestCase):
    def setUp(self):
        self.macro = MacroManager()

    @patch('yfinance.download')
    def test_calculate_macro_bias_defensive_yield(self, mock_yf):
        # Simulate Inverted Yield Curve (Spread < -0.2)
        # 1. 10Y, 2. 3M, 3. ETFs
        mock_yf.side_effect = [
            pd.DataFrame({'Close': [4.0]}), # 10Y
            pd.DataFrame({'Close': [4.5]}), # 3M
            pd.DataFrame(
                [[100, 100, 100]]*14, 
                columns=pd.MultiIndex.from_tuples([('Close', 'HYG'), ('Close', 'IEF'), ('Close', 'TIP')])
            )
        ]
        
        status = self.macro.fetch_yields()
        self.assertEqual(status['bias'], "DEFENSIVE")

    @patch('yfinance.download')
    def test_calculate_macro_bias_defensive_credit(self, mock_yf):
        # Simulate Normal Yield but Tightening Credit (HYG underperforms IEF)
        # HYG drops 5%, IEF stays flat over 10 days
        hyg_data = [100.0]*10 + [95.0]*4 # 5% drop
        ief_data = [100.0]*14
        tip_data = [100.0]*14
        
        # Create MultiIndex DF
        etf_df = pd.DataFrame(
            list(zip(hyg_data, ief_data, tip_data)),
            columns=pd.MultiIndex.from_tuples([('Close', 'HYG'), ('Close', 'IEF'), ('Close', 'TIP')])
        )

        mock_yf.side_effect = [
            pd.DataFrame({'Close': [4.5]}), # 10Y
            pd.DataFrame({'Close': [4.0]}), # 3M
            etf_df
        ]
        
        status = self.macro.fetch_yields()
        self.assertEqual(status['bias'], "DEFENSIVE")

    @patch('yfinance.download')
    def test_calculate_macro_bias_inflationary(self, mock_yf):
        # Simulate Normal Yield/Credit but Inflation Pulse (TIP outperforming IEF)
        tip_data = [100.0]*10 + [103.0]*4
        hyg_data = [100.0]*14
        ief_data = [100.0]*14
        
        etf_df = pd.DataFrame(
            list(zip(hyg_data, ief_data, tip_data)),
            columns=pd.MultiIndex.from_tuples([('Close', 'HYG'), ('Close', 'IEF'), ('Close', 'TIP')])
        )

        mock_yf.side_effect = [
            pd.DataFrame({'Close': [4.5]}), # 10Y
            pd.DataFrame({'Close': [4.0]}), # 3M
            etf_df
        ]
        
        status = self.macro.fetch_yields()
        self.assertEqual(status['bias'], "INFLATIONARY")

    @patch('yfinance.download')
    def test_calculate_macro_bias_growth(self, mock_yf):
        # Everything stable/normal
        mock_yf.side_effect = [
            pd.DataFrame({'Close': [4.5]}), # 10Y
            pd.DataFrame({'Close': [4.0]}), # 3M
            pd.DataFrame(
                [[100, 100, 100]]*14, 
                columns=pd.MultiIndex.from_tuples([('Close', 'HYG'), ('Close', 'IEF'), ('Close', 'TIP')])
            )
        ]
        
        status = self.macro.fetch_yields()
        self.assertEqual(status['bias'], "GROWTH")

if __name__ == '__main__':
    unittest.main()
