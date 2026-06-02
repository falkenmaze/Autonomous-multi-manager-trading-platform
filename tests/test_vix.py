
import sys
import os
sys.path.append(os.getcwd())
from trading.market_regime import MarketRegimeManager

print("--- Testing VIX Fetch ---")
regime_mgr = MarketRegimeManager()
vix = regime_mgr.get_vix()
state = regime_mgr.get_regime()

print(f"Current VIX: {vix:.2f}")
print(f"Current Regime: {state}")

if vix > 0:
    print("SUCCESS: VIX Data retrieved correctly! ✅")
else:
    print("FAILURE: VIX Data is invalid. ❌")
