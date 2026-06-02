import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from alpaca.trading.client import TradingClient

def test_connection():
    print("Testing connection to Alpaca...")
    try:
        trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)
        account = trading_client.get_account()
        print(f"SUCCESS! Connected to account #{account.account_number}")
        print(f"Cash Balance: ${account.cash}")
        print(f"Portfolio Value: ${account.portfolio_value}")
    except Exception as e:
        print(f"FAILED: {e}")
        print("Please check your .env file and ensure keys are correct.")

if __name__ == "__main__":
    test_connection()
