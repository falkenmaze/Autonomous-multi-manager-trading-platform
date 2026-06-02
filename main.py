from trading.trader import Trader
import config
import traceback
import sys

if __name__ == "__main__":
    try:
        trader = Trader()
        trader.start()
    except KeyboardInterrupt:
        print("\n✋ Bot stopped by user (Ctrl+C). Exiting gracefully...")
        sys.exit(0)
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        print(f"\n📋 Full Traceback:")
        traceback.print_exc()
        print(f"\n💡 Recovery Tips:")
        print(f"   • Check your internet connection")
        print(f"   • Verify Alpaca API status at https://status.alpaca.markets")
        print(f"   • Restart the bot with: python main.py")
        sys.exit(1)
