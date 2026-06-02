import json

with open('logs/portfolio_history.json', 'r') as f:
    data = json.load(f)

print("March 24-25:")
for r in data:
    if '2026-03-24' in r['timestamp'] or '2026-03-25' in r['timestamp']:
        print(f"{r['timestamp']} | Equity: {r['equity']:.2f}")
