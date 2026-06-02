
import yfinance as yf
import json
import os

class SectorManager:
    """
    Fetches and caches sector information for tickers using yfinance.
    """
    def __init__(self, log_dir="logs"):
        self.log_path = os.path.join(log_dir, "sectors.json")
        os.makedirs(log_dir, exist_ok=True)
        self.sector_map = self._load()

    def _load(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        with open(self.log_path, 'w') as f:
            json.dump(self.sector_map, f, indent=4)

    def get_sector(self, symbol):
        """Returns the sector for a symbol, fetching it if not in cache."""
        if symbol in self.sector_map:
            return self.sector_map[symbol]

        try:
            print(f"  [Sectors] Fetching sector for {symbol}...")
            ticker = yf.Ticker(symbol)
            sector = ticker.info.get('sector', 'Unknown')
            self.sector_map[symbol] = sector
            self._save()
            return sector
        except Exception as e:
            print(f"  [Sectors] Error fetching {symbol}: {e}")
            return "Unknown"

    def get_batch_sectors(self, symbols):
        """Efficiently fetches sectors for multiple symbols."""
        results = {}
        to_fetch = []
        for s in symbols:
            if s in self.sector_map:
                results[s] = self.sector_map[s]
            else:
                to_fetch.append(s)
        
        if to_fetch:
            for s in to_fetch:
                results[s] = self.get_sector(s)
        
        return results
