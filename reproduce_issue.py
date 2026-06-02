
import requests
import time
from bs4 import BeautifulSoup

def test_connection():
    base_url = "http://openinsider.com/screener"
    ticker = "AAPL"
    url = f"{base_url}?s={ticker}"
    
    print(f"Testing connection to {url}...")
    
    # Test 1: Original Logic (No Headers)
    print("\n--- Test 1: Original Logic ---")
    try:
        start_time = time.time()
        response = requests.get(url, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Time taken: {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: With User-Agent Header
    print("\n--- Test 2: With User-Agent Header ---")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=20)
        print(f"Status Code: {response.status_code}")
        print(f"Time taken: {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_connection()
