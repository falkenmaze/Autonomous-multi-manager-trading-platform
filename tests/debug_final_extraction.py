
from trading.alpaca_client import AlpacaClient
import json

client = AlpacaClient()
symbol = "INTC"
print(f"Fetching news for {symbol}...")
response = client.get_company_news(symbol, lookback_days=7) # Increase lookback to be sure

print(f"Response Type: {type(response)}")

# Method 1: .news attribute
if hasattr(response, 'news'):
    print("Method 1 (.news): SUCCESS")
    print(f"Count: {len(response.news)}")
else:
    print("Method 1 (.news): FAILED")

# Method 2: dict() conversion
try:
    as_dict = dict(response)
    if 'news' in as_dict:
        print("Method 2 (dict conversion): SUCCESS")
        print(f"Count: {len(as_dict['news'])}")
    else:
        print("Method 2 (dict conversion): FAILED (no 'news' key)")
except Exception as e:
    print(f"Method 2 (dict conversion): FAILED (Error: {e})")

# Method 3: Direct Iteration
print("Method 3 (Iteration):")
try:
    for i, item in enumerate(response):
        print(f"  Item {i}: {type(item)} - {item}")
        if i > 1: break
except Exception as e:
    print(f"  Iteration failed: {e}")
