
from trading.alpaca_client import AlpacaClient
import time

def debug_hedging():
    client = AlpacaClient()
    
    print("--- Diagnostic: Alpaca Connection ---")
    try:
        acct = client.get_account()
        print(f"Account Status: {acct.status}")
        print(f"Equity: ${acct.equity}")
        print(f"Buying Power: ${acct.buying_power}")
    except Exception as e:
        print(f"Failed to fetch account: {e}")
        return

    print("\n--- Diagnostic: SPY Position ---")
    spy_pos = 0
    try:
        positions = client.get_positions()
        for p in positions:
            if p.symbol == 'SPY':
                print(f"Found SPY Position: {p.qty} shares (Side: {p.side})")
                spy_pos = float(p.qty)
    except Exception as e:
        print(f"Failed to fetch positions: {e}")

    print("\n--- Diagnostic: Test Order ---")
    # Simulate the failing call: BUY 1 share of SPY
    # We use 1 share to minimize impact, but enough to test "Buy"
    symbol = 'SPY'
    qty = 1
    side = 'buy'
    
    print(f"Attempting to submit: {side.upper()} {qty} {symbol}")
    
    try:
        # Pass explicit limit_price=None to force Market Order path used by Hedging
        order = client.submit_order(symbol, qty, side, limit_price=None)
        print(f"✅ Order Submitted Successfully! ID: {order.id}")
        
        # Cleanup (Cancel/Sell if filled)
        print("Cleaning up (Selling the test share)...")
        time.sleep(2)
        client.submit_order(symbol, qty, 'sell')
        
    except Exception as e:
        print(f"❌ Order Failed: {e}")
        
    print("\n--- Diagnostic: Checking Logic ---")
    # Print what the client WOULD send for the failing case (60 shares)
    print("Simulating side logic:")
    diff = 52 # Positive diff
    sim_side = 'sell' if diff < 0 else 'buy'
    print(f"Diff: {diff}, Side: {sim_side} (Expected: buy)")
    
if __name__ == "__main__":
    debug_hedging()
