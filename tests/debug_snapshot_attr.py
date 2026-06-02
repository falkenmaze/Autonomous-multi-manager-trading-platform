
from trading.alpaca_client import AlpacaClient
from alpaca.data.requests import StockSnapshotRequest

client = AlpacaClient()
request = StockSnapshotRequest(symbol_or_symbols="AAPL")
snapshots = client.data_client.get_stock_snapshot(request)
snapshot = snapshots["AAPL"]

print("Snapshot attributes:")
for i in dir(snapshot):
    if not i.startswith("_"):
        print(i)
