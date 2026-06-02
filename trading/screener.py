from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockSnapshotRequest
from trading.alpaca_client import AlpacaClient
from trading.sector_manager import SectorManager
from trading.macro_manager import MacroManager
import pandas as pd

from config_tickers import SP100_TICKERS

class MarketScreener:
    def __init__(self, client: AlpacaClient, sentiment_analyzer=None, macro_manager=None):
        self.client = client
        self.sentiment = sentiment_analyzer
        self.macro = macro_manager or MacroManager()
        self.sector_manager = SectorManager()
        
        # Use full S&P 100 list for broad market scanning
        self.universe = SP100_TICKERS
        
        # State exposure for Dashboard/Logging
        self.last_market_mood = "UNKNOWN"
        self.last_market_score = 0.0

    def get_active_assets(self, limit: int = 5):
        """
        Returns top N stocks from the universe sorted by activity.
        Uses Market Sentiment to adjust filters and Macro Bias to favor specific sectors.
        """
        print("Scanning market for active assets...")
        
        # 1. CHECK MACRO BIAS
        macro_bias = self.macro.get_market_bias()
        print(f"  [Screener] Macro Bias Detected: {macro_bias}")

        # 2. CHECK MARKET SENTIMENT
        self.last_market_mood = "NEUTRAL"
        self.last_market_score = 0.0
        
        if self.sentiment:
            self.last_market_score = self.sentiment.analyze_market_sentiment()
            if self.last_market_score > 0.15: self.last_market_mood = "BULLISH"
            elif self.last_market_score < -0.15: self.last_market_mood = "BEARISH"
            
        print(f"  [Screener] Market Mood: {self.last_market_mood} ({self.last_market_score:.2f})")
        
        market_mood = self.last_market_mood # Local alias for logic below

        # 3. FETCH SNAPSHOTS (Batching/Handled by AlpacaClient)
        snapshots = self.client.get_snapshots(self.universe)
        
        if not snapshots:
            print("  ⚠️ Market Scan failed: No snapshots retrieved.")
            return []
        
        data = []
        for symbol, snapshot in snapshots.items():
            price = snapshot.latest_trade.price
            day_change = snapshot.daily_bar.close - snapshot.daily_bar.open
            pct_change = (day_change / snapshot.daily_bar.open) * 100
            volume = snapshot.daily_bar.volume
            prev_volume = snapshot.previous_daily_bar.volume if snapshot.previous_daily_bar else 0
            curr_volume = snapshot.daily_bar.volume
            
            # --- FUNDAMENTAL QUALITY FILTER ---
            # 1. Price > $10 (Avoid Penny Stocks)
            if price < 10.0: continue
                
            # 2. Volume > 1M 
            if prev_volume < 1_000_000: continue
                
            # 3. Avoid Zombie Stocks 
            if abs(pct_change) == 0 and curr_volume < 10000: continue
            
            # --- DYNAMIC MARKET FILTER ---
            # If Bearish, require positive momentum (don't catch falling knives)
            if market_mood == "BEARISH" and pct_change < 0:
                  if volume < 5_000_000: continue
            
            data.append({
                'symbol': symbol,
                'price': price,
                'pct_change': abs(pct_change), 
                'raw_change': pct_change,
                'volume': volume
            })
            
        df = pd.DataFrame(data)
        
        if df.empty:
            print("No assets passed the Quality Filter!")
            return []
        
        # --- MACRO SECTOR BOOSTING ---
        def get_macro_multiplier(symbol):
            sector = self.sector_manager.get_sector(symbol)
            
            # DEFENSIVE Bias: Boost Healthcare, Utilities, Cons. Staples
            if macro_bias == "DEFENSIVE":
                if sector in ["Healthcare", "Utilities", "Consumer Defensive"]:
                    return 1.5
            
            # INFLATIONARY Bias: Boost Energy, Basic Materials
            elif macro_bias == "INFLATIONARY":
                if sector in ["Energy", "Basic Materials"]:
                    return 1.5
            
            return 1.0

        # Create activity score and apply macro multiplier
        df['activity_score'] = df['pct_change'] * df['volume']
        df['macro_multiplier'] = df['symbol'].apply(get_macro_multiplier)
        df['activity_score'] *= df['macro_multiplier']
        
        df = df.sort_values(by='activity_score', ascending=False)
        
        # Take Top candidates for Sentiment Validation (2x limit to allow for drops)
        candidates = df.head(limit * 2)['symbol'].tolist()
        
        final_picks = []
        print(f"\n  [Screener] Validating {len(candidates)} candidates with News...")
        
        if self.sentiment:
            for sym in candidates:
                if len(final_picks) >= limit: break
                
                score, _ = self.sentiment.analyze_sentiment(sym)
                
                # REJECTION LOGIC
                if score < -0.2:
                    print(f"  ❌ Dropping {sym}: Negative News Sentiment ({score:.2f})")
                    continue
                else:
                    print(f"  ✅ Keeping {sym}: News Support ({score:.2f})")
                    final_picks.append(sym)
        else:
            final_picks = candidates[:limit]
            
        print(f"Top active assets: {final_picks}")
        return final_picks
