import numpy as np
import pandas as pd
import ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from strategy.monte_carlo import MonteCarloStrategy
from strategy.smart_money_analyzer import SmartMoneyAnalyzer
from trading.event_manager import EventManager
import pickle
import os
import time
import config

class SafeRLAgent:
    """
    A simplified Q-Learning agent that learns to adjust confidence.
    It does NOT initiate trades on its own. It only acts as a 'Advisor'.
    """
    def __init__(self, symbol):
        self.symbol = symbol
        self.q_table = {} # State -> Weight Adjustment
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.last_state = None
        self.last_action = None
        
        self.model_path = f"models/{symbol}_qtable.pkl"
        self.load_memory()

    def load_memory(self):
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.q_table = pickle.load(f)
                print(f"  [RL] Loaded Q-Table for {self.symbol} (Size: {len(self.q_table)})")
            except Exception as e:
                print(f"  [RL] Failed to load memory for {self.symbol}: {e}")

    def save_memory(self):
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.q_table, f)
        except Exception as e:
            print(f"  [RL] Failed to save memory for {self.symbol}: {e}")
        
    def get_state(self, rsi, trend):
        # Discretize state to keep table small
        # RSI Buckets: 0=Oversold, 1=Normal, 2=Overbought
        rsi_state = 0 if rsi < 30 else (2 if rsi > 70 else 1)
        # Trend: 0=Down, 1=Up
        trend_state = 1 if trend > 0 else 0
        return (rsi_state, trend_state)

    def get_adjustment(self, state):
        # Returns a small adjustment to confidence (e.g., +0.05 or -0.05)
        # Defaults to 0 if unknown
        return self.q_table.get(state, 0.0)

    def update(self, reward):
        """Standard Q-Learning Update"""
        if self.last_state is None: return
        
        current_q = self.q_table.get(self.last_state, 0.0)
        new_q = current_q + self.learning_rate * (reward - current_q)
        # Clip to prevent RL from acting crazy (Safety Limit)
        self.q_table[self.last_state] = np.clip(new_q, -0.15, 0.15)
        
        print(f"  [RL] {self.symbol} Update: State={self.last_state}, Reward={reward:+.2f}, New Q={self.q_table[self.last_state]:+.4f}")
        self.save_memory() # Save after learning 

class EnsembleStrategy:
    def __init__(self, symbol, sentiment_analyzer=None, smart_money=None):
        self.symbol = symbol
        self.sentiment = sentiment_analyzer
        self.smart_money = smart_money # Shared smart money analyzer
        self.mc = MonteCarloStrategy(symbol)
        self.rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.rl = SafeRLAgent(symbol)
        self.events = EventManager() # Check for earnings
        
        self.rf_path = f"models/{symbol}_rf.pkl"
        self.is_trained = False
        self.load_model()
    
    def load_model(self):
        if os.path.exists(self.rf_path):
            try:
                # Check file age for auto-retraining
                last_modified = os.path.getmtime(self.rf_path)
                file_age = time.time() - last_modified
                max_age = 5 * 86400 # 5 days
                
                if file_age > max_age:
                    print(f"  [RF] Model for {self.symbol} is stale ({file_age/86400:.1f} days old). Forcing retrain.")
                    self.is_trained = False
                    return

                with open(self.rf_path, 'rb') as f:
                    self.rf = pickle.load(f)
                self.is_trained = True
                print(f"  [RF] Loaded Random Forest for {self.symbol}")
            except Exception as e:
                print(f"  [RF] Failed to load RF due to {e}")
                self.is_trained = False

    def save_model(self):
        try:
            with open(self.rf_path, 'wb') as f:
                pickle.dump(self.rf, f)
        except Exception as e:
            print(f"  [RF] Failed to save RF for {self.symbol}: {e}")
        
    def prepare_features(self, df):
        """Enhanced feature engineering with trend, momentum, and volatility indicators."""
        if len(df) < 50:
            return pd.DataFrame()

        df = df.copy()
        
        # === EXISTING FEATURES ===
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['ema_20'] = ta.trend.ema_indicator(df['close'], window=20)
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / (df['volume_ma'] + 1e-6)
        
        # === TREND INDICATORS ===
        # MACD - Moving Average Convergence Divergence
        df['macd'] = ta.trend.macd_diff(df['close'])
        
        # ADX - Average Directional Index (trend strength)
        df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
        
        # EMA Cross (50 vs 20)
        df['ema_50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['ema_cross'] = (df['ema_20'] - df['ema_50']) / df['close']  # Normalized
        
        # === MOMENTUM INDICATORS ===
        # Rate of Change
        df['roc_10'] = ta.momentum.roc(df['close'], window=10)
        
        # Stochastic Oscillator
        df['stoch'] = ta.momentum.stoch(df['high'], df['low'], df['close'], window=14)
        
        # Williams %R
        df['williams_r'] = ta.momentum.williams_r(df['high'], df['low'], df['close'], lbp=14)
        
        # === VOLATILITY INDICATORS ===
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_width'] = bb.bollinger_wband()  # Width of bands
        df['bb_position'] = bb.bollinger_pband()  # Position within bands (0-1)
        
        # Average True Range (volatility)
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
        df['atr_pct'] = df['atr'] / df['close']  # Normalized
        
        # === PRICE PATTERNS ===
        # Higher highs / Lower lows
        df['higher_high'] = (df['high'] > df['high'].shift(1)).astype(int)
        df['lower_low'] = (df['low'] < df['low'].shift(1)).astype(int)
        
        # Price vs moving averages
        df['price_vs_ema20'] = (df['close'] - df['ema_20']) / df['ema_20']
        df['price_vs_ema50'] = (df['close'] - df['ema_50']) / df['ema_50']
        
        # === REGIME DETECTION ===
        # Trending vs Ranging detection using ADX
        # ADX > 25 = Strong trend, ADX < 20 = Ranging
        df['is_trending'] = (df['adx'] > 25).astype(int)
        
        # Trend direction
        df['trend_up'] = ((df['close'] > df['ema_20']) & (df['ema_20'] > df['ema_50'])).astype(int)
        df['trend_down'] = ((df['close'] < df['ema_20']) & (df['ema_20'] < df['ema_50'])).astype(int)
        
        df.dropna(inplace=True)
        return df

    def prepare_training_data(self, df):
        """Prepares features and adds the prediction target for model training."""
        features_df = self.prepare_features(df)
        if features_df.empty:
            return features_df
            
        # === MULTI-DAY TARGET ===
        # Target: Will price be higher 5 days from now by at least 1%?
        # This aligns with multi-day trading strategy (3-5 day holds)
        features_df['future_return'] = features_df['close'].pct_change(5).shift(-5)
        features_df['target'] = (features_df['future_return'] > 0.01).astype(int)  # 1% threshold for daily bars
        
        features_df.dropna(inplace=True)
        return features_df

    def train_rf(self, df):
        """Retrains Random Forest with enhanced feature set."""
        data = self.prepare_training_data(df)
        if data.empty or len(data) < 50: return
        
        # Enhanced feature set with all new indicators
        features = [
            # Original features
            'rsi', 'volatility', 'volume_ratio',
            # Trend indicators
            'macd', 'adx', 'ema_cross',
            # Momentum indicators
            'roc_10', 'stoch', 'williams_r',
            # Volatility indicators
            'bb_width', 'bb_position', 'atr_pct',
            # Price patterns
            'price_vs_ema20', 'price_vs_ema50',
            # Regime features
            'is_trending', 'trend_up', 'trend_down'
        ]
        
        X = data[features]
        y = data['target']
        
        try:
            # Hyperparameter tuning using TimeSeriesSplit to avoid look-ahead bias
            tscv = TimeSeriesSplit(n_splits=3)
            
            param_dist = {
                'n_estimators': [50, 100, 200],
                'max_depth': [3, 5, 7, 10, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'max_features': ['sqrt', 'log2']
            }
            
            rf_base = RandomForestClassifier(random_state=42)
            
            # RandomizedSearchCV for faster tuning compared to GridSearchCV
            search = RandomizedSearchCV(
                estimator=rf_base,
                param_distributions=param_dist,
                n_iter=10,
                cv=tscv,
                scoring='accuracy',
                n_jobs=-1,
                random_state=42
            )
            
            search.fit(X, y)
            self.rf = search.best_estimator_
            
            self.is_trained = True
            self.save_model() # Save after training
            print(f"  [RF] Tuned model for {self.symbol}. Best params: {search.best_params_}")
        except Exception as e:
            print(f"RF training failed for {self.symbol}: {e}")
            self.is_trained = False
    
    def mean_reversion_signal(self, df):
        """Mean reversion strategy for ranging markets."""
        if len(df) < 30:
            return 0.5

        # Calculate z-score (how many std devs from mean)
        close_mean = df['close'].rolling(20).mean().iloc[-1]
        close_std = df['close'].rolling(20).std().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        if close_std == 0:
            return 0.5  # No signal if no volatility
        
        zscore = (current_price - close_mean) / close_std
        
        # RSI confirmation
        rsi = ta.momentum.rsi(df['close'], window=14).iloc[-1]
        
        # Mean reversion logic:
        # Price far above mean + overbought RSI = SELL (expect reversion down)
        # Price far below mean + oversold RSI = BUY (expect reversion up)
        
        if zscore > 2 and rsi > 70:
            # Overbought: High probability of reverting down
            return 0.20  # Strong sell signal
        elif zscore > 1.5 and rsi > 60:
            return 0.35  # Moderate sell signal
        elif zscore < -2 and rsi < 30:
            # Oversold: High probability of reverting up
            return 0.80  # Strong buy signal
        elif zscore < -1.5 and rsi < 40:
            return 0.65  # Moderate buy signal
        else:
            return 0.5  # Neutral

    def analyze(self, df, vix_level=20.0):
        """Enhanced analysis with regime-aware and VIX-aware ensemble."""
        reasons = [] # Initialize reason logging
        
        # 1. Monte Carlo Signal (The Foundation)
        mc_prob = self.mc.run_simulation(df)
        
        # 2. Random Forest Signal (The Pattern Matcher)
        rf_prob = 0.5
        if not self.is_trained:
            self.train_rf(df) # First time train
            
        if self.is_trained:
            # We need to compute features for the current moment
            current_df = self.prepare_features(df.iloc[-100:].copy()) # Last 100 is enough
            if not current_df.empty:
                # Enhanced feature set
                feature_cols = [
                    'rsi', 'volatility', 'volume_ratio',
                    'macd', 'adx', 'ema_cross',
                    'roc_10', 'stoch', 'williams_r',
                    'bb_width', 'bb_position', 'atr_pct',
                    'price_vs_ema20', 'price_vs_ema50',
                    'is_trending', 'trend_up', 'trend_down'
                ]
                # Pass DataFrame to preserve feature names (fixes sklearn warning)
                last_features = current_df.iloc[-1:][feature_cols]
                rf_prob = self.rf.predict_proba(last_features)[0][1] # Probability of Class 1 (Up)
        
        # 3. Mean Reversion Signal (For ranging markets)
        mr_prob = self.mean_reversion_signal(df)
        
        # 4. Regime Detection
        if len(df) < 30:
            is_trending = False
            is_ranging = False
        else:
            adx = ta.trend.adx(df['high'], df['low'], df['close'], window=14).iloc[-1]
            is_trending = adx > 25
            is_ranging = adx < 20
            
        # Log raw model scores for transparency
        reasons.append(f"MC: {mc_prob:.2f}")
        reasons.append(f"RF: {rf_prob:.2f}")
        reasons.append(f"MR: {mr_prob:.2f}")
        
        # 5. RL Adjustment (The Learning Advisor)
        current_price = df['close'].iloc[-1]
        if len(df) < 30:
            ema = current_price
            rsi = 50.0
        else:
            ema = ta.trend.ema_indicator(df['close'], window=20).iloc[-1]
            rsi = ta.momentum.rsi(df['close'], window=14).iloc[-1]
            
        trend = 1 if current_price > ema else -1
        
        rl_state = self.rl.get_state(rsi, trend)
        rl_adj = self.rl.get_adjustment(rl_state)
        self.rl.last_state = rl_state # Save for next update cycle
        
        # --- VIX-AWARE MODEL WEIGHTING ---
        # Low VIX (< 15): Trust Trends (RF)
        # High VIX (> 25): Trust Volatility Simulation (MC)
        if vix_level > 25:
             w_mc, w_rf, w_mr = 0.60, 0.30, 0.10
             vix_state = "FEAR"
        elif vix_level < 15:
             w_mc, w_rf, w_mr = 0.30, 0.60, 0.10
             vix_state = "CALM"
        else:
             w_mc, w_rf, w_mr = 0.45, 0.45, 0.10
             vix_state = "NORMAL"

        # --- REGIME-AWARE ENSEMBLE VOTING ---
        if is_trending:
            # In trending markets: Ignore Mean Reversion
            # Normalize w_mc and w_rf to sum to 1.0
            sum_w = w_mc + w_rf
            base_confidence = ((w_mc/sum_w) * mc_prob) + ((w_rf/sum_w) * rf_prob)
            regime_type = f'TREND ({vix_state})'
        elif is_ranging:
            # In ranging markets: Keep weights as defined (includes MR)
            base_confidence = (w_mc * mc_prob) + (w_rf * rf_prob) + (w_mr * mr_prob)
            
            # --- SIDEWAYS PENALTY ---
            # Penalize confidence in sideways markets to avoid "Death by a Thousand Cuts"
            penalty = getattr(config, 'SIDEWAYS_REGIME_PENALTY', 0.05)
            if base_confidence > 0.5:
                base_confidence -= penalty
            else:
                base_confidence += penalty
            
            regime_type = f'RANGE ({vix_state})'
            reasons.append(f"Regime: {regime_type} (Penalty Applied)")
        else:
            # Unclear regime: Balanced but biased by VIX
            base_confidence = (w_mc * mc_prob) + (w_rf * rf_prob) + (w_mr * mr_prob)
            regime_type = f'MIXED ({vix_state})'
            
        reasons.append(f"Regime: {regime_type}")
        reasons.append(f"Base: {base_confidence:.2f}")
        
        # 4. SENTIMENT VETO (Multi-tier weighted — all thresholds from config)
        # -----------------------------------------------
        news_meta = None
        if self.sentiment:
            sentiment_score, news_meta = self.sentiment.analyze_sentiment(self.symbol)
        else:
            sentiment_score = 0

        sent_veto    = getattr(config, 'SENTIMENT_VETO_THRESHOLD',  -0.2)
        sent_boost   = getattr(config, 'SENTIMENT_BOOST_THRESHOLD',  0.2)
        sent_amount  = getattr(config, 'SENTIMENT_BOOST_AMOUNT',     0.1)
        sent_hard_veto = getattr(config, 'SENTIMENT_HARD_VETO_THRESHOLD', -0.6)
        sent_penalty_scale = getattr(config, 'SENTIMENT_PENALTY_SCALE', 0.5)

        if sentiment_score < sent_hard_veto:
            # HARD VETO: Extreme negative sentiment forces hold — no trading allowed
            reasons.append(f"Sent: {sentiment_score:.2f} (HARD VETO)")
            return 'hold', 0.5, " | ".join(reasons), news_meta
        elif sentiment_score < sent_veto:
            # Proportional penalty: worse sentiment = bigger confidence reduction
            penalty = abs(sentiment_score) * sent_penalty_scale
            base_confidence -= penalty
            reasons.append(f"Sent: {sentiment_score:.2f} (NEG -{penalty:.2f})")
        elif sentiment_score > sent_boost:
            base_confidence += sent_amount
            reasons.append(f"Sent: {sentiment_score:.2f} (POS)")
        else:
            reasons.append(f"Sent: {sentiment_score:.2f}")

        # 5. SMART MONEY (Insider Cluster Buying — all thresholds from config)
        # -----------------------------------------------
        sm_score = 0
        if self.smart_money:
            sm_score = self.smart_money.get_signal(self.symbol)
            sm_buy_thresh  = getattr(config, 'SM_STRONG_BUY_THRESHOLD',    0.5)
            sm_sell_thresh = getattr(config, 'SM_STRONG_SELL_THRESHOLD',   -0.5)
            sm_buy_boost   = getattr(config, 'SM_BUY_CONFIDENCE_BOOST',    0.15)
            sm_sell_pen    = getattr(config, 'SM_SELL_CONFIDENCE_PENALTY',  0.10)
            if sm_score > sm_buy_thresh:
                base_confidence += sm_buy_boost
                reasons.append(f"Whale: {sm_score:.2f} (POS)")
            elif sm_score < sm_sell_thresh:
                base_confidence -= sm_sell_pen
                reasons.append(f"Whale: {sm_score:.2f} (NEG)")
            else:
                reasons.append(f"Whale: {sm_score:.2f}")

        # -----------------------------------------------
        # 6. REINFORCEMENT LEARNING ADJUSTMENT (Applied earlier)
        # -----------------------------------------------
        reasons.append(f"RL: {rl_adj:+.2f}")
        
        # 7. EARNINGS VETO
        # -----------------------------------------------
        is_near_earnings, earnings_date = self.events.is_near_earnings(self.symbol)
        if is_near_earnings:
            date_str = earnings_date.strftime("%Y-%m-%d")
            reasons.append(f"EARNINGS ({date_str}) - VETO")
            # If near earnings, we force a 'hold' by returning early or zeroing confidence
            # In institutional trading, we often close 1-2 days before.
            return 'hold', 0.5, " | ".join(reasons), news_meta

        final_confidence = base_confidence + rl_adj
        
        # Clip confidence to 0-1
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        # Combine reasons
        reason_str = " | ".join(reasons)
        
        # === DECISION LOGIC WITH VOLATILITY-AWARE QUALITY FILTER ===
        # Buy Threshold: 60% (Config)
        # Sell/Short Threshold: 40% (Config)
        
        # 1. Calculate Dynamic Confidence Gap
        # If VIX is high, we require MORE conviction (higher gap)
        base_gap = getattr(config, 'MIN_CONFIDENCE_GAP', 0.10)
        vix_threshold = getattr(config, 'VIX_THRESHOLD_HIGH', 25.0)
        gap_multiplier = getattr(config, 'DYNAMIC_GAP_MULTIPLIER', 1.5)
        
        dynamic_gap = base_gap
        if vix_level > vix_threshold:
            dynamic_gap = base_gap * gap_multiplier
            reasons.append(f"VIX Protected (Gap: {dynamic_gap:.2f})")
            # Re-generate reason_str to include protection log
            reason_str = " | ".join(reasons)

        # 2. Calculate "Conviction" (distance from neutral 0.50)
        conviction = abs(final_confidence - 0.5)

        # --- ALPHA BOOSTER: CONFIRMATION OVER CONVICTION ---
        # If confidence is slightly low, allow it IF confirmed by Sentiment or Smart Money.
        # Thresholds come from config (tunable by PortfolioTuner).
        is_confirmed = False
        alpha_sent_threshold   = getattr(config, 'SENTIMENT_BOOST_THRESHOLD', 0.2) * 0.5  # Half of boost level
        alpha_insider_threshold = getattr(config, 'SM_ALPHA_CONFIRM_THRESHOLD', 0.3)
        if 0.55 <= final_confidence <= config.CONFIDENCE_THRESHOLD_BUY:
            sentiment_ok = sentiment_score > alpha_sent_threshold
            insider_ok   = sm_score > alpha_insider_threshold
            if sentiment_ok or insider_ok:
                is_confirmed = True
                reasons.append("ALPHA: CONFIRMED ENTRY")
                reason_str = " | ".join(reasons)

        if (final_confidence > config.CONFIDENCE_THRESHOLD_BUY and conviction >= dynamic_gap) or is_confirmed:
            return 'buy', final_confidence, reason_str, news_meta
        elif final_confidence < config.CONFIDENCE_THRESHOLD_SELL and conviction >= dynamic_gap:
            return 'sell', final_confidence, reason_str, news_meta
        
        return 'hold', final_confidence, reason_str, news_meta

    def update_rl(self, profit_pnl):
        """
        Called after a trade is closed to teach the RL agent.
        profit_pnl: Positive for win, Negative for loss.
        """
        # Reward: +1 for profit, -1 for loss
        reward = 1.0 if profit_pnl > 0 else -1.0
        self.rl.update(reward)
