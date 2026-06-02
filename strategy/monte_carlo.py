import numpy as np
import pandas as pd
import ta
import config

class MonteCarloStrategy:
    def __init__(self, symbol):
        self.symbol = symbol
        self.simulations = 1000
        self.time_horizon = 5  # Simulate next 5 trading days (multi-day strategy)
        
    def prepare_technical_indicators(self, df: pd.DataFrame):
        """Adds RSI and EMA to dataframe."""
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['ema_20'] = ta.trend.ema_indicator(df['close'], window=20)
        return df

    def run_simulation(self, df: pd.DataFrame):
        """
        Runs Geometric Brownian Motion (GBM) simulation.
        Returns: Probability of Price Increase (0.0 - 1.0)
        """
        if len(df) < 50:
            return 0.5

        # Calculate Log Returns
        log_returns = np.log(1 + df['close'].pct_change())
        
        # Calculate Drift and Volatility (scaled to minutes)
        u = log_returns.mean()
        var = log_returns.var()
        drift = u - (0.5 * var)
        stdev = log_returns.std()
        
        # Current Price
        last_price = df['close'].iloc[-1]
        
        # Monte Carlo Simulation
        # Formula: S_t = S_0 * exp((drift) + stdev * Z)
        daily_returns = np.exp(drift + stdev * np.random.normal(0, 1, (self.time_horizon, self.simulations)))
        
        price_paths = np.zeros_like(daily_returns)
        price_paths[0] = last_price
        
        for t in range(1, self.time_horizon):
            price_paths[t] = price_paths[t-1] * daily_returns[t]
            
        # Analysis
        final_prices = price_paths[-1]
        wins = len(final_prices[final_prices > last_price])
        probability = wins / self.simulations
        
        return probability

    def analyze(self, df: pd.DataFrame):
        """
        Main analysis function.
        Combines Monte Carlo Probability + Technical Analysis.
        Returns: 'buy', 'sell', or 'hold' and the probability/reason confidence.
        """
        # 1. Technical Indicators
        df = self.prepare_technical_indicators(df)
        last_row = df.iloc[-1]
        
        current_rsi = last_row['rsi']
        current_price = last_row['close']
        current_ema = last_row['ema_20']
        
        # 2. Monte Carlo Probability
        mc_prob = self.run_simulation(df)
        
        print(f"Stats for {self.symbol}: MC_Prob={mc_prob:.2f}, RSI={current_rsi:.2f}, Price={current_price:.2f}, EMA={current_ema:.2f}")

        # 3. Hybrid Decision Logic
        # BUY SIGNAL
        if mc_prob > 0.60:
            # Tech Check: Not Overbought AND Uptrend
            if current_rsi < 70 and current_price > current_ema:
                return 'buy', mc_prob
        
        # SELL SIGNAL
        if mc_prob < 0.40:
            # Tech Check: Not Oversold AND Downtrend (or just take heavy probability)
            if current_rsi > 30 and current_price < current_ema:
                return 'sell', mc_prob
                
        return 'hold', mc_prob
