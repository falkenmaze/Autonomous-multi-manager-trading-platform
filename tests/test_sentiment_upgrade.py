
import sys
import os
import time

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategy.sentiment_analyzer import SentimentAnalyzer

def test_google_news_sentiment():
    print("=== Testing Google News Sentiment Upgrade ===")
    
    analyzer = SentimentAnalyzer()
    
    # Test symbols that usually have Tier 1 news
    symbols = ['TSLA', 'AAPL', 'NVDA']
    
    for symbol in symbols:
        print(f"\n--- Analyzing {symbol} ---")
        score = analyzer.analyze_sentiment(symbol)
        print(f"Result: {score:.4f}")
        
        if score != 0:
            print("✅ Successfully fetched and analyzed Tier 1 news.")
        else:
            print("⚠️ No Tier 1 news found (or neutral). This might be valid if no major news exists.")

if __name__ == "__main__":
    test_google_news_sentiment()
