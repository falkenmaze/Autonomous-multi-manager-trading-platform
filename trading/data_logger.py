
import json
import os
import pandas as pd
from datetime import datetime
from trading.performance_metrics import PerformanceCalculator
from trading.alpaca_client import AlpacaClient

class DataLogger:
    def __init__(self, log_dir="logs", client=None):
        self.log_dir = log_dir
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            self.history_file = os.path.join(log_dir, "portfolio_history.json")
            self.latest_state_file = os.path.join(log_dir, "latest_state.json")
            self.trades_file = os.path.join(log_dir, "trades.json")
        else:
            self.history_file = None
            self.latest_state_file = None
            self.trades_file = None
        
        # Use provided client or create new one
        self.client = client if client else AlpacaClient()
        
        # Performance calculator
        self.perf_calc = PerformanceCalculator()
        self._load_trades()
        
        # Benchmark cache
        self.spy_cache = None
        self.spy_cache_time = None

    def _load_trades(self):
        """Load historical trades for win rate calculation."""
        if self.trades_file and os.path.exists(self.trades_file):
            try:
                with open(self.trades_file, 'r') as f:
                    self.perf_calc.trades = json.load(f)
            except:
                self.perf_calc.trades = []
    
    def _save_trades(self):
        """Save trades log."""
        if self.trades_file:
            with open(self.trades_file, 'w') as f:
                json.dump(self.perf_calc.trades, f, indent=4)
    
    def log_trade(self, symbol, entry_price, exit_price, qty, side):
        """
        Log a completed trade.
        
        Args:
            symbol: Stock ticker
            entry_price: Entry price
            exit_price: Exit price
            qty: Quantity
            side: 'long' or 'short'
        """
        self.perf_calc.log_trade(symbol, entry_price, exit_price, qty, side)
        self._save_trades()
        print(f"  [Logger] Trade logged: {symbol} {side} PnL: ${(exit_price - entry_price) * qty if side == 'long' else (entry_price - exit_price) * qty:.2f}")
    
    def _get_spy_returns(self, days_back=180):
        """
        Fetch SPY returns for benchmark comparison.
        Cache for 1 hour to avoid excessive API calls.
        """
        now = datetime.now()
        
        # Check cache
        if self.spy_cache is not None and self.spy_cache_time is not None:
            if (now - self.spy_cache_time).seconds < 3600:  # 1 hour
                return self.spy_cache
        
        try:
            # Fetch SPY data using Alpaca (Reliable, no rate limits for this volume)
            spy_df = self.client.get_historical_data('SPY', lookback_days=days_back)
            
            if not spy_df.empty:
                # Alpaca get_historical_data returns a DataFrame with 'close' column
                # Calculate returns
                spy_returns = spy_df['close'].pct_change().dropna()
                
                self.spy_cache = spy_returns
                self.spy_cache_time = now
                return spy_returns
                
        except Exception as e:
            print(f"  [Logger] Error fetching SPY data: {e}")
        
        return pd.Series()

    def log_cycle(self, cycle_data: dict):
        """
        Appends cycle data to history, calculates performance metrics, and overwrites latest state.
        cycle_data should include: timestamp, equity, cash, positions, signals.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cycle_data['timestamp'] = timestamp

        # 1. Update History
        history = []
        if self.history_file and os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append({
            'timestamp': timestamp,
            'equity': cycle_data.get('equity', 0),
            'cash': cycle_data.get('cash', 0)
        })
        
        # Keep history reasonable (last 1000 data points)
        if len(history) > 1000:
            history = history[-1000:]

        if self.history_file:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=4)
        
        # 2. Calculate Performance Metrics
        try:
            history_df = pd.DataFrame(history)
            
            if not history_df.empty and len(history_df) >= 2:
                # Get SPY returns for alpha calculation
                spy_returns = self._get_spy_returns()
                
                # Calculate all metrics
                metrics = self.perf_calc.get_all_metrics(history_df, spy_returns)
                
                # Add to cycle data
                cycle_data['performance_metrics'] = metrics
            else:
                # Not enough data yet
                cycle_data['performance_metrics'] = {
                    'sharpe_ratio': 0.0,
                    'max_drawdown': 0.0,
                    'current_drawdown': 0.0,
                    'win_rate': 0.0,
                    'total_return': 0.0,
                    'total_return_pct': 0.0,
                    'volatility': 0.0,
                    'alpha': 0.0,
                    'total_trades': 0,
                    'profit_factor': 0.0
                }
        except Exception as e:
            print(f"  [Logger] Error calculating performance metrics: {e}")
            # Set default metrics on error
            cycle_data['performance_metrics'] = {
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'current_drawdown': 0.0,
                'win_rate': 0.0,
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'volatility': 0.0,
                'alpha': 0.0,
                'total_trades': 0,
                'profit_factor': 0.0
            }

        # 3. Save Latest Detailed State
        if self.latest_state_file:
            with open(self.latest_state_file, 'w') as f:
                json.dump(cycle_data, f, indent=4)

        print(f"  [Logger] Cycle data persisted to {self.log_dir}")
