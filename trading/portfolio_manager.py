import numpy as np
import pandas as pd
import time
from scipy.optimize import minimize
import scipy.cluster.hierarchy as sch
import scipy.spatial.distance as ssd
from trading.sector_manager import SectorManager
from trading.macro_manager import MacroManager
import config

class PortfolioManager:
    def __init__(self, client, sector_manager=None, macro_manager=None):
        self.client = client
        self.sector_manager = sector_manager or SectorManager()
        self.macro_manager = macro_manager or MacroManager()
        self.spy_symbol = 'SPY'
        self.beta_cache = {} # Map symbol -> (beta, timestamp)

    def _get_sector_exposure(self, positions, total_equity):
        """Calculates current % exposure per sector."""
        exposure = {} # sector -> dollar_val
        for p in positions:
            if p.symbol == self.spy_symbol: continue
            sector = self.sector_manager.get_sector(p.symbol)
            val = float(p.market_value)
            exposure[sector] = exposure.get(sector, 0) + val
            
        # Convert to % of equity
        pct_exposure = {s: v / (total_equity + 1e-6) for s, v in exposure.items()}
        return pct_exposure

    def calculate_position_size(self, symbol, price, volatility, total_equity):
        """
        Calculates position size based on Volatility Targeting.
        High Volatility -> Smaller Size.
        """
        # Base allocation: 5% of equity
        base_allocation = total_equity * 0.05
        
        # Volatility Adjustment (Inverse Volatility)
        # If vol is high (e.g. 0.02 daily), multiplier is lower
        # Standard vol reference = 0.01 (1%)
        vol_multiplier = 0.01 / (volatility + 1e-6) 
        vol_multiplier = np.clip(vol_multiplier, 0.5, 2.0) # Cap multiplier between 0.5x and 2x
        
        allocation = base_allocation * vol_multiplier
        qty = int(allocation // price)
        
        return max(1, qty) # Always buy at least 1

    def get_real_time_beta(self, symbol):
        """
        Calculates Beta dynamically by comparing asset returns vs SPY returns.
        Uses 180-day lookback.
        """
        # 1. Check Cache (Valid for 24 hours - Beta drift is slow)
        current_time = time.time()
        if symbol in self.beta_cache:
            cached_beta, cached_ts = self.beta_cache[symbol]
            if current_time - cached_ts < 86400: # 1 day
                return cached_beta

        try:
            # 2. Fetch Data
            # We need synchronized dates, so we fetch both.
            asset_df = self.client.get_historical_data(symbol, lookback_days=180)
            spy_df = self.client.get_historical_data(self.spy_symbol, lookback_days=180)
            
            if asset_df.empty or spy_df.empty:
                print(f"  [Beta] Missing data for {symbol} or SPY. Defaulting to 1.0")
                return 1.0
            
            # 3. Align Data (Inner Join on Date)
            # Alpaca returns MultiIndex (symbol, timestamp). We must match on timestamp only.
            asset_ret = asset_df['close'].reset_index(level=0, drop=True).pct_change().dropna()
            spy_ret = spy_df['close'].reset_index(level=0, drop=True).pct_change().dropna()
            
            # Align by index (timestamp)
            data = pd.DataFrame({'asset': asset_ret, 'spy': spy_ret}).dropna()
            
            if len(data) < 30: # Not enough overlapping data
                 print(f"  [Beta] Insufficient overlapping data for {symbol}. Defaulting to 1.0")
                 return 1.0

            # 4. Calculate Beta = Cov(asset, spy) / Var(spy)
            # Covariance matrix: [[Var(asset), Cov(a,s)], [Cov(s,a), Var(spy)]]
            # rowvar=False because variables are columns (asset, spy)
            cov_matrix = np.cov(data['asset'], data['spy'], rowvar=False) 
            covariance = cov_matrix[0, 1]
            variance_spy = cov_matrix[1, 1]
            
            if variance_spy == 0:
                print(f"  [Beta] SPY Variance is 0. Defaulting to 1.0")
                return 1.0
                
            beta = covariance / variance_spy
            
            # 5. Cache it
            print(f"  [Beta] Calculated {symbol} Beta: {beta:.2f} (Correlation: {data.corr().iloc[0,1]:.2f})")
            self.beta_cache[symbol] = (beta, current_time)
            return beta
            
        except Exception as e:
            print(f"  [Beta] Error calculating for {symbol}: {e}. Defaulting to 1.2")
            return 1.2

    def calculate_portfolio_beta(self, positions):
        """
        Estimates portfolio beta using Real-Time calculations.
        Returns: (portfolio_beta_relative_to_value, total_value, total_weighted_beta_dollars)
        """
        total_weighted_beta = 0
        total_value = 0
        
        print("\n--- Calculating Portfolio Beta ---")
        
        for p in positions:
            symbol = p.symbol
            if symbol == 'SPY': continue # Don't count the hedge itself yet
            
            qty = float(p.qty)
            price = float(p.current_price)
            val = qty * price
            
            # Dynamic Beta Calculation
            beta = self.get_real_time_beta(symbol)
            
            total_weighted_beta += (val * beta)
            total_value += val
            
            # print(f"  {symbol}: Val=${val:.0f} x Beta {beta:.2f} = Exp ${val*beta:.0f}")
        
        # Avoid Division by Zero
        if total_value == 0:
            portfolio_beta = 0
        else:
            portfolio_beta = total_weighted_beta / total_value
            
        return portfolio_beta, total_value, total_weighted_beta

    def _get_dynamic_sector_limits(self, sector_name, bias):
        """
        Returns the maximum portfolio exposure allowed for a sector.
        Adjusts based on Macro Bias (Defensive vs GROWTH).
        """
        # Default limit is 30%
        base_limit = 0.30
        
        if bias == "DEFENSIVE":
            # Boost caps for safe havens
            if sector_name in ["Healthcare", "Utilities", "Consumer Defensive"]:
                return 0.45
            # Tighten caps for Cyclicals/Tech
            elif sector_name in ["Technology", "Communication Services", "Consumer Cyclical"]:
                return 0.15
        
        elif bias == "INFLATIONARY":
            # Boost Energy/Materials
            if sector_name in ["Energy", "Basic Materials"]:
                return 0.45
                
        return base_limit

    def optimize_allocations(self, potential_buys, total_equity, confidence_scores=None):
        """
        Uses Markowitz Mean-Variance Optimization to allocate capital cleaner.
        Includes Macro-Aware dynamic sector caps.
        """
        if not potential_buys:
            return {}
            
        strategy = getattr(config, 'ALLOCATION_STRATEGY', 'MVO')
        print(f"\n--- Running {strategy} Optimization for {potential_buys} ---")
        
        # 0. Get Macro Bias and Sector Constraints
        bias = self.macro_manager.get_market_bias()
        positions = self.client.get_positions()
        current_sector_exposure = self._get_sector_exposure(positions, total_equity)
        
        # 1. Fetch History and Sectors
        data_frames = {}
        valid_buy_sectors = {}
        for symbol in potential_buys:
            try:
                sector = self.sector_manager.get_sector(symbol)
                valid_buy_sectors[symbol] = sector
                
                df = self.client.get_historical_data(symbol, lookback_days=90)
                if not df.empty:
                    data_frames[symbol] = df['close'].pct_change().dropna()
            except Exception as e:
                print(f"MVO Error fetching {symbol}: {e}")
                
        valid_symbols = list(data_frames.keys())
        if not valid_symbols:
            return {}
            
        if len(valid_symbols) == 1:
            sym = valid_symbols[0]
            sector = valid_buy_sectors[sym]
            existing_exp = current_sector_exposure.get(sector, 0.0)
            limit = self._get_dynamic_sector_limits(sector, bias)
            
            if existing_exp > limit:
                print(f"  [Sector Guard] Skipping {sym}: Sector {sector} already at {existing_exp:.1%} exposure (Limit: {limit:.1%}).")
                return {}
            
            print(f"MVO: Only one asset {sym}, allocating max safe amount.")
            vol = data_frames[sym].std()
            recent_data = self.client.get_historical_data(sym, lookback_days=5)
            if recent_data.empty: return {}
            price = recent_data.iloc[-1]['close']
            qty = self.calculate_position_size(sym, price, vol, total_equity)
            return {sym: qty}

        # 2. Setup Optimizer
        price_matrix = pd.DataFrame(data_frames).dropna()
        if len(price_matrix) < 30:
             return {s: int((total_equity * 0.05) // 100) for s in valid_symbols}
            
        returns_mean = price_matrix.mean()
        cov_matrix = price_matrix.cov()
        
        if strategy == "RISK_PARITY":
            return self.calculate_risk_parity(valid_symbols, price_matrix, total_equity, valid_buy_sectors, current_sector_exposure, bias)
        elif strategy == "HRP":
            return self.calculate_hrp(valid_symbols, price_matrix, total_equity, valid_buy_sectors, current_sector_exposure, bias, confidence_scores)
        
        def negative_sortino(weights):
            portfolio_return = np.sum(returns_mean * weights) * 252
            # Calculate daily returns for the weighted portfolio
            port_daily_returns = np.dot(price_matrix, weights)
            # Downside deviation (returns < 0)
            downside_returns = port_daily_returns[port_daily_returns < 0]
            if len(downside_returns) > 0:
                downside_vol = np.sqrt(np.mean(downside_returns**2)) * np.sqrt(252)
            else:
                downside_vol = 1e-6
            return - (portfolio_return / downside_vol) if downside_vol > 0 else 0
            
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        pot_size_pct = 0.25 
        
        limit_sectors = set(valid_buy_sectors.values())
        for sector_name in limit_sectors:
            limit = self._get_dynamic_sector_limits(sector_name, bias)
            
            def sector_limit_func(weights, s_name=sector_name, current_limit=limit):
                sector_weight = 0
                for i, sym in enumerate(valid_symbols):
                    if valid_buy_sectors[sym] == s_name:
                        sector_weight += weights[i]
                
                total_new_exp = current_sector_exposure.get(s_name, 0.0) + (sector_weight * pot_size_pct)
                return current_limit - total_new_exp
            
            constraints.append({'type': 'ineq', 'fun': sector_limit_func})

        bounds = tuple((0, 1) for _ in range(len(valid_symbols))) 
        initial_guess = [1./len(valid_symbols)] * len(valid_symbols)
        
        result = minimize(negative_sortino, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
        valid_weights = result.x
        
        # 3. Convert Weights to Quantities
        allocation_map = {}
        for i, symbol in enumerate(valid_symbols):
            weight = valid_weights[i]
            if weight < 0.01: continue
            
            ticker_data = self.client.get_historical_data(symbol, lookback_days=5)
            if ticker_data.empty: continue
            price = ticker_data['close'].iloc[-1]
            
            dollar_amt = (total_equity * pot_size_pct) * weight
            
            if confidence_scores and symbol in confidence_scores:
                conf = confidence_scores[symbol]
                multiplier = 1.0
                if conf >= config.CONVICTION_BOOST_LEVEL_2: multiplier = 2.0
                elif conf >= config.CONVICTION_BOOST_LEVEL_1: multiplier = 1.5
                dollar_amt *= multiplier

            dollar_amt = min(dollar_amt, total_equity * 0.15) 
            qty = int(dollar_amt // price)
            if qty > 0:
                print(f"  MVO Allocation {symbol} ({valid_buy_sectors[symbol]}): {weight:.2%} -> ${dollar_amt:.0f} ({qty} shares)")
                allocation_map[symbol] = qty
                
        return allocation_map

    def calculate_risk_parity(self, symbols, price_matrix, total_equity, sectors, current_sector_exp, bias="GROWTH"):
        """
        Calculates Risk Parity weights with Macro-Aware sector limits.
        """
        volatilities = price_matrix.std() * np.sqrt(252)
        inv_vols = 1.0 / (volatilities + 1e-6)
        weights = inv_vols / inv_vols.sum()
        
        pot_size = total_equity * 0.25
        allocation_map = {}
        
        for symbol, weight in weights.items():
            sector = sectors[symbol]
            limit = self._get_dynamic_sector_limits(sector, bias)
            existing_exp = current_sector_exp.get(sector, 0.0)
            
            dollar_amt = pot_size * weight
            
            # Use dynamic limit check
            if (existing_exp + (dollar_amt / total_equity)) > limit:
                print(f"  [Risk Parity] Clipping {symbol}: Sector {sector} limit reached ({limit:.1%}).")
                dollar_amt = max(0, (limit - existing_exp) * total_equity)
            
            dollar_amt = min(dollar_amt, total_equity * 0.15)
            
            ticker_data = self.client.get_historical_data(symbol, lookback_days=1)
            if ticker_data.empty: continue
            current_price = ticker_data['close'].iloc[-1]
            
            qty = int(dollar_amt // current_price)
            if qty > 0:
                print(f"  Risk Parity Allocation {symbol} ({sector}): {weight:.2%} -> ${dollar_amt:.0f} ({qty} shares)")
                allocation_map[symbol] = qty
                
        return allocation_map

    def calculate_hrp(self, symbols, price_matrix, total_equity, sectors, current_sector_exp, bias="GROWTH", confidence_scores=None):
        """
        Calculates Hierarchical Risk Parity (HRP) weights with conviction scaling and sector caps.
        """
        # 1. Calculate Covariance & Correlation Matrix
        cov = price_matrix.cov()
        corr = price_matrix.corr().fillna(0)
        
        # 2. Compute Distance Matrix D and Column Distance Matrix tilde_D
        # D(i, j) = sqrt((1 - corr(i, j)) / 2)
        d_mat = np.sqrt(np.clip((1.0 - corr.values) / 2.0, 0.0, 1.0))
        num_assets = d_mat.shape[0]
        tilde_d = np.zeros((num_assets, num_assets))
        for i in range(num_assets):
            for j in range(num_assets):
                tilde_d[i, j] = np.sqrt(np.sum((d_mat[:, i] - d_mat[:, j])**2))
                
        # 3. Perform Hierarchical Agglomerative Clustering
        linkage_method = getattr(config, 'HRP_LINKAGE_METHOD', 'single')
        condensed_d = ssd.squareform(tilde_d, checks=False)
        linkage = sch.linkage(condensed_d, method=linkage_method)
        
        # 4. Quasi-Diagonalization
        ordered_indices = sch.leaves_list(linkage)
        ordered_symbols = [price_matrix.columns[i] for i in ordered_indices]
        
        # 5. Recursive Bisection
        hrp_weights = pd.Series(1.0, index=ordered_symbols)
        
        def rec_bisec(symbols_list, parent_weight):
            n = len(symbols_list)
            if n == 1:
                hrp_weights[symbols_list[0]] = parent_weight
                return
                
            mid = n // 2
            left = symbols_list[:mid]
            right = symbols_list[mid:]
            
            def get_branch_var(branch_symbols):
                sub_cov = cov.loc[branch_symbols, branch_symbols]
                diag = np.diag(sub_cov)
                inv_var = 1.0 / (diag + 1e-8)
                branch_w = inv_var / inv_var.sum()
                return np.dot(branch_w, np.dot(sub_cov, branch_w))
                
            var_left = get_branch_var(left)
            var_right = get_branch_var(right)
            
            alpha = var_right / (var_left + var_right + 1e-8)
            
            rec_bisec(left, parent_weight * alpha)
            rec_bisec(right, parent_weight * (1.0 - alpha))
            
        rec_bisec(ordered_symbols, 1.0)
        
        # 6. Post-Optimization Sizing & Risk Guards
        pot_size = total_equity * 0.25
        allocation_map = {}
        
        for symbol, weight in hrp_weights.items():
            sector = sectors[symbol]
            limit = self._get_dynamic_sector_limits(sector, bias)
            existing_exp = current_sector_exp.get(sector, 0.0)
            
            dollar_amt = pot_size * weight
            
            # Apply Conviction Boosting from Machine Learning predictions
            if confidence_scores and symbol in confidence_scores:
                conf = confidence_scores[symbol]
                multiplier = 1.0
                if conf >= config.CONVICTION_BOOST_LEVEL_2: multiplier = 2.0
                elif conf >= config.CONVICTION_BOOST_LEVEL_1: multiplier = 1.5
                dollar_amt *= multiplier
            
            # Sector Guard Check
            if (existing_exp + (dollar_amt / total_equity)) > limit:
                print(f"  [HRP Guard] Clipping {symbol}: Sector {sector} limit reached ({limit:.1%}).")
                dollar_amt = max(0, (limit - existing_exp) * total_equity)
            
            # Hard Drawdown Constraint: Max 15% allocation per asset
            dollar_amt = min(dollar_amt, total_equity * 0.15)
            
            # Convert to Quantity
            ticker_data = self.client.get_historical_data(symbol, lookback_days=1)
            if ticker_data.empty: continue
            current_price = ticker_data['close'].iloc[-1]
            
            qty = int(dollar_amt // current_price)
            if qty > 0:
                print(f"  HRP Allocation {symbol} ({sector}): {weight:.2%} -> ${dollar_amt:.0f} ({qty} shares)")
                allocation_map[symbol] = qty
                
        return allocation_map

    def hedge_portfolio(self, positions):
        """
        Checks Beta Exposure. If > Threshold, Shorts SPY.
        """
        beta, total_value, total_weighted_beta = self.calculate_portfolio_beta(positions)
        print(f"Portfolio Beta: {beta:.2f} | exposure: ${total_value:.2f} | Weighted Beta Dollars: ${total_weighted_beta:.0f}")
        
        # Desired Hedge:
        # We want Total Beta Exposure = Target Beta
        
        # Determine Target Beta dynamically from Macro Regime
        target_beta = self.macro_manager.get_recommended_beta()
        print(f"  [Portfolio] Macro Regime Recommended Beta: {target_beta}")
        
        # Current Beta Exposure = Portfolio Value * Beta = total_weighted_beta
        # Required Beta Balance = Value * target_beta
        # Hedge Needed = Current Beta Exposure - Required Beta Balance
        # e.g. If Current Exp is $1000 and target is $200 (target_beta 0.2), 
        # we need to hedge $800.
        
        hedge_value_needed = total_weighted_beta - (total_value * target_beta)
        
        # FIX: Use absolute value so we don't ignore Short Portfolios (where value is negative)
        if abs(hedge_value_needed) < 500: # Don't hedge tiny portfolios
            return
            
        # Check current SPY position
        spy_qty = 0
        for p in positions:
            if p.symbol == self.spy_symbol:
                spy_qty = float(p.qty) # Negative if short
                
        # Get SPY Price
        spy_bar = self.client.get_historical_data(self.spy_symbol, lookback_days=1)
        if spy_bar.empty: return
        spy_price = spy_bar.iloc[-1]['close']
        
        target_spy_qty = -1 * int(hedge_value_needed // spy_price) # Negative for Short
        
        diff = target_spy_qty - spy_qty
        
        if abs(diff) > 2: # Only rebalance if difference is > 2 shares
            
            # --- FLIP DETECTION ---
            # If we are switching from Short to Long (or vice versa), 
            # Alpaca can error if we try to "Buy to Cover" more than we are short.
            # We must split this into 2 trades: Close -> Open New.
            
            is_flipping = (spy_qty < 0 and target_spy_qty > 0) or (spy_qty > 0 and target_spy_qty < 0)
            
            if is_flipping:
                print(f"HEDGING: Flipping SPY Position (Current: {spy_qty}, Target: {target_spy_qty})")
                
                # 1. Close Existing Position (Get to 0)
                print(f"  Step 1: Closing existing position...")
                self.client.close_position(self.spy_symbol)
                
                import time
                time.sleep(2) # Wait for fill
                
                # 2. Open New Position (0 to Target)
                side = 'buy' if target_spy_qty > 0 else 'sell'
                qty = abs(target_spy_qty)
                if qty > 0:
                    print(f"  Step 2: Opening new {side.upper()} position for {qty} shares.")
                    self.client.submit_order(self.spy_symbol, qty, side)
            
            else:
                # Standard Adjustment (Increase/Decrease existing, or 0 to something)
                side = 'sell' if diff < 0 else 'buy'
                qty = abs(diff)
                print(f"HEDGING: Executing {side.upper()} {qty} SPY to adjust Beta.")
                self.client.submit_order(self.spy_symbol, qty, side)
