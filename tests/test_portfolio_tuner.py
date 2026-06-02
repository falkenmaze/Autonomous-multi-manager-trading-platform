"""
Tests for PortfolioTuner — self-tuning parameter optimizer.

Verifies:
1. Default params load correctly when no saved state exists.
2. Params stay within their defined bounds after optimization.
3. apply_to_config patches the live config module.
4. History persistence (save/load round-trip).
5. Reward function produces expected sign for win/loss.
6. Optimization triggers at the correct interval.
"""

import sys
import os
import json
import tempfile
import unittest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from strategy.portfolio_tuner import PortfolioTuner, PARAM_SPACE, PARAM_NAMES


class TestPortfolioTuner(unittest.TestCase):

    def setUp(self):
        """Snapshot all tunable config values before each test."""
        self._config_snapshot = {name: getattr(config, name, PARAM_SPACE[name][2])
                                  for name in PARAM_NAMES}

    def tearDown(self):
        """Restore all tunable config values after each test."""
        for name, val in self._config_snapshot.items():
            setattr(config, name, val)

    def _make_tuner(self, tmp_dir: str) -> PortfolioTuner:
        """Helper: create a tuner pointing to a temp directory (clean slate)."""
        params_path  = os.path.join(tmp_dir, "tuner_params.json")
        history_path = os.path.join(tmp_dir, "tuner_history.json")
        config.TUNER_PARAMS_PATH            = params_path
        config.TUNER_HISTORY_PATH           = history_path
        config.TUNER_MIN_TRADES_TO_OPTIMIZE = 3
        config.TUNER_OPTIMIZATION_INTERVAL  = 3
        config.TUNER_EXPLORATION_WEIGHT     = 0.2
        return PortfolioTuner()

    # ------------------------------------------------------------------ #


    def test_defaults_loaded_when_no_saved_state(self):
        """Params should equal config defaults on a fresh start."""
        with tempfile.TemporaryDirectory() as tmp:
            tuner = self._make_tuner(tmp)
            params = tuner.get_params()
            for name in PARAM_NAMES:
                expected_default = PARAM_SPACE[name][2]
                self.assertAlmostEqual(
                    params[name], expected_default, places=6,
                    msg=f"{name} default mismatch"
                )

    def test_params_within_bounds_after_optimization(self):
        """After optimization, all params must stay inside their defined bounds."""
        with tempfile.TemporaryDirectory() as tmp:
            tuner = self._make_tuner(tmp)

            # Feed enough trades to trigger optimization (min=3, interval=3)
            trades = [
                ("AAPL",  0.040, 0.010),
                ("NVDA", -0.015, 0.030),
                ("MSFT",  0.025, 0.008),
            ]
            for sym, pnl, dd in trades:
                tuner.record_decision(sym, {"action": "buy"})
                tuner.record_outcome(sym, pnl, dd)

            params = tuner.get_params()
            for name, val in params.items():
                lo, hi, _ = PARAM_SPACE[name]
                self.assertGreaterEqual(val, lo - 1e-9, f"{name} below lower bound")
                self.assertLessEqual(val, hi + 1e-9,   f"{name} above upper bound")

    def test_apply_to_config_patches_live_module(self):
        """apply_to_config should immediately update the config module attributes."""
        with tempfile.TemporaryDirectory() as tmp:
            tuner = self._make_tuner(tmp)

            # Force a known value
            test_val = 0.77
            tuner._current_params["SM_STRONG_BUY_THRESHOLD"] = test_val
            tuner.apply_to_config()

            self.assertAlmostEqual(
                config.SM_STRONG_BUY_THRESHOLD, test_val, places=6,
                msg="Config module not patched by apply_to_config()"
            )

    def test_history_persistence(self):
        """History should survive a tuner restart (save/load round-trip)."""
        with tempfile.TemporaryDirectory() as tmp:
            tuner1 = self._make_tuner(tmp)
            trades = [
                ("TSLA",  0.030, 0.010),
                ("AMZN", -0.020, 0.025),
            ]
            for sym, pnl, dd in trades:
                tuner1.record_decision(sym, {"action": "buy"})
                tuner1.record_outcome(sym, pnl, dd)

            # Create a second tuner pointing at same files
            tuner2 = self._make_tuner(tmp)
            self.assertEqual(
                len(tuner2._history_y), 2,
                "History not reloaded after restart"
            )

    def test_reward_sign(self):
        """Winning trades should produce positive reward; losses negative."""
        with tempfile.TemporaryDirectory() as tmp:
            tuner = self._make_tuner(tmp)
            tuner.record_decision("WIN", {"action": "buy"})
            tuner.record_outcome("WIN", pnl_pct=0.05, max_drawdown_during_hold=0.01)
            self.assertGreater(tuner._history_y[-1], 0, "Win should give positive reward")

            tuner.record_decision("LOSS", {"action": "buy"})
            tuner.record_outcome("LOSS", pnl_pct=-0.03, max_drawdown_during_hold=0.04)
            self.assertLess(tuner._history_y[-1], 0, "Loss should give negative reward")

    def test_optimization_interval(self):
        """Optimization should fire exactly once after opt_interval closed trades."""
        with tempfile.TemporaryDirectory() as tmp:
            config.TUNER_MIN_TRADES_TO_OPTIMIZE = 3
            config.TUNER_OPTIMIZATION_INTERVAL  = 3
            tuner = self._make_tuner(tmp)

            # Track optimization calls
            opt_calls = []
            original_opt = tuner._optimise
            def _patched_opt():
                opt_calls.append(1)
                original_opt()
            tuner._optimise = _patched_opt

            # 2 trades — should NOT optimise
            for sym in ["A", "B"]:
                tuner.record_decision(sym, {})
                tuner.record_outcome(sym, 0.01, 0.005)
            self.assertEqual(len(opt_calls), 0, "Should not optimise before reaching min_trades")

            # 3rd trade — should trigger
            tuner.record_decision("C", {})
            tuner.record_outcome("C", 0.02, 0.005)
            self.assertEqual(len(opt_calls), 1, "Should optimise after 3 trades")

            # 4th/5th trades — should NOT trigger again until next interval
            for sym in ["D", "E"]:
                tuner.record_decision(sym, {})
                tuner.record_outcome(sym, 0.01, 0.005)
            self.assertEqual(len(opt_calls), 1, "Should not optimise again before next interval")

            # 6th trade — 3 since last opt → trigger again
            tuner.record_decision("F", {})
            tuner.record_outcome("F", 0.03, 0.005)
            self.assertEqual(len(opt_calls), 2, "Should optimise again after another interval")


if __name__ == "__main__":
    unittest.main(verbosity=2)
