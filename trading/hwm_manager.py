
import json
import os

class HWMManager:
    """
    Manages High Water Marks (HWM) for open positions to support Trailing Stops.
    Persists data to logs/hwm.json.
    """
    def __init__(self, log_dir="logs"):
        self.log_path = os.path.join(log_dir, "hwm.json")
        self.hwm_data = self._load()

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
            json.dump(self.hwm_data, f, indent=4)

    def update(self, symbol, current_price, side):
        """
        Updates the HWM for a symbol if the current price is a new peak.
        side: 'long' or 'short'
        """
        if symbol not in self.hwm_data:
            self.hwm_data[symbol] = current_price
            self._save()
            return current_price

        peak = self.hwm_data[symbol]
        
        if side == 'long':
            if current_price > peak:
                self.hwm_data[symbol] = current_price
                self._save()
                return current_price
        else: # short
            if current_price < peak:
                self.hwm_data[symbol] = current_price
                self._save()
                return current_price
        
        return peak

    def get_peak(self, symbol):
        return self.hwm_data.get(symbol)

    def reset(self, symbol):
        """Call when a position is closed."""
        if symbol in self.hwm_data:
            del self.hwm_data[symbol]
            self._save()

    def get_portfolio_peak(self, current_equity):
        """Tracks the highest ever portfolio equity for drawdown calculations."""
        key = "PORTFOLIO_PEAK"
        if key not in self.hwm_data:
            self.hwm_data[key] = current_equity
            self._save()
            return current_equity
            
        peak = self.hwm_data[key]
        if current_equity > peak:
            self.hwm_data[key] = current_equity
            self._save()
            return current_equity
            
        return peak

    def cleanup(self, current_open_symbols):
        """Remove HWM for symbols no longer held. Excludes meta-keys like PORTFOLIO_PEAK."""
        to_delete = [s for s in self.hwm_data if s not in current_open_symbols and s != "PORTFOLIO_PEAK"]
        if to_delete:
            for s in to_delete:
                del self.hwm_data[s]
            self._save()
