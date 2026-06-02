
from trading.alpaca_client import AlpacaClient

client = AlpacaClient()
print("Fetching news for AAPL...")
response = client.get_company_news("AAPL", lookback_days=3)

print(f"Original Response Type: {type(response)}")

if hasattr(response, 'news'):
    news_content = response.news
    print(f"Response.news Type: {type(news_content)}")
    print(f"Is list? {isinstance(news_content, list)}")
    print(f"Length: {len(news_content) if hasattr(news_content, '__len__') else 'N/A'}")
    if len(news_content) > 0:
        print(f"First item: {news_content[0]}")
else:
    print("Response has no .news attribute!")
