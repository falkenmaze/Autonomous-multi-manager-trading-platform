from alpaca.data.historical import StockHistoricalDataClient
import config

client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)
methods = [method_name for method_name in dir(client) if callable(getattr(client, method_name))]
print("Methods available:", methods)
