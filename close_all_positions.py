"""
Close all existing positions in the Alpaca account.
Run this script at market close or anytime you want to flatten your portfolio.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.alpaca_client import AlpacaClient


def close_all_positions():
    """Close all open positions and display results."""
    
    print("=" * 70)
    print("CLOSE ALL POSITIONS")
    print("=" * 70)
    
    client = AlpacaClient()
    
    # Get all current positions
    try:
        positions = client.get_positions()
        
        if not positions:
            print("\n✓ No open positions to close.")
            return
        
        print(f"\nFound {len(positions)} open position(s):")
        print("-" * 70)
        
        total_value = 0
        
        for pos in positions:
            qty = float(pos.qty)
            market_value = float(pos.market_value)
            unrealized_pl = float(pos.unrealized_pl)
            unrealized_plpc = float(pos.unrealized_plpc)
            
            total_value += market_value
            
            side = "LONG" if qty > 0 else "SHORT"
            
            print(f"{pos.symbol:<8} | {side:<6} | Qty: {abs(qty):<8.0f} | "
                  f"Value: ${market_value:>10,.2f} | "
                  f"P&L: ${unrealized_pl:>8,.2f} ({unrealized_plpc*100:+.2f}%)")
        
        print("-" * 70)
        print(f"Total Portfolio Value: ${total_value:,.2f}")
        
        # Ask for confirmation
        print("\n⚠️  WARNING: This will close ALL positions immediately.")
        response = input("Type 'YES' to confirm: ")
        
        if response.strip().upper() != 'YES':
            print("\n❌ Aborted - No positions were closed.")
            return
        
        # Close all positions
        print("\nClosing positions...")
        print("-" * 70)
        
        for pos in positions:
            try:
                client.close_position(pos.symbol)
                print(f"✓ Closed {pos.symbol}")
            except Exception as e:
                print(f"✗ Failed to close {pos.symbol}: {e}")
        
        print("-" * 70)
        print("\n✅ All positions closed successfully!")
        
        # Show final account status
        account = client.get_account()
        print(f"\nFinal Account Status:")
        print(f"  Cash: ${float(account.cash):,.2f}")
        print(f"  Equity: ${float(account.equity):,.2f}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    close_all_positions()
