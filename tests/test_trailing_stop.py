
import sys
import os
sys.path.append(os.getcwd())

from trading.hwm_manager import HWMManager
import config

print("--- Testing Trailing Stop Logic ---")
hwm = HWMManager("tests") # Use tests dir for mock hwm.json

symbol = "TEST_STOCK"
side = 'long'
entry_price = 100.0
trail_pct = 0.03 # 3%

# 1. Entry
print(f"Entry at ${entry_price}")
peak = hwm.update(symbol, entry_price, side)

# 2. Price Rally to 110
rally_price = 110.0
print(f"Price rallies to ${rally_price}")
peak = hwm.update(symbol, rally_price, side)
print(f"  New Peak: {peak}")

# 3. Price Dips to 108 (1.8% dip - Should NOT trigger)
dip_price = 108.0
drop = (peak - dip_price) / peak
print(f"Price dips to ${dip_price} (Drop: {drop:.2%})")
if drop >= trail_pct:
    print("  TRIGGER: Trailing Stop Hit!")
else:
    print("  SAFE: Below Trail %")

# 4. Price Dips to 106.5 (3.18% dip - Should TRIGGER)
trigger_price = 106.5
drop = (peak - trigger_price) / peak
print(f"Price dips to ${trigger_price} (Drop: {drop:.2%})")
if drop >= trail_pct:
    print("  TRIGGER: Trailing Stop Hit! ✅")
    hwm.reset(symbol)
else:
    print("  ERROR: Should have triggered.")

# Cleanup
if os.path.exists("tests/hwm.json"):
    os.remove("tests/hwm.json")
