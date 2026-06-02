from trading.alpaca_client import AlpacaClient
from trading.screener import MarketScreener
from strategy.ensemble_strategy import EnsembleStrategy
from strategy.sentiment_analyzer import SentimentAnalyzer
from strategy.smart_money_analyzer import SmartMoneyAnalyzer
from strategy.portfolio_tuner import PortfolioTuner
from trading.portfolio_manager import PortfolioManager
from trading.sector_manager import SectorManager
from trading.market_regime import MarketRegimeManager
from trading.data_logger import DataLogger
from trading.hwm_manager import HWMManager
from trading.macro_manager import MacroManager
from alpaca.trading.enums import PositionSide
from alpaca.trading.requests import ClosePositionRequest
from datetime import datetime
import config
import time
import schedule
import ta
import pandas as pd
import os
import pytz

class Trader:
    def __init__(self, log_dir="logs"):
        # Ensure models directory exists for persistence
        os.makedirs("models", exist_ok=True)
        
        self.client = AlpacaClient()
        self.sector_manager = SectorManager()
        self.regime_manager = MarketRegimeManager()
        self.macro = MacroManager() # New Economic Pulse
        self.sentiment = SentimentAnalyzer(self.client) # Init first
        self.smart_money = SmartMoneyAnalyzer() # Shared insider tracker
        self.screener = MarketScreener(self.client, self.sentiment, self.macro) # Pass macro dependency
        self.pm = PortfolioManager(self.client, self.sector_manager, self.macro) # Pass macro dependency
        self.logger = DataLogger(log_dir=log_dir, client=self.client)
        self.hwm = HWMManager()
        self.strategies = {} # Map symbol -> AIStrategy instance
        self.strategies = {} # Map symbol -> AIStrategy instance
        self.atr_cache = {} # Map symbol -> (atr_value, timestamp)
        self.lockdown = False # System-wide stop (Circuit Breaker)
        self.market_tz = pytz.timezone("US/Eastern")

        # ── PortfolioTuner: loads persisted params and patches config ──────────
        self.tuner = PortfolioTuner()
        self.tuner.apply_to_config(self.tuner.get_params())

    def _is_market_open_window(self):
        """Checks if current time is within the volatile 'Market Open' window."""
        now = datetime.now(self.market_tz)
        
        # Define the trigger time (9:30 AM)
        open_time = now.replace(hour=config.MARKET_OPEN_START_HOUR, 
                                minute=config.MARKET_OPEN_START_MIN, 
                                second=0, microsecond=0)
        
        # Window end (e.g., 10:00 AM)
        window_end = open_time + pd.Timedelta(minutes=config.MARKET_OPEN_DURATION_MINS)
        
        return open_time <= now <= window_end

    def _get_dynamic_risk(self, symbol, avg_entry_price, verbose=True):
        """
        Calculates dynamic Stop Loss and Take Profit percentages based on ATR.
        Returns: (stop_loss_limit, take_profit_limit)
        """
        stop_loss_limit = config.STOP_LOSS_PCT
        take_profit_limit = config.TAKE_PROFIT_PCT
        
        if config.USE_ATR_BASED_RISK:
            # --- ATR CACHING LOGIC ---
            current_time = time.time()
            atr = None
            
            # Check Cache (Valid for 1 Hour = 3600 seconds)
            if symbol in self.atr_cache:
                cached_atr, cached_ts = self.atr_cache[symbol]
                if current_time - cached_ts < 3600:
                    atr = cached_atr
            
            # If not in cache or expired, fetch data
            if atr is None:
                # Fetch recent history (30 days) for ATR calculation
                try:
                    df = self.client.get_historical_data(symbol, lookback_days=30)
                    if not df.empty and len(df) > 14:
                        atr = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14).iloc[-1]
                        self.atr_cache[symbol] = (atr, current_time) # Update cache
                except Exception as e:
                    print(f"Error fetching ATR for {symbol}: {e}")
            
            if atr is not None:
                # Convert ATR to % relative to Entry Price
                atr_sl_pct = (atr * config.ATR_MULTIPLIER_SL) / (avg_entry_price + 1e-6)
                atr_tp_pct = (atr * config.ATR_MULTIPLIER_TP) / (avg_entry_price + 1e-6)
                
                # Sanity Check: Don't let stops be TOO tight or TOO wide
                stop_loss_limit = max(0.02, min(atr_sl_pct, 0.10)) # Min 2%, Max 10%
                take_profit_limit = max(0.04, min(atr_tp_pct, 0.20)) # Min 4%, Max 20%

        # --- MARKET OPEN PROTECTION: TIGHTEN STOPS (Strategy A) ---
        if self._is_market_open_window():
            stop_loss_limit *= config.OPEN_STOP_LOSS_MULTIPLIER
            # Ensure it doesn't get absurdly wide
            stop_loss_limit = min(stop_loss_limit, 0.20) # Max 20% total
            if verbose:
                print(f"  [MarketOpen] Tightening stop loss for {symbol} to {stop_loss_limit:.2%}")

        return stop_loss_limit, take_profit_limit

    def run_daily_scan(self):
        """Runs once a day/session to pick the universe."""
        print("\n=== Running Daily Market Scan ===")
        try:
            active_assets = self.screener.get_active_assets(limit=5)
        except Exception as e:
            print(f"❌ Market Scan Failed: {e}")
            active_assets = []
        
        if not active_assets:
            print("  ⚠️ No assets selected for today. Strategies will remain idle.")
            return
        
        # Reset strategies for new universe
        self.strategies = {symbol: EnsembleStrategy(symbol, self.sentiment, self.smart_money) for symbol in active_assets}
        print(f"Universe selected: {list(self.strategies.keys())}")

    def run_risk_management(self):
        """
        Checks all open positions against Stop Loss and Take Profit thresholds.
        Uses ATR (Volatility) to set dynamic stops if enabled.
        Returns a set of symbols that were closed to avoid immediate re-entry.
        """
        if not config.ENABLE_RISK_MANAGER:
            return set()

        print("\n--- Running Risk Management Checks ---")
        closed_symbols = set()
        
        # --- PORTFOLIO CIRCUIT BREAKER ---
        acct = self.client.get_account()
        equity = float(acct.equity)
        last_equity = self.logger.get_last_equity() if hasattr(self.logger, 'get_last_equity') else equity
        
        # Calculate PnL since last cycle peak or started
        # For a true circuit breaker, we track drawdown from high-water mark
        peak_equity = self.hwm.get_portfolio_peak(equity)
        portfolio_drawdown = (equity - peak_equity) / peak_equity if peak_equity > 0 else 0
        
        if portfolio_drawdown <= -config.MAX_PORTFOLIO_DRAWDOWN:
            print(f"🛑 PORTFOLIO CIRCUIT BREAKER TRIGGERED: Drawdown {portfolio_drawdown:.2%} exceeds {config.MAX_PORTFOLIO_DRAWDOWN:.2%}")
            print("  >>> LIQUIDATING ALL POSITIONS AND ENTERING LOCKDOWN <<<")
            self.lockdown = True
            
            # Close EVERYTHING
            positions = self.client.get_positions()
            for p in positions:
                print(f"  Closing {p.symbol} due to portfolio lockdown...")
                side = 'long' if p.side == PositionSide.LONG else 'short'
                self.logger.log_trade(p.symbol, float(p.avg_entry_price), float(p.current_price), abs(float(p.qty)), side)
                self.client.close_position(p.symbol)
                closed_symbols.add(p.symbol)
            return closed_symbols

        positions = self.client.get_positions()

        for p in positions:
            symbol = p.symbol
            try:
                # Calculate Unrealized PnL %
                current_price = float(p.current_price)
                avg_entry_price = float(p.avg_entry_price) if p.avg_entry_price else 0.0
                
                if avg_entry_price == 0:
                    print(f"  [WARNING] Missing avg_entry_price for {symbol}. Using previous close as fallback.")
                    try:
                        fallback_df = self.client.get_historical_data(symbol, lookback_days=5)
                        if not fallback_df.empty and len(fallback_df) > 1:
                            avg_entry_price = float(fallback_df['close'].iloc[-2])
                        else:
                            avg_entry_price = current_price
                    except Exception:
                        avg_entry_price = current_price

                # Determine PnL direction
                if p.side == PositionSide.LONG:
                    pnl_raw = (current_price - avg_entry_price)
                    pnl_pct = pnl_raw / avg_entry_price
                else: # short
                    pnl_raw = (avg_entry_price - current_price)
                    pnl_pct = pnl_raw / avg_entry_price

                # --- DYNAMIC RISK CALCULATION ---
                stop_loss_limit, take_profit_limit = self._get_dynamic_risk(symbol, avg_entry_price)
                
                # Check Stop Loss
                if pnl_pct <= -stop_loss_limit:
                    print(f"🚨 STOP LOSS TRIGGERED for {symbol}: PnL {pnl_pct:.2%} (Limit: -{stop_loss_limit:.2%})")
                    side = 'long' if p.side == PositionSide.LONG else 'short'
                    self.logger.log_trade(symbol, avg_entry_price, current_price, abs(float(p.qty)), side)
                    self.client.close_position(symbol)
                    
                    # Update RL + PortfolioTuner with the loss
                    if symbol in self.strategies:
                        effective_pnl = pnl_pct - (config.TRANSACTION_COST_PCT * 2)
                        self.strategies[symbol].update_rl(effective_pnl)
                        self.tuner.record_outcome(symbol, effective_pnl)
                        
                    self.hwm.reset(symbol)
                    closed_symbols.add(symbol)
                    
                # Else: Check Take Profit (With Partial Scale-Out)
                elif pnl_pct >= take_profit_limit:
                    if config.ENABLE_PARTIAL_TP:
                        # --- ALPHA BOOSTER: DYNAMIC SCALE-OUT ---
                        vix = self.regime_manager.get_vix()
                        if vix >= config.VIX_TP_HIGH:
                            target_tp_pct = config.PARTIAL_TP_PCT_HIGH_VIX
                            print(f"  [DynamicTP] High Volatility ({vix:.1f}). Banking {target_tp_pct:.0%} of gains.")
                        elif vix <= config.VIX_TP_LOW:
                            target_tp_pct = config.PARTIAL_TP_PCT_LOW_VIX
                            print(f"  [DynamicTP] Low Volatility ({vix:.1f}). Letting {1-target_tp_pct:.0%} of position run.")
                        else:
                            target_tp_pct = config.PARTIAL_TP_PCT_NORMAL
                            print(f"  [DynamicTP] Normal Volatility ({vix:.1f}). Selling {target_tp_pct:.0%}.")

                        qty_to_close = max(1, int(float(p.qty) * target_tp_pct))
                        
                        if qty_to_close < float(p.qty):
                            print(f"💰 PARTIAL TAKE PROFIT for {symbol}: Scaling out {qty_to_close} shares ({target_tp_pct:.0%}).")
                            side = 'long' if p.side == PositionSide.LONG else 'short'
                            self.logger.log_trade(symbol, avg_entry_price, current_price, qty_to_close, side)
                            self.client.trading_client.close_position(symbol, close_options=ClosePositionRequest(qty=str(qty_to_close)))
                        else:
                            print(f"💰 TAKE PROFIT for {symbol}: Position too small to scale out. Closing entirely.")
                            side = 'long' if p.side == PositionSide.LONG else 'short'
                            self.logger.log_trade(symbol, avg_entry_price, current_price, abs(float(p.qty)), side)
                            self.client.close_position(symbol)
                            closed_symbols.add(symbol)
                    else:
                        print(f"💰 TAKE PROFIT TRIGGERED for {symbol}: PnL {pnl_pct:.2%} (Limit: +{take_profit_limit:.2%})")
                        side = 'long' if p.side == PositionSide.LONG else 'short'
                        self.logger.log_trade(symbol, avg_entry_price, current_price, abs(float(p.qty)), side)
                        self.client.close_position(symbol)
                        closed_symbols.add(symbol)
                    
                    # Update RL + PortfolioTuner with the gain
                    if symbol in self.strategies:
                        effective_pnl = pnl_pct - (config.TRANSACTION_COST_PCT * 2)
                        self.strategies[symbol].update_rl(effective_pnl)
                        self.tuner.record_outcome(symbol, effective_pnl)
                        
                    self.hwm.reset(symbol)
                
                # --- TRAILING STOP LOGIC ---
                elif config.ENABLE_TRAILING_STOP:
                    side_str = 'long' if p.side == PositionSide.LONG else 'short'
                    peak = self.hwm.update(symbol, current_price, side_str)
                    
                    # Calculate drop from peak
                    if side_str == 'long':
                        drop_from_peak = (peak - current_price) / peak
                    else: # short
                        drop_from_peak = (current_price - peak) / peak
                    
                    # --- MARKET OPEN PROTECTION: TIGHTEN TRAILING (Strategy B) ---
                    # Only if we are gapped up and it's the opening window
                    current_trailing_pct = config.TRAILING_STOP_PCT
                    if self._is_market_open_window() and pnl_pct >= config.OPEN_GAP_THRESHOLD:
                        current_trailing_pct = config.OPEN_GAP_TRAILING_STOP
                        print(f"  [MarketOpen] Gap-up detected for {symbol} ({pnl_pct:.2%}). Tightening Trailing Stop to {current_trailing_pct:.2%}")

                    # --- ALPHA BOOSTER: RUNNER TRAILING STOP ---
                    # If we are already profitable (above TP limit) but let it run, use a wider stop
                    reason_msg = None
                    if pnl_pct >= take_profit_limit:
                        current_trailing_pct = config.RUNNER_TRAILING_STOP_PCT
                        reason_msg = "ALPHA RUNNER TRAILING"
                    
                    if drop_from_peak >= current_trailing_pct:
                        if not reason_msg: # Fallback
                            reason_msg = "TRAILING STOP" if current_trailing_pct == config.TRAILING_STOP_PCT else "MARKET OPEN GAP FADE"
                        print(f"📉 {reason_msg} TRIGGERED for {symbol}: Drop from peak {drop_from_peak:.2%} (Limit: {current_trailing_pct:.2%})")
                        side = 'long' if p.side == PositionSide.LONG else 'short'
                        self.logger.log_trade(symbol, avg_entry_price, current_price, abs(float(p.qty)), side)
                        self.client.close_position(symbol)
                        
                        # Update RL + PortfolioTuner
                        if symbol in self.strategies:
                            effective_pnl = pnl_pct - (config.TRANSACTION_COST_PCT * 2)
                            self.strategies[symbol].update_rl(effective_pnl)
                            self.tuner.record_outcome(symbol, effective_pnl)
                            
                        self.hwm.reset(symbol)
                        closed_symbols.add(symbol)

            except Exception as e:
                print(f"Error checking risk for {symbol}: {e}")
        
        # Cleanup HWM for closed positions
        self.hwm.cleanup([p.symbol for p in positions if p.symbol not in closed_symbols])
        
        if not closed_symbols:
            print(f"  ✅ Risk Monitor: Checked {len(positions)} positions. All safe.")
            
        return closed_symbols

    def cleanup_stale_orders(self):
        """
        Cancels open orders that have been sitting for longer than config.ORDER_TIMEOUT_MINUTES.
        This prevents 'chasing' the market with stale limit prices.
        """
        if not hasattr(config, 'ORDER_TIMEOUT_MINUTES'):
            return

        print(f"\n--- Checking for Stale Orders (Timeout: {config.ORDER_TIMEOUT_MINUTES}m) ---")
        try:
            open_orders = self.client.get_open_orders()
            now = datetime.now()
            
            for order in open_orders:
                # order.created_at is often in UTC
                created_at = order.created_at
                if created_at.tzinfo:
                    from datetime import timezone
                    now_utc = datetime.now(timezone.utc)
                    age_minutes = (now_utc - created_at).total_seconds() / 60
                else:
                    age_minutes = (now - created_at).total_seconds() / 60

                if age_minutes >= config.ORDER_TIMEOUT_MINUTES:
                    print(f"  ⚠️ Order {order.id} for {order.symbol} is STALE ({age_minutes:.1f}m old). Cancelling...")
                    self.client.trading_client.cancel_order_by_id(order.id)
        except Exception as e:
            print(f"Error during order cleanup: {e}")

    def run_trading_cycle(self):
        """Runs every N minutes."""
        try:
            if self.lockdown:
                print("\n⛔ BOT IS IN LOCKDOWN MODE. No new analysis or trades will be executed.")
                print("   Manual intervention required to reset.")
                return

            print(f"\n=== Trading Cycle at {time.ctime()} ===")
            
            # --- PRE-SCAN PHASE ---
            # Clean up old unfilled orders before starting new analysis
            self.cleanup_stale_orders()
            
            if not self.strategies:
                self.run_daily_scan()

            # --- RISK MANAGEMENT PHASE ---
            # Close losing/winning positions BEFORE running new analysis
            closed_symbols = self.run_risk_management()

            # --- REGIME DETECTION PHASE ---
            vix_level = self.regime_manager.get_vix()
            regime = self.regime_manager.get_regime()

            # List to store potential buys for batch optimization
            potential_buys = []
            # Store analysis results to avoid re-running
            analysis_results = {} # symbol -> (action, prob, volatility)
            confidence_scores = {} # For optimizer
            
            # 1. ANALYSIS PHASE
            for symbol, strategy in self.strategies.items():
                if symbol in closed_symbols:
                    print(f"Skipping {symbol} (Position closed by Risk Manager)")
                    continue

                try:
                    print(f"-- Analyzing {symbol} (Regime: {regime}) --")
                    df = self.client.get_historical_data(symbol, lookback_days=180)
                    
                    if df.empty:
                        continue

                    action, prob, reason, news_meta = strategy.analyze(df, vix_level=vix_level)
                    volatility = df['close'].pct_change().std()
                    
                    analysis_results[symbol] = (action, prob, volatility, reason, news_meta)
                    confidence_scores[symbol] = prob
                    
                    if action == 'buy':
                        potential_buys.append(symbol)
                except Exception as e:
                    print(f"Error analyzing {symbol}: {e}")

            # 2. OPTIMIZATION PHASE (MVO)
            acct = self.client.get_account()
            equity = float(acct.equity)
            buying_power = float(acct.buying_power)
            
            # Calculate optimal allocations for all buys together
            optimized_allocations = self.pm.optimize_allocations(potential_buys, equity, confidence_scores=confidence_scores)
            
            # 3. EXECUTION PHASE
            # --- MARKET OPEN BLOCK: No new entries at 9:30-10:00 AM ---
            in_open_window = self._is_market_open_window()
            if in_open_window:
                print("⏸️  [MarketOpen] ENTRY BLOCK ACTIVE (9:30–10:00 AM). Skipping new buys/shorts. Risk management still running.")

            for symbol, (action, prob, volatility, reason, news_meta) in analysis_results.items():
                try:
                    # Check current position
                    qty_held = 0
                    positions = self.client.get_positions()
                    for p in positions:
                        if p.symbol == symbol:
                            qty_held = float(p.qty)
                            break
                    
                    # --- SPREAD-AWARE PRICING ---
                    quote = self.client.get_latest_quote(symbol)
                    if not quote:
                        print(f"Skipping {symbol}: Could not fetch latest quote.")
                        continue
                        
                    current_price = quote['last']
                    bid_price = quote['bid']
                    ask_price = quote['ask']
                    
                    # --- SAFEGUARD: SPREAD-SIZE FILTER ---
                    if bid_price > 0:
                        spread_pct = (ask_price - bid_price) / bid_price
                        if spread_pct > config.MAX_SPREAD_PCT:
                            print(f"[WARNING] Skipping {symbol}: Spread TOO WIDE ({spread_pct:.2%} > {config.MAX_SPREAD_PCT:.2%})")
                            continue

                    # DYNAMIC PRICING: Use Midpoint + Half-Spread for Slippage Buffer
                    # Instead of fixed 0.05%, we use half the spread or min 0.01%
                    spread_pct = quote.get('spread_pct', 0.0)
                    dynamic_buffer = max(0.0001, spread_pct * 0.5)
                    
                    buy_limit = ask_price * (1 + dynamic_buffer)
                    sell_limit = bid_price * (1 - dynamic_buffer)
                    
                    print(f"  [Price] {symbol} Mid: {(bid_price+ask_price)/2:.2f} | Spread: {spread_pct:.4%} | Buffer: {dynamic_buffer:.4%}")
                    
                    # Check for existing open orders to prevent duplicates
                    open_orders = self.client.get_open_orders(symbol)
                    has_open_order = len(open_orders) > 0
                    
                    if has_open_order:
                        # Show detailed info about unfilled orders
                        for order in open_orders:
                            print(f"  [ORDER] {order.id}: {order.side} {order.qty} @ {order.limit_price or 'Market'} (Status: {order.status}, Filled: {order.filled_qty}/{order.qty})")
                        print(f"[WAIT] Skipping {symbol}: Already has {len(open_orders)} unfilled order(s)")
                        continue

                    if action == 'buy':
                        # COVER SHORT FIRST
                        if qty_held < 0:
                             print(f"COVERING SHORT {symbol} (Conf: {prob:.2f})")
                             
                             # Get PnL for RL + tuner update before closing
                             pnl_pct = 0
                             for p in positions:
                                 if p.symbol == symbol:
                                     avg_entry = float(p.avg_entry_price)
                                     if avg_entry > 0:
                                         pnl_pct = (avg_entry - current_price) / avg_entry
                                     break
                                     
                             self.logger.log_trade(symbol, avg_entry, current_price, abs(qty_held), 'short')
                             self.client.close_position(symbol)
                             
                             effective_pnl = pnl_pct - (config.TRANSACTION_COST_PCT * 2)
                             self.strategies[symbol].update_rl(effective_pnl)
                             self.tuner.record_outcome(symbol, effective_pnl)
                             
                             print(f"  [WAIT] Position closed. Will enter LONG on next cycle after fill confirmation.")
                             continue
                             
                        # EXECUTE LONG (Using MVO Size)
                        if qty_held <= 0:
                            # --- MARKET OPEN BLOCK ---
                            if in_open_window:
                                print(f"  ⏸️  [MarketOpen] Blocking new LONG entry for {symbol}. Will re-evaluate after 10:00 AM.")
                                continue
                            # Use Optimised Size from MVO
                            if symbol in optimized_allocations:
                                size = optimized_allocations[symbol]
                                
                                cost = size * buy_limit
                                if cost > buying_power * (1 - config.MARGIN_BUFFER_PCT):
                                    print(f"[WARNING] Skipping {symbol}: Insufficient Buying Power (Needs ${cost:,.2f}, Have ${buying_power:,.2f})")
                                    continue

                                print(f"BUY SIGNAL for {symbol} (Ask: {ask_price}, Limit: {buy_limit:.2f}, Size: {size})")
                                self.client.submit_order(symbol, qty=size, side='buy', limit_price=buy_limit)
                                buying_power -= cost

                                # Record decision context for PortfolioTuner
                                self.tuner.record_decision(symbol, {
                                    'action': 'buy', 'final_confidence': prob,
                                    'reason': reason, 'vix': vix_level,
                                })
                            else:
                                print(f"Skipping {symbol} (MVO allocated 0 zero)")
                        else:
                            print(f"HOLD LONG {symbol} (Conf: {prob:.2f}) | {reason}")

                    elif action == 'sell':
                        # SELL POSTION
                        if qty_held > 0:
                            print(f"SELL SIGNAL for {symbol} (Conf: {prob:.2f})")
                            
                            # Get PnL for RL + tuner update before closing
                            pnl_pct = 0
                            for p in positions:
                                if p.symbol == symbol:
                                    avg_entry = float(p.avg_entry_price)
                                    if avg_entry > 0:
                                        pnl_pct = (current_price - avg_entry) / avg_entry
                                    break
                                    
                            self.logger.log_trade(symbol, avg_entry, current_price, abs(qty_held), 'long')
                            self.client.close_position(symbol)
                            
                            effective_pnl = pnl_pct - (config.TRANSACTION_COST_PCT * 2)
                            self.strategies[symbol].update_rl(effective_pnl)
                            self.tuner.record_outcome(symbol, effective_pnl)
                            
                            print(f"  [WAIT] Position closed. Will enter SHORT on next cycle after fill confirmation.")
                            continue
                            
                        # ENTER SHORT (Legacy Volatility Sizing for Shorts)
                        elif qty_held == 0:
                             # --- MARKET OPEN BLOCK ---
                             if in_open_window:
                                 print(f"  ⏸️  [MarketOpen] Blocking new SHORT entry for {symbol}. Will re-evaluate after 10:00 AM.")
                                 continue
                             # --- SAFEGUARD: SHORTING AVAILABILITY CHECK ---
                             asset = self.client.get_asset(symbol)
                             if not asset or not asset.shortable or asset.easy_to_borrow is False:
                                 print(f"[WARNING] Skipping SHORT {symbol}: Asset NOT Shortable or Hard-to-Borrow (HTB)")
                                 continue
                             
                             vol_val = volatility if not pd.isna(volatility) else 0.02
                             size = self.pm.calculate_position_size(symbol, current_price, vol_val, equity)
                             
                             # --- SAFEGUARD: BUYING POWER CHECK ---
                             cost = size * current_price # Shorts still use BP
                             if cost > buying_power * (1 - config.MARGIN_BUFFER_PCT):
                                 print(f"[WARNING] Skipping {symbol}: Insufficient Buying Power (Needs ${cost:,.2f}, Have ${buying_power:,.2f})")
                                 continue

                             print(f"SHORT SIGNAL for {symbol} (Bid: {bid_price}, Limit: {sell_limit:.2f}, Size: {size})")
                             self.client.submit_order(symbol, qty=size, side='sell', limit_price=sell_limit)
                             buying_power -= cost

                             # Record decision context for PortfolioTuner
                             self.tuner.record_decision(symbol, {
                                 'action': 'sell', 'final_confidence': prob,
                                 'reason': reason, 'vix': vix_level,
                             })
                        else:
                             print(f"HOLD SHORT {symbol} (Conf: {prob:.2f}) | {reason}")
                    
                    else:
                        print(f"HOLD/WAIT {symbol} (Conf: {prob:.2f}) | {reason}")
                        
                    time.sleep(1) 
                except Exception as e:
                    print(f"Error executing {symbol}: {e}")
                
            # 4. HEDGING PHASE
            try:
                # Fetch current positions (used for both hedging and logging)
                current_positions = self.client.get_positions()
                
                print("\n--- Executing Beta Hedging ---")
                self.pm.hedge_portfolio(current_positions)
            except Exception as e:
                print(f"Hedging Error: {e}")
                # Fetch positions again if hedging failed
                current_positions = self.client.get_positions()
                
            # 5. LOGGING PHASE (For Dashboard)
            try:
                
                positions_data = []
                for p in current_positions:
                    positions_data.append({
                        'symbol': p.symbol,
                        'qty': float(p.qty),
                        'market_value': float(p.market_value),
                        'pnl': float(p.unrealized_pl),
                        'avg_entry': float(p.avg_entry_price)
                    })
                    
                    # Fetch Risk Targets silently (skip SPY hedge — it has no strategy stop-loss)
                    if p.symbol != self.pm.spy_symbol:
                        sl_pct, tp_pct = self._get_dynamic_risk(p.symbol, float(p.avg_entry_price), verbose=False)
                    else:
                        sl_pct, tp_pct = None, None  # Hedge position; N/A
                    positions_data[-1]['sl_pct'] = sl_pct
                    positions_data[-1]['tp_pct'] = tp_pct
                
                # Format signals for logger
                signals_data = {}
                for sym, res in analysis_results.items():
                     # res is (action, prob, volatility, reason, news_meta)
                     signals_data[sym] = {
                         'action': res[0],
                         'confidence': float(res[1]),
                         'volatility': float(res[2]),
                         'reason': res[3],
                         'catalyst': res[4] # Add Catalyst
                     }
                 
                # Calculate Portfolio Risk Types (Beta & Exposure)
                # Returns: (raw_beta, net_val_non_spy, weighted_beta_dollars)
                _, port_val, port_weighted_beta = self.pm.calculate_portfolio_beta(current_positions)
                
                # Check for SPY hedge
                spy_pos = next((p for p in current_positions if p.symbol == 'SPY'), None)
                spy_val = float(spy_pos.market_value) if spy_pos else 0.0
                net_exposure = port_val + spy_val # Total Long + Short Hedge

                # Calculate Effective Beta (Dollar Beta / Equity)
                # This is "How many units of SPY is the portfolio behaving like?" per unit of Equity
                effective_beta = port_weighted_beta / (equity + 1e-6)

                self.logger.log_cycle({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'equity': equity,
                    'cash': float(acct.cash),
                    'vix': vix_level,
                    'regime': regime,
                    'macro_bias': self.macro.get_market_bias(), # Log specific bias
                    'risk_metrics': {
                        'beta': effective_beta,
                        'gross_exposure': port_val, # Note: This is Net Non-SPY
                        'net_exposure': net_exposure
                    },
                    'market_sentiment': {
                        'score': getattr(self.screener, 'last_market_score', 0.0),
                        'mood': getattr(self.screener, 'last_market_mood', "UNKNOWN")
                    },
                    'positions': positions_data,
                    'signals': signals_data,
                    'screener_picks': list(self.strategies.keys()), # The universe in use
                    'potential_buys': potential_buys,
                    'allocations': optimized_allocations
                })
            except Exception as e:
                print(f"Logging Error: {e}")
        
        except Exception as e:
            print(f"\n⚠️ TRADING CYCLE ERROR: {e}")
            print(f"   The bot will retry on the next scheduled cycle...")
            import traceback
            traceback.print_exc()

    def start(self):
        print("Starting Mini AI Hedge Fund...")
        
        # Initial scan
        self.run_daily_scan()
        
        # Initial cycle
        self.run_trading_cycle()
        
        
        # Schedule - check every 30 minutes for multi-day strategy
        # Less frequent checks appropriate for daily timeframe
        schedule.every(30).minutes.do(self.run_trading_cycle)
        
        # MONITORING: Run Risk Checks every 5 minutes (High Frequency)
        # This protects us from sharp intraday moves even if the strategy is sleeping.
        schedule.every(5).minutes.do(self.run_risk_management)
        
        print("Bot is running. Press Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)
