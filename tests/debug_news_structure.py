
from trading.alpaca_client import AlpacaClient
import json

print("Fetching news for AAPL...")
client = AlpacaClient()
news_list = client.get_company_news("AAPL", lookback_days=1)

print(f"Type of news_list: {type(news_list)}")
if news_list and len(news_list) > 0:
    first_item = news_list[0]
    print(f"Type of first item: {type(first_item)}")
    print(f"First item content: {first_item}")
    
    if hasattr(first_item, '__dict__'):
        print("Attributes:", dir(first_item))
else:
    print("No news found.")
