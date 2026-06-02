import numpy as np
import pandas as pd
from datetime import datetime, timedelta

class PerformanceCalculator:
    """
    Calculates hedge fund-grade performance metrics.
    """
    
    def __init__(self):
        self.trades = []  # List of completed trades
        
    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """
        Calculate annualized Sharpe Ratio.
        
        Args:
            returns: Series or array of returns (daily)
            risk_free_rate: Annual risk-free rate (default 2%)
        
        Returns:
            float: Annualized Sharpe Ratio
        """
        if len(returns) < 2:
            return 0.0
            
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        
        if excess_returns.std() == 0:
            return 0.0
            
        sharpe = excess_returns.mean() / excess_returns.std()
        annualized_sharpe = sharpe * np.sqrt(252)  # Annualize
        
        return annualized_sharpe
    
    def calculate_max_drawdown(self, equity_curve):
        """
        Calculate maximum drawdown from equity curve.
        
        Args:
            equity_curve: Series or array of portfolio values
        
        Returns:
            tuple: (max_drawdown_pct, current_drawdown_pct, peak_value)
        """
        if len(equity_curve) < 2:
            return 0.0, 0.0, equity_curve[-1] if len(equity_curve) > 0 else 0
        
        # Convert to numpy array
        if isinstance(equity_curve, pd.Series):
            equity_curve = equity_curve.values
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_curve)
        
        # Calculate drawdown at each point
        drawdowns = (equity_curve - running_max) / running_max
        
        max_drawdown = drawdowns.min()  # Most negative = largest drawdown
        current_drawdown = drawdowns[-1]
        peak_value = running_max[-1]
        
        return max_drawdown, current_drawdown, peak_value
    
    def calculate_win_rate(self, trades=None):
        """
        Calculate win rate from completed trades.
        
        Args:
            trades: List of trade dicts with 'pnl' key, or None to use self.trades
        
        Returns:
            dict: {'win_rate': %, 'total_trades': int, 'wins': int, 'losses': int}
        """
        if trades is None:
            trades = self.trades
            
        if not trades:
            return {
                'win_rate': 0.0,
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'avg_win': 0.0,
                'avg_loss': 0.0
            }
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        
        win_rate = (len(wins) / len(trades)) * 100 if trades else 0
        
        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
        
        return {
            'win_rate': win_rate,
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }
    
    def calculate_alpha(self, portfolio_returns, benchmark_returns):
        """
        Calculate alpha (excess return vs benchmark).
        
        Args:
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark (SPY) returns
        
        Returns:
            float: Annualized alpha
        """
        try:
            if len(portfolio_returns) < 2 or len(benchmark_returns) < 2:
                return 0.0
            
            # Flatten if ndarray with wrong shape
            if isinstance(portfolio_returns, np.ndarray):
                portfolio_returns = portfolio_returns.flatten()
            if isinstance(benchmark_returns, np.ndarray):
                benchmark_returns = benchmark_returns.flatten()
            
            # Convert to Series if needed
            if not isinstance(portfolio_returns, pd.Series):
                portfolio_returns = pd.Series(portfolio_returns)
            if not isinstance(benchmark_returns, pd.Series):
                benchmark_returns = pd.Series(benchmark_returns)
            
            # Align by date index if both have datetime index
            # Otherwise, align by position (most recent N days)
            min_len = min(len(portfolio_returns), len(benchmark_returns))
            
            if min_len < 2:
                return 0.0
            
            # Take the most recent matching period
            port_ret = portfolio_returns.tail(min_len).values.flatten()
            bench_ret = benchmark_returns.tail(min_len).values.flatten()
            
            if len(port_ret) != len(bench_ret):
                return 0.0
            
            # Calculate beta using covariance
            cov_matrix = np.cov(port_ret, bench_ret)
            
            if cov_matrix.shape != (2, 2):
                return 0.0
                
            covariance = cov_matrix[0, 1]
            benchmark_variance = cov_matrix[1, 1]
            
            if benchmark_variance == 0:
                beta = 1.0
            else:
                beta = covariance / benchmark_variance
            
            # Calculate alpha
            portfolio_mean = np.mean(port_ret) * 252  # Annualize
            benchmark_mean = np.mean(bench_ret) * 252  # Annualize
            
            alpha = portfolio_mean - (beta * benchmark_mean)
            
            return alpha
            
        except Exception as e:
            print(f"  [Alpha] Error calculating alpha: {e}")
            return 0.0
    
    def calculate_volatility(self, returns):
        """
        Calculate annualized volatility.
        
        Args:
            returns: Series or array of daily returns
        
        Returns:
            float: Annualized volatility (%)
        """
        if len(returns) < 2:
            return 0.0
        
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        return annual_vol * 100  # As percentage
    
    def calculate_profit_factor(self, trades=None):
        """
        Calculate profit factor (gross profit / gross loss).
        
        Args:
            trades: List of trade dicts with 'pnl' key
        
        Returns:
            float: Profit factor
        """
        if trades is None:
            trades = self.trades
            
        if not trades:
            return 0.0
        
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def log_trade(self, symbol, entry_price, exit_price, qty, side):
        """
        Log a completed trade for win rate tracking.
        
        Args:
            symbol: Stock ticker
            entry_price: Entry price
            exit_price: Exit price
            qty: Quantity
            side: 'long' or 'short'
        """
        if side == 'long':
            pnl = (exit_price - entry_price) * qty
        else:  # short
            pnl = (entry_price - exit_price) * qty
        
        self.trades.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'pnl': pnl,
            'side': side,
            'qty': qty
        })
    
    def get_all_metrics(self, history_df, benchmark_returns=None):
        """
        Calculate all metrics at once.
        
        Args:
            history_df: DataFrame with 'timestamp', 'equity', 'cash' columns
            benchmark_returns: Optional Series of benchmark returns
        
        Returns:
            dict: All performance metrics
        """
        if history_df.empty or len(history_df) < 2:
            return {
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
        
        equity = history_df['equity']
        
        # Calculate returns
        returns = equity.pct_change().dropna()
        
        # Total return
        starting_equity = equity.iloc[0]
        current_equity = equity.iloc[-1]
        total_return = current_equity - starting_equity
        total_return_pct = (total_return / starting_equity) * 100
        
        # Sharpe
        sharpe = self.calculate_sharpe_ratio(returns)
        
        # Drawdown
        max_dd, curr_dd, peak = self.calculate_max_drawdown(equity)
        
        # Win rate
        win_stats = self.calculate_win_rate()
        
        # Volatility
        vol = self.calculate_volatility(returns)
        
        # Alpha
        alpha = 0.0
        if benchmark_returns is not None and not benchmark_returns.empty:
            alpha = self.calculate_alpha(returns, benchmark_returns)
        
        # Profit factor
        pf = self.calculate_profit_factor()
        
        return {
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd * 100,  # As percentage
            'current_drawdown': curr_dd * 100,
            'win_rate': win_stats['win_rate'],
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'volatility': vol,
            'alpha': alpha * 100,  # As percentage
            'total_trades': win_stats['total_trades'],
            'wins': win_stats['wins'],
            'losses': win_stats['losses'],
            'avg_win': win_stats['avg_win'],
            'avg_loss': win_stats['avg_loss'],
            'profit_factor': pf,
            'peak_equity': peak
        }
