
from trading.alpaca_client import AlpacaClient

print("Fetching news for AAPL...")
client = AlpacaClient()
news_set = client.get_company_news("AAPL", lookback_days=1)

print(f"Type of returned object: {type(news_set)}")
print(f"Attributes of object: {[x for x in dir(news_set) if not x.startswith('_')]}")

# try iterating
print("\nIterating over object:")
try:
    for i, item in enumerate(news_set):
        print(f"Item {i} type: {type(item)}")
        print(f"Item {i} content: {item}")
        if i >= 0: break
except Exception as e:
    print(f"Iteration error: {e}")

# Check .news attribute if it exists
if hasattr(news_set, 'news'):
    print(f"\nChecking .news attribute type: {type(news_set.news)}")
    if isinstance(news_set.news, list) and len(news_set.news) > 0:
        first = news_set.news[0]
        print(f"First item in .news type: {type(first)}")
        print(f"First item attributes: {[x for x in dir(first) if not x.startswith('_')]}")
