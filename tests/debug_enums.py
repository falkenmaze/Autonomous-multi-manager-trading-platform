
try:
    from alpaca.trading.enums import QueryOrderStatus
    print("QueryOrderStatus attributes:")
    for i in dir(QueryOrderStatus):
        if not i.startswith("_"):
            print(i)
except ImportError:
    print("QueryOrderStatus not found in alpaca.trading.enums")
