import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.ai_strategy import AIStrategy
import config

def test_training_loop():
    print("Testing Training Loop...")
    
    # generate synthetic data
    dates = pd.date_range(start='2024-01-01', periods=3000, freq='1min')
    df = pd.DataFrame(index=dates)
    df['close'] = np.random.randn(3000).cumsum() + 100
    df['volume'] = np.random.randint(100, 1000, 3000)
    
    # Initialize Strategy
    strategy = AIStrategy("TEST")
    
    # Run Train
    try:
        success = strategy.train(df)
        if success:
            print("Training completed successfully!")
        else:
            print("Training returned False.")
    except Exception as e:
        print(f"Training crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_training_loop()
