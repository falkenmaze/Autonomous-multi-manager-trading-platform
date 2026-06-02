
from trading.alpaca_client import AlpacaClient
from strategy.sentiment_analyzer import SentimentAnalyzer

print("--- Testing Sentiment Analyzer Live ---")
client = AlpacaClient()
analyzer = SentimentAnalyzer(client)

symbol = "AAPL"
print(f"Analyzing {symbol}...")
score = analyzer.analyze_sentiment(symbol)
print(f"Result: {score}")

if score == 0.0:
    print("WARNING: Score is 0.0. Check if news was found (enable verbose logs in analyzer if needed).")
else:
    print("SUCCESS: Non-zero sentiment score calculated.")
