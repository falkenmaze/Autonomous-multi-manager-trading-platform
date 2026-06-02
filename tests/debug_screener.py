
from trading.alpaca_client import AlpacaClient
from trading.screener import MarketScreener
import config_tickers

print("Initializing Client...")
client = AlpacaClient()

print(f"Scanning {len(config_tickers.SP100_TICKERS)} tickers...")

from alpaca.data.requests import StockSnapshotRequest
request = StockSnapshotRequest(symbol_or_symbols=config_tickers.SP100_TICKERS)
snapshots = client.data_client.get_stock_snapshot(request)

print("\n--- SCREENER DIAGNOSTICS ---")
print(f"{'SYMBOL':<6} | {'PRICE':<8} | {'VOLUME':<12} | {'CHANGE%':<8} | {'STATUS'}")
print("-" * 60)

count_pass = 0
for symbol, snapshot in snapshots.items():
    price = snapshot.latest_trade.price
    day_close = snapshot.daily_bar.close
    day_open = snapshot.daily_bar.open
    
    # Handle division by zero or None
    if day_open and day_open > 0:
        day_change = day_close - day_open
        pct_change = (day_change / day_open) * 100
    else:
        pct_change = 0.0

    volume = snapshot.daily_bar.volume
    
    status = "✅ PASS"
    reasons = []
    
    if price < 10.0:
        status = "❌ FAIL"
        reasons.append("Price < 10")
        
    if volume < 1_000_000:
        status = "❌ FAIL"
        reasons.append("Vol < 1M")
        
    if status == "✅ PASS":
        count_pass += 1
        
    print(f"{symbol:<6} | ${price:<7.2f} | {volume:<12} | {pct_change:<7.2f}% | {status} {', '.join(reasons)}")

print(f"\nTotal Passing: {count_pass}/{len(snapshots)}")
