"""
PortfolioTuner — Self-Tuning Parameter Optimizer
=================================================
Observes every trade decision (with its exact parameter context) and the
resulting PnL outcome, then uses Bayesian Optimization (Gaussian Process +
UCB acquisition) to automatically nudge all decision thresholds toward values
that maximise risk-adjusted return.

Learning loop
─────────────
1. At trade ENTRY  → record_decision(symbol, context_dict)
   Stamps the full parameter vector used at decision time.

2. At trade CLOSE  → record_outcome(symbol, pnl_pct, max_drawdown_during_hold)
   Computes reward = pnl_pct / max(0.01, max_drawdown_during_hold)  (mini-Sharpe)
   Stores (param_vector, reward) pair.
   Every TUNER_OPTIMIZATION_INTERVAL pairs → runs one GP optimisation step.

3. Optimisation step
   a. Fit a GP regressor on all (param_vectors, rewards) seen so far.
   b. Sample candidate parameter vectors inside their defined bounds.
   c. Apply UCB = μ(candidates) + κ·σ(candidates) to pick the best candidate.
   d. Patch the live `config` module so all downstream code uses new values.
   e. Write params + history to disk so they survive restarts.

No external ML frameworks required beyond scipy + numpy (already in use).
"""

import json
import os
import time
import numpy as np
import config

# --------------------------------------------------------------------------- #
#  Parameter search space: name → (min, max, default)                         #
#  ATR multipliers and VIX thresholds are intentionally excluded (manual).     #
# --------------------------------------------------------------------------- #
PARAM_SPACE = {
    # Sentiment tier weights
    "SENTIMENT_TIER1_WEIGHT":      (0.5,  1.0,   1.0),
    "SENTIMENT_TIER2_WEIGHT":      (0.1,  0.9,   0.6),
    "SENTIMENT_TIER3_WEIGHT":      (0.0,  0.5,   0.3),
    # Sentiment decision thresholds
    "SENTIMENT_VETO_THRESHOLD":    (-0.5, -0.05, -0.2),
    "SENTIMENT_BOOST_THRESHOLD":   (0.05, 0.5,   0.2),
    "SENTIMENT_BOOST_AMOUNT":      (0.05, 0.3,   0.1),
    # Smart money thresholds
    "SM_STRONG_BUY_THRESHOLD":     (0.2,  0.9,   0.5),
    "SM_STRONG_SELL_THRESHOLD":    (-0.9, -0.2, -0.5),
    "SM_BUY_CONFIDENCE_BOOST":     (0.05, 0.3,   0.15),
    "SM_SELL_CONFIDENCE_PENALTY":  (0.05, 0.3,   0.10),
    "SM_ALPHA_CONFIRM_THRESHOLD":  (0.1,  0.7,   0.3),
    # Ensemble decision thresholds
    "MIN_CONFIDENCE_GAP":          (0.05, 0.25,  0.10),
    "SIDEWAYS_REGIME_PENALTY":     (0.0,  0.15,  0.05),
    # Risk Management & Stops
    "TRAILING_STOP_PCT":           (0.01, 0.06,  0.03),
    "OPEN_GAP_THRESHOLD":          (0.005, 0.03,  0.015),
    "OPEN_STOP_LOSS_MULTIPLIER":   (0.5,  2.0,   1.0),
}

PARAM_NAMES = list(PARAM_SPACE.keys())
N_PARAMS = len(PARAM_NAMES)
N_CANDIDATES = 500   # Random candidates to evaluate in UCB acquisition step


class PortfolioTuner:
    """
    Self-tuning meta-learner that optimises all decision thresholds
    using closed-trade feedback.
    """

    def __init__(self):
        self.params_path  = getattr(config, "TUNER_PARAMS_PATH",  "models/portfolio_tuner_params.json")
        self.history_path = getattr(config, "TUNER_HISTORY_PATH", "models/portfolio_tuner_history.json")
        self.min_trades   = getattr(config, "TUNER_MIN_TRADES_TO_OPTIMIZE", 5)
        self.opt_interval = getattr(config, "TUNER_OPTIMIZATION_INTERVAL",  3)
        self.kappa        = getattr(config, "TUNER_EXPLORATION_WEIGHT",      0.2)

        # Pending decisions: symbol → {'params': vector, 'timestamp': t}
        self._pending: dict = {}

        # Accumulated (param_vector, reward) history
        self._history_X: list[list[float]] = []
        self._history_y: list[float]       = []

        # Closed-trade counter (triggers optimization)
        self._trades_since_last_opt: int = 0

        # Current best params (loaded from disk or defaulted)
        self._current_params: dict[str, float] = self._load_params()

        # Load prior history for warm-starting GP
        self._load_history()

        print(f"  [Tuner] Initialized. {len(self._history_X)} prior trade(s) in history. "
              f"Optimizing every {self.opt_interval} closed trade(s).")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_params(self) -> dict[str, float]:
        """Returns the current learned parameters."""
        return dict(self._current_params)

    def apply_to_config(self, params: dict[str, float] | None = None) -> None:
        """
        Patches the live `config` module object so all downstream code that
        does `getattr(config, 'X')` picks up the new values immediately —
        no restart required.
        """
        if params is None:
            params = self._current_params
        for name, value in params.items():
            setattr(config, name, value)
        print(f"  [Tuner] Config patched with {len(params)} learned parameter(s).")

    def record_decision(self, symbol: str, context: dict) -> None:
        """
        Call this at trade ENTRY for every symbol a buy/sell order is placed for.

        context keys (all optional but richer = better tuning):
            mc_prob, rf_prob, mr_prob, sentiment_score, sm_score,
            vix_level, adx, regime, final_confidence, action
        """
        param_vector = self._snapshot_params()
        self._pending[symbol] = {
            "params":    param_vector,
            "context":   context,
            "timestamp": time.time(),
        }

    def record_outcome(self, symbol: str, pnl_pct: float,
                       max_drawdown_during_hold: float = 0.0) -> None:
        """
        Call this at trade CLOSE (after RL update) for every closed position.

        pnl_pct: realized gain/loss as a decimal (e.g. 0.031 = +3.1%)
        max_drawdown_during_hold: peak unrealised loss during the hold.
            Defaults to 0 (unavailable) — reward degrades gracefully to
            raw pnl_pct in that case.
        """
        if symbol not in self._pending:
            # Outcome for a trade we didn't record at entry (e.g. pre-existing).
            # Still log if possible, using current params as proxy.
            param_vector = self._snapshot_params()
        else:
            param_vector = self._pending.pop(symbol)["params"]

        # ── Mini-Sharpe reward ──────────────────────────────────────────
        # Reward = PnL / max_drawdown  (no overtrading penalty)
        denominator = max(abs(max_drawdown_during_hold), 0.01)
        reward = pnl_pct / denominator

        self._history_X.append(param_vector)
        self._history_y.append(reward)
        self._trades_since_last_opt += 1

        print(f"  [Tuner] {symbol} outcome recorded → PnL: {pnl_pct:+.3f} | "
              f"Reward: {reward:+.3f} | History size: {len(self._history_y)}")

        # Persist history so we survive restarts
        self._save_history()

        # Trigger optimization if conditions are met
        if (len(self._history_y) >= self.min_trades and
                self._trades_since_last_opt >= self.opt_interval):
            self._optimise()
            self._trades_since_last_opt = 0

    # ------------------------------------------------------------------ #
    #  Optimisation internals                                              #
    # ------------------------------------------------------------------ #

    def _optimise(self) -> None:
        """
        Bayesian Optimisation step:
        1. Fit GP on (param_vectors, rewards) history.
        2. Sample N_CANDIDATES random candidate param vectors.
        3. Use UCB to pick the best candidate.
        4. Update current params, patch config, persist.
        """
        print(f"\n  [Tuner] ── Running optimisation step "
              f"(history: {len(self._history_y)} trades) ──")

        X = np.array(self._history_X)   # shape (n_trades, N_PARAMS)
        y = np.array(self._history_y)   # shape (n_trades,)

        # Normalise X to [0, 1] for numerical stability
        bounds = np.array([[PARAM_SPACE[n][0], PARAM_SPACE[n][1]] for n in PARAM_NAMES])
        X_norm = (X - bounds[:, 0]) / (bounds[:, 1] - bounds[:, 0] + 1e-12)

        # Fit a simple RBF Gaussian Process
        gp = _SimpleGP(length_scale=0.5, noise=0.1)
        gp.fit(X_norm, y)

        # Sample random candidates and pick the one maximising UCB
        rng = np.random.default_rng(seed=int(time.time()) % 2**32)
        candidates_norm = rng.uniform(0.0, 1.0, size=(N_CANDIDATES, N_PARAMS))
        mu, sigma = gp.predict(candidates_norm)
        ucb = mu + self.kappa * sigma
        best_idx = int(np.argmax(ucb))
        best_norm = candidates_norm[best_idx]

        # Denormalise back to real parameter space
        new_params_raw = bounds[:, 0] + best_norm * (bounds[:, 1] - bounds[:, 0])
        new_params = {PARAM_NAMES[i]: float(new_params_raw[i]) for i in range(N_PARAMS)}

        # Log changes
        print("  [Tuner] Parameter updates:")
        for name, new_val in new_params.items():
            old_val = self._current_params.get(name, PARAM_SPACE[name][2])
            if abs(new_val - old_val) > 1e-6:
                print(f"    {name}: {old_val:.4f} → {new_val:.4f}")

        self._current_params = new_params
        self.apply_to_config(new_params)
        self._save_params()

    def _snapshot_params(self) -> list[float]:
        """Returns the current live param vector as a list (same order as PARAM_NAMES)."""
        return [self._current_params.get(name, PARAM_SPACE[name][2])
                for name in PARAM_NAMES]

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def _load_params(self) -> dict[str, float]:
        """Load persisted params or fall back to config defaults."""
        defaults = {name: getattr(config, name, PARAM_SPACE[name][2])
                    for name in PARAM_NAMES}
        try:
            if os.path.exists(self.params_path):
                with open(self.params_path, "r") as f:
                    saved = json.load(f)
                # Merge: use saved values where available, defaults elsewhere
                merged = {**defaults, **{k: v for k, v in saved.items() if k in PARAM_SPACE}}
                print(f"  [Tuner] Loaded persisted params from {self.params_path}")
                return merged
        except Exception as e:
            print(f"  [Tuner] Could not load params ({e}), using defaults.")
        return defaults

    def _save_params(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.params_path) or ".", exist_ok=True)
            with open(self.params_path, "w") as f:
                json.dump(self._current_params, f, indent=2)
        except Exception as e:
            print(f"  [Tuner] Failed to save params: {e}")

    def _load_history(self) -> None:
        try:
            if os.path.exists(self.history_path):
                with open(self.history_path, "r") as f:
                    data = json.load(f)
                self._history_X = data.get("X", [])
                self._history_y = data.get("y", [])
                print(f"  [Tuner] Loaded {len(self._history_y)} historical trade(s) from disk.")
        except Exception as e:
            print(f"  [Tuner] Could not load history ({e}), starting fresh.")

    def _save_history(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.history_path) or ".", exist_ok=True)
            with open(self.history_path, "w") as f:
                json.dump({"X": self._history_X, "y": self._history_y}, f)
        except Exception as e:
            print(f"  [Tuner] Failed to save history: {e}")


# --------------------------------------------------------------------------- #
#  Lightweight Gaussian Process (RBF kernel, no sklearn dependency)            #
# --------------------------------------------------------------------------- #

class _SimpleGP:
    """
    Minimal Gaussian Process regressor using a squared-exponential (RBF) kernel.
    Only requires numpy — no sklearn GP needed.

    K(x, x') = exp(-||x - x'||² / (2 · l²))
    Posterior: μ = K*ᵀ (K + σ²I)⁻¹ y
               σ² = diag(K** - K*ᵀ (K + σ²I)⁻¹ K*)
    """

    def __init__(self, length_scale: float = 0.5, noise: float = 0.1):
        self.l   = length_scale
        self.sig = noise
        self.X_train: np.ndarray | None = None
        self.alpha:   np.ndarray | None = None
        self.K_inv:   np.ndarray | None = None

    def _rbf(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Compute RBF kernel matrix between rows of A and B."""
        # Euclidean distance squared via broadcasting
        diff = A[:, np.newaxis, :] - B[np.newaxis, :, :]   # (n, m, d)
        sq_dist = np.sum(diff ** 2, axis=-1)                 # (n, m)
        return np.exp(-sq_dist / (2 * self.l ** 2))

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        n = len(X)
        K = self._rbf(X, X) + (self.sig ** 2) * np.eye(n)
        # Small jitter for numerical stability
        K += 1e-8 * np.eye(n)
        try:
            self.K_inv = np.linalg.inv(K)
        except np.linalg.LinAlgError:
            self.K_inv = np.linalg.pinv(K)
        self.alpha   = self.K_inv @ y
        self.X_train = X

    def predict(self, X_new: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns (mean, std) for each row in X_new."""
        K_star = self._rbf(X_new, self.X_train)         # (m, n)
        mu     = K_star @ self.alpha                     # (m,)
        K_ss   = np.ones(len(X_new))                    # diag of K(X*, X*)
        sigma2 = K_ss - np.sum((K_star @ self.K_inv) * K_star, axis=1)
        sigma2 = np.maximum(sigma2, 0.0)                # numerical clamp
        return mu, np.sqrt(sigma2)


# --------------------------------------------------------------------------- #
#  Quick smoke test                                                            #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print("=== PortfolioTuner Smoke Test ===")
    tuner = PortfolioTuner()

    # Simulate 6 trades (above the opt_interval=3 threshold)
    trades = [
        ("AAPL", 0.031, 0.010),
        ("NVDA", -0.018, 0.025),
        ("MSFT", 0.052, 0.008),
        ("TSLA", -0.041, 0.050),
        ("AMZN", 0.027, 0.012),
        ("GOOGL", 0.015, 0.007),
    ]
    for sym, pnl, dd in trades:
        tuner.record_decision(sym, {"action": "buy", "final_confidence": 0.65})
        tuner.record_outcome(sym, pnl, dd)

    print("\nFinal learned params:")
    for k, v in tuner.get_params().items():
        default = PARAM_SPACE[k][2]
        marker = " ← changed" if abs(v - default) > 1e-6 else ""
        print(f"  {k}: {v:.4f}  (default={default}){marker}")
