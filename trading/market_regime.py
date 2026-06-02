import yfinance as yf
import time
import pandas as pd

class MarketRegimeManager:
    """
    Monitors global market volatility via VIX.
    """
    def __init__(self):
        self.vix_symbol = "^VIX"
        self.last_vix = 20.0 # Default neutral
        self.last_fetch = 0
        self.cache_duration = 3600 # 1 hour

    def get_vix(self):
        """Fetches latest VIX value with caching."""
        now = time.time()
        if now - self.last_fetch < self.cache_duration:
            return self.last_vix

        try:
            print(f"  [Regime] Fetching latest ^VIX...")
            
            # Anti-Rate Limit: Sleep randomly (1-3s) before request
            import random
            time.sleep(random.uniform(1, 3))
            
            # progress=False hides the progress bar
            # switch to daily data for reliability
            vix_data = yf.download(self.vix_symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
            if not vix_data.empty:
                # yfinance returns Close as a single col unless multi-ticker
                self.last_vix = float(vix_data['Close'].iloc[-1].item())
                self.last_fetch = now
                print(f"  [Regime] VIX is {self.last_vix:.2f}")
                return self.last_vix
        except Exception as e:
            if "Rate limited" in str(e):
                print(f"  [Regime] VIX Rate Limited. Using last known value: {self.last_vix}")
            else:
                print(f"  [Regime] Error fetching VIX: {e}")
        
        return self.last_vix

    def get_regime(self):
        v = self.get_vix()
        if v < 15: return "LOW_VOL"
        if v < 25: return "NORMAL"
        return "HIGH_VOL"
