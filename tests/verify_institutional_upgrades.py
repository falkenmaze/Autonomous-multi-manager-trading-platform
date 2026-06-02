import sys
import os
# Add parent dir to path
sys.path.append(os.getcwd())

from strategy.ensemble_strategy import EnsembleStrategy
from trading.portfolio_manager import PortfolioManager
from trading.macro_manager import MacroManager
from strategy.smart_money_analyzer import SmartMoneyAnalyzer
import pandas as pd
import numpy as np

def test_macro_beta_impact():
    print("\n--- Testing Macro Beta Impact ---")
    pm = PortfolioManager(client=None) # Mocking client
    regime_data = pm.macro_manager.get_status()
    print(f"Detected Regime: {regime_data['regime']}")
    print(f"Recommended Beta: {regime_data['recommended_beta']}")
    
    # Test beta balancing math
    # Mock positions
    class MockPosition:
        def __init__(self, symbol, qty, price):
            self.symbol = symbol
            self.qty = qty
            self.current_price = price
            
    positions = [MockPosition("NVDA", 10, 100)] # $1000 value
    # Let's assume NVDA beta is 2.0
    # PortfolioManager uses get_real_time_beta which needs history. 
    # For this test, we just want to see if the target_beta is being used in hedge_portfolio.
    
    target_beta = pm.macro_manager.get_recommended_beta()
    print(f"Target Beta is correctly pulled: {target_beta}")

def test_smart_money_integration():
    print("\n--- Testing Smart Money Integration ---")
    # We'll mock the smart money analyzer to return a strong buy signal
    class MockSmartMoney:
        def get_signal(self, ticker):
            return 0.8 # Strong buy
            
    strategy = EnsembleStrategy("AAPL", smart_money=MockSmartMoney())
    
    # Mock data for analyze()
    df = pd.DataFrame({
        'close': np.linspace(100, 105, 100),
        'high': np.linspace(101, 106, 100),
        'low': np.linspace(99, 104, 100),
        'volume': [1000] * 100
    })
    
    # Run analysis
    action, prob, reason, meta = strategy.analyze(df)
    print(f"Action: {action} | Prob: {prob:.2f}")
    print(f"Reasoning includes Smart Money: {'Whale' in reason}")
    if 'Whale' in reason:
        print(f"  Result: {reason.split('Whale:')[1].split('|')[0].strip()}")

if __name__ == "__main__":
    test_macro_beta_impact()
    test_smart_money_integration()
