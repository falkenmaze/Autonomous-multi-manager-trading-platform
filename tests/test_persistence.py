
import unittest
import os
import shutil
import pickle
from strategy.ensemble_strategy import SafeRLAgent, EnsembleStrategy
import pandas as pd
import numpy as np

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # clean up models dir
        if os.path.exists("models"):
            shutil.rmtree("models")
        os.makedirs("models")
        
    def tearDown(self):
        if os.path.exists("models"):
            shutil.rmtree("models")

    def test_rl_persistence(self):
        # 1. Create agent, learn something
        agent1 = SafeRLAgent("TEST_RL")
        agent1.last_state = (1, 1) # Normal RSI, Uptrend
        agent1.update(1.0) # Reward +1
        
        # Verify it learned (Q-value should not be 0)
        q_val1 = agent1.q_table[(1, 1)]
        self.assertNotEqual(q_val1, 0.0)
        
        # 2. Agent should have saved automatically on update.
        # Check file exists
        self.assertTrue(os.path.exists("models/TEST_RL_qtable.pkl"))
        
        # 3. Create NEW agent (simulate restart)
        agent2 = SafeRLAgent("TEST_RL")
        
        # 4. Verify memory
        q_val2 = agent2.q_table.get((1, 1), 0.0)
        self.assertEqual(q_val1, q_val2)
        print(f"RL Memory Verified: {q_val1} == {q_val2}")

    def test_rf_persistence(self):
        # 1. Create Strategy, Train RF
        strat1 = EnsembleStrategy("TEST_RF")
        
        # Fake data
        df = pd.DataFrame({
            'high': np.random.randn(200) + 100, 
            'low': np.random.randn(200) + 90, 
            'close': np.random.randn(200) + 95, 
            'open': np.random.randn(200) + 95, 
            'volume': np.random.randint(100, 1000, 200)
        })
        strat1.train_rf(df)
        self.assertTrue(strat1.is_trained)
        self.assertTrue(os.path.exists("models/TEST_RF_rf.pkl"))
        
        # 2. Create NEW Strategy (Simulate restart)
        strat2 = EnsembleStrategy("TEST_RF")
        
        # 3. Verify it loaded the model
        self.assertTrue(strat2.is_trained)
        self.assertIsNotNone(strat2.rf)
        print("RF Memory Verified: Model loaded successfully.")

if __name__ == '__main__':
    unittest.main()
