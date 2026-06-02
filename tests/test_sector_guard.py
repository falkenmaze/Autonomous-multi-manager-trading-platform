
import sys
import os
sys.path.append(os.getcwd())

from trading.portfolio_manager import PortfolioManager
from trading.sector_manager import SectorManager
from unittest.mock import MagicMock

class MockPosition:
    def __init__(self, symbol, market_value):
        self.symbol = symbol
        self.market_value = market_value

print("--- Testing Sector Exposure Guard ---")

# Setup
client = MagicMock()
sector_mgr = SectorManager("tests")
# Pre-cache sector for AAPL as Technology
sector_mgr.sector_map["AAPL"] = "Technology"
sector_mgr.sector_map["MSFT"] = "Technology"
pm = PortfolioManager(client, sector_mgr)

total_equity = 100000

# 1. Simulate a portfolio already heavy (31%) on Technology
positions = [MockPosition("AAPL", 31000)]
client.get_positions.return_value = positions

print(f"Current Portfolio: AAPL ($31,000) in Technology. Equity: ${total_equity}")
exposure = pm._get_sector_exposure(positions, total_equity)
print(f"Current Tech Exposure: {exposure.get('Technology', 0):.1%}")

# 2. Try to optimize allocation for another Tech stock (MSFT)
print("Attempting to allocate MSFT (Technology)...")
# Mock historical data for MSFT
mock_df = MagicMock()
mock_df.empty = False
mock_df.__len__.return_value = 100
client.get_historical_data.return_value = mock_df

# This should trigger Sector Guard and return {}
allocations = pm.optimize_allocations(["MSFT"], total_equity)

if not allocations:
    print("SUCCESS: Sector Guard blocked the trade! ✅")
else:
    print(f"FAILURE: Sector Guard allowed {allocations}. ❌")

# Cleanup
if os.path.exists("tests/sectors.json"):
    os.remove("tests/sectors.json")
