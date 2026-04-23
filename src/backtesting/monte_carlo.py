"""
Monte Carlo Simulation
=======================
Robustness testing via randomized trade sequence simulation.

Why Monte Carlo matters:
  A strategy with 100 trades could have performed well just by
  luck of the specific trade order. Monte Carlo shuffles the trade
  sequence 10,000 times to build a statistical distribution of outcomes.

Reports:
  - 5th percentile equity curve (worst-case realistic scenario)
  - 95th percentile equity curve (best-case realistic scenario)
  - Median equity curve
  - Probability of ruin (equity drops below 50% of initial)
  - Expected max drawdown distribution
  - Value at Risk (VaR) at 95% confidence
  - Conditional VaR (CVaR) — average of worst 5%
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MonteCarloResult:
    n_simulations:      int
    n_trades:           int
    initial_equity:     float

    # Equity distribution at end of simulation
    final_equity_p5:    float     # 5th percentile (bad case)
    final_equity_p25:   float     # 25th percentile
    final_equity_median: float    # Median
    final_equity_p75:   float     # 75th percentile
    final_equity_p95:   float     # 95th percentile (good case)
    final_equity_mean:  float

    # Risk metrics
    probability_of_ruin: float    # P(equity < 50% of initial)
    max_dd_p5:           float    # 5th percentile max drawdown (worst)
    max_dd_median:       float    # Median max drawdown
    max_dd_p95:          float    # 95th percentile max drawdown
    var_95:              float    # Value at Risk 95% (USD loss)
    cvar_95:             float    # Conditional VaR (expected loss in worst 5%)

    # Equity curves (sampled)
    curve_p5:     List[float] = field(default_factory=list)
    curve_median: List[float] = field(default_factory=list)
    curve_p95:    List[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"━━━━━━ Monte Carlo ({self.n_simulations:,} sims) ━━━━━━\n"
            f"Initial Equity:   ${self.initial_equity:,.0f}\n"
            f"Median Outcome:   ${self.final_equity_median:,.0f} "
            f"({(self.final_equity_median/self.initial_equity-1)*100:+.1f}%)\n"
            f"5th Percentile:   ${self.final_equity_p5:,.0f} "
            f"({(self.final_equity_p5/self.initial_equity-1)*100:+.1f}%)\n"
            f"95th Percentile:  ${self.final_equity_p95:,.0f} "
            f"({(self.final_equity_p95/self.initial_equity-1)*100:+.1f}%)\n"
            f"Prob. of Ruin:    {self.probability_of_ruin:.1%}\n"
            f"Max DD (median):  {self.max_dd_median:.1f}%\n"
            f"Max DD (worst 5%): {self.max_dd_p5:.1f}%\n"
            f"VaR 95%:          ${self.var_95:,.0f}\n"
            f"CVaR 95%:         ${self.cvar_95:,.0f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    def is_robust(self) -> Tuple[bool, str]:
        """Check if strategy passes robustness criteria."""
        checks = []
        if self.probability_of_ruin > 0.05:
            checks.append(f"Ruin probability {self.probability_of_ruin:.1%} > 5% threshold")
        if self.max_dd_p5 > 25.0:
            checks.append(f"Worst-case drawdown {self.max_dd_p5:.1f}% > 25% threshold")
        if self.final_equity_p5 < self.initial_equity * 0.70:
            checks.append(f"5th percentile equity {(self.final_equity_p5/self.initial_equity):.0%} < 70% threshold")

        if checks:
            return False, " | ".join(checks)
        return True, "Strategy passed all robustness checks"


class MonteCarloSimulator:
    """
    Runs Monte Carlo simulations by randomizing trade sequence.
    
    Two simulation modes:
      1. Trade shuffling: Shuffle historical trade P&Ls in random order
      2. Bootstrap:       Sample with replacement from trade P&Ls
    """

    def __init__(
        self,
        n_simulations:    int   = 10_000,
        ruin_threshold:   float = 0.50,   # Equity < 50% = ruin
        random_seed:      Optional[int] = 42,
    ):
        self.n_simulations   = n_simulations
        self.ruin_threshold  = ruin_threshold
        self._rng = np.random.default_rng(random_seed)

    def run(
        self,
        trade_returns:  List[float],    # List of trade % returns (e.g. [0.02, -0.01, ...])
        initial_equity: float = 10_000.0,
        method:         str   = "bootstrap",   # "shuffle" or "bootstrap"
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.

        Args:
            trade_returns:  Historical trade returns as decimals (0.02 = +2%)
            initial_equity: Starting capital
            method:         "shuffle" (no replacement) or "bootstrap" (with replacement)

        Returns:
            MonteCarloResult with full statistical breakdown
        """
        if not trade_returns or len(trade_returns) < 5:
            raise ValueError("Need at least 5 trades to run Monte Carlo simulation")

        returns_arr = np.array(trade_returns, dtype=float)
        n_trades    = len(returns_arr)

        logger.info(
            f"Running {self.n_simulations:,} Monte Carlo simulations "
            f"({n_trades} trades, method={method})"
        )

        # ── Run simulations ───────────────────────────────────────────────────
        final_equities = np.zeros(self.n_simulations)
        max_drawdowns  = np.zeros(self.n_simulations)

        # Store sampled paths for percentile curves
        all_curves = np.zeros((self.n_simulations, n_trades + 1))
        all_curves[:, 0] = initial_equity

        for i in range(self.n_simulations):
            if method == "bootstrap":
                # Sample with replacement (allows more extreme outcomes)
                sampled = self._rng.choice(returns_arr, size=n_trades, replace=True)
            else:
                # Shuffle without replacement (preserves distribution exactly)
                sampled = returns_arr.copy()
                self._rng.shuffle(sampled)

            # Build equity curve
            equity_curve = self._build_equity_curve(initial_equity, sampled)
            all_curves[i] = equity_curve

            final_equities[i] = equity_curve[-1]
            max_drawdowns[i]  = self._max_drawdown(equity_curve)

        # ── Compute statistics ────────────────────────────────────────────────
        ruin_count       = np.sum(final_equities < initial_equity * self.ruin_threshold)
        prob_ruin        = ruin_count / self.n_simulations

        # Percentile curves (using median index sim)
        p5_idx   = int(np.argsort(final_equities)[int(self.n_simulations * 0.05)])
        med_idx  = int(np.argsort(final_equities)[int(self.n_simulations * 0.50)])
        p95_idx  = int(np.argsort(final_equities)[int(self.n_simulations * 0.95)])

        # VaR and CVaR
        sorted_finals = np.sort(final_equities)
        var_idx       = int(self.n_simulations * 0.05)
        var_95        = float(initial_equity - sorted_finals[var_idx])
        cvar_95       = float(initial_equity - sorted_finals[:var_idx].mean()) if var_idx > 0 else var_95

        result = MonteCarloResult(
            n_simulations       = self.n_simulations,
            n_trades            = n_trades,
            initial_equity      = initial_equity,
            final_equity_p5     = float(np.percentile(final_equities, 5)),
            final_equity_p25    = float(np.percentile(final_equities, 25)),
            final_equity_median = float(np.median(final_equities)),
            final_equity_p75    = float(np.percentile(final_equities, 75)),
            final_equity_p95    = float(np.percentile(final_equities, 95)),
            final_equity_mean   = float(final_equities.mean()),
            probability_of_ruin = float(prob_ruin),
            max_dd_p5           = float(np.percentile(max_drawdowns, 95)),  # worst
            max_dd_median       = float(np.median(max_drawdowns)),
            max_dd_p95          = float(np.percentile(max_drawdowns, 5)),   # best
            var_95              = float(max(0, var_95)),
            cvar_95             = float(max(0, cvar_95)),
            curve_p5            = all_curves[p5_idx].tolist(),
            curve_median        = all_curves[med_idx].tolist(),
            curve_p95           = all_curves[p95_idx].tolist(),
        )

        robust, reason = result.is_robust()
        logger.info(
            f"Monte Carlo complete: "
            f"median={result.final_equity_median:,.0f} "
            f"p_ruin={prob_ruin:.1%} "
            f"robust={'✅' if robust else '❌'}"
        )

        return result

    def run_with_slippage_stress(
        self,
        trade_returns:  List[float],
        initial_equity: float = 10_000.0,
        extra_cost_pct: float = 0.002,   # 0.2% additional cost per trade
    ) -> MonteCarloResult:
        """
        Run simulation with added transaction cost stress.
        Tests how strategy performs under higher slippage / fees.
        """
        stressed = [r - extra_cost_pct for r in trade_returns]
        return self.run(stressed, initial_equity, method="bootstrap")

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_equity_curve(
        self, initial: float, returns: np.ndarray
    ) -> np.ndarray:
        """Build equity curve from sequence of returns."""
        curve = np.empty(len(returns) + 1)
        curve[0] = initial
        equity = initial
        for i, ret in enumerate(returns):
            equity *= (1 + ret)
            equity = max(equity, 0.01)  # Prevent negative equity
            curve[i + 1] = equity
        return curve

    def _max_drawdown(self, equity_curve: np.ndarray) -> float:
        """Calculate maximum drawdown % from an equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        peaks    = np.maximum.accumulate(equity_curve)
        dd_pct   = (equity_curve - peaks) / peaks * 100
        return float(abs(dd_pct.min()))
