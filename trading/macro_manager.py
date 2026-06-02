import yfinance as yf
import pandas as pd
import numpy as np
import time

class MacroManager:
    """
    Analyzes global macro-economic regimes using Treasury Yields.
    Focuses on the 10Y-3M spread (Predictive of recessions).
    """
    def __init__(self):
        self.ten_year_symbol = "^TNX"     # CBOE 10-Year Treasury Note Yield
        self.three_month_symbol = "^IRX"  # 13-week Treasury Bill Yield
        self.last_fetch = 0
        self.cache_duration = 86400  # 1 day (Macro data doesn't move fast)
        self.cache = {
            'spread': 0.0,
            'regime': 'NORMAL',
            'recommended_beta': 0.0
        }

    def fetch_yields(self):
        """Fetches 10Y/3M yields and Credit/Inflation indicators via yfinance."""
        now = time.time()
        if now - self.last_fetch < self.cache_duration:
            return self.cache

        try:
            print(f"\n  [Macro] Fetching Economic Indicators (Yields, Credit, Inflation)...")
            
            # Treasury Yields
            ten_y = yf.download(self.ten_year_symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
            three_m = yf.download(self.three_month_symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
            
            # Credit & Inflation ETFs
            # HYG (High Yield), IEF (7-10Y Treasury), TIP (Inflation Protected)
            macro_etfs = yf.download(["HYG", "IEF", "TIP"], period="14d", interval="1d", progress=False, auto_adjust=True)

            if ten_y.empty or three_m.empty or macro_etfs.empty:
                print("  [Macro] Warning: Missing critical macro data.")
                return self.cache

            # 1. Yield Curve
            y10 = float(ten_y['Close'].iloc[-1].item())
            y3m = float(three_m['Close'].iloc[-1].item())
            spread = y10 - y3m

            # 2. Credit Spread (HYG vs IEF)
            # We look at the 10-day performance ratio to see if credit is "tightening"
            hyg_ret = macro_etfs['Close']['HYG'].pct_change(10).iloc[-1]
            ief_ret = macro_etfs['Close']['IEF'].pct_change(10).iloc[-1]
            credit_spread_trend = hyg_ret - ief_ret # Positive means Junk bonds outperforming (Risk-On)

            # 3. Inflation Pulse (TIP vs IEF)
            tip_ret = macro_etfs['Close']['TIP'].pct_change(10).iloc[-1]
            inflation_pulse = tip_ret - ief_ret # Positive means TIPS outperforming (Inflation fears)

            regime, beta = self._determine_regime(spread, y10)
            bias = self._calculate_macro_bias(spread, credit_spread_trend, inflation_pulse)
            
            self.cache = {
                'spread': spread,
                'regime': regime,
                'bias': bias,
                'recommended_beta': beta,
                'y10': y10,
                'y3m': y3m,
                'credit_trend': credit_spread_trend,
                'inflation_pulse': inflation_pulse
            }
            self.last_fetch = now
            print(f"  [Macro] Spread: {spread:.2f}% | Bias: {bias} | Regime: {regime} | Beta Rec: {beta}")
            return self.cache

        except Exception as e:
            print(f"  [Macro] Error fetching macro data: {e}")
            return self.cache

    def _determine_regime(self, spread, y10):
        """Standard yield-curve based regime detection."""
        if spread < 0:
            return "INVERTED", 0.3
        elif spread < 1.0:
            return "FLATTENING", 0.5
        elif spread < 2.5:
            return "NORMAL", 1.0
        else:
            return "STEEP", 1.2

    def _calculate_macro_bias(self, spread, credit_trend, inflation_pulse):
        """
        Determines the 'Market Bias' for sector selection:
        - DEFENSIVE: Yield curve inversion OR Credit tightening (Risk-Off)
        - INFLATIONARY: TIPS outperforming Treasuries
        - GROWTH: Normal curve and stable credit
        """
        if spread < -0.2 or credit_trend < -0.015:
            return "DEFENSIVE"
        elif inflation_pulse > 0.01:
            return "INFLATIONARY"
        return "GROWTH"

    def get_market_bias(self):
        data = self.fetch_yields()
        return data.get('bias', 'GROWTH')

    def get_recommended_beta(self):
        data = self.fetch_yields()
        return data['recommended_beta']

    def get_status(self):
        return self.fetch_yields()

if __name__ == "__main__":
    # Test script
    mm = MacroManager()
    print(mm.get_status())
