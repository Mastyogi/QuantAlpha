"""
Walk-Forward Validator
=======================
TRUE out-of-sample performance validation.

Why walk-forward > simple backtest:
  Simple backtest: Train on 2020-2023, test on 2020-2023 → OVERFIT
  Walk-forward:    Train Jan-Sep, test Oct → Train Feb-Oct, test Nov → ...
                   Each test period was NEVER seen during training → honest

Process:
  1. Split data into N windows
  2. For each window: train on past, test on unseen future
  3. Aggregate OOS performance → true expected performance

Metrics reported:
  - OOS Accuracy, Precision (win rate), Recall, F1, AUC
  - Sharpe Ratio on OOS equity curve
  - Max Drawdown on OOS signals
  - Per-window stability (variance of performance)
  - Degradation test: does performance decline over time?
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
)

from src.ai_engine.advanced_features import AdvancedFeaturePipeline
from src.ai_engine.ensemble_model import StackingEnsemble
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FoldResult:
    fold:       int
    train_size: int
    test_size:  int
    accuracy:   float
    precision:  float
    recall:     float
    f1:         float
    auc:        float
    n_signals:  int     # How many signals fired
    signal_rate: float  # % of test periods with signals


@dataclass
class WalkForwardReport:
    symbol:      str
    n_folds:     int
    total_bars:  int
    folds:       List[FoldResult] = field(default_factory=list)

    # Aggregate OOS metrics
    oos_accuracy:   float = 0.0
    oos_precision:  float = 0.0   # ← This is the WIN RATE
    oos_recall:     float = 0.0
    oos_f1:         float = 0.0
    oos_auc:        float = 0.0

    # Stability
    precision_std:  float = 0.0   # Lower = more stable
    performance_trend: str = ""   # "improving" / "stable" / "degrading"

    # Trading simulation
    simulated_trades: int   = 0
    win_rate:         float = 0.0
    avg_rr:           float = 0.0
    sharpe_ratio:     float = 0.0
    max_drawdown_pct: float = 0.0
    total_return_pct: float = 0.0

    total_time_s: float = 0.0

    def summary(self) -> str:
        grade = "🔥 EXCELLENT" if self.oos_precision >= 0.72 else \
                "✅ GOOD"      if self.oos_precision >= 0.62 else \
                "⚠️  MARGINAL"  if self.oos_precision >= 0.52 else \
                "❌ POOR"
        lines = [
            f"{'='*52}",
            f"  Walk-Forward Report: {self.symbol}  {grade}",
            f"{'─'*52}",
            f"  Folds:      {self.n_folds}  ({self.total_bars} bars total)",
            f"{'─'*52}",
            f"  OOS Win Rate (Precision): {self.oos_precision:.1%}",
            f"  OOS Accuracy:             {self.oos_accuracy:.1%}",
            f"  OOS AUC:                  {self.oos_auc:.3f}",
            f"  Precision Stability:      ±{self.precision_std:.3f}",
            f"  Performance Trend:        {self.performance_trend}",
            f"{'─'*52}",
            f"  Simulated Trades: {self.simulated_trades}",
            f"  Win Rate:         {self.win_rate:.1%}",
            f"  Sharpe Ratio:     {self.sharpe_ratio:.2f}",
            f"  Max Drawdown:     {self.max_drawdown_pct:.1f}%",
            f"  Total Return:     {self.total_return_pct:.1f}%",
            f"{'─'*52}",
        ]
        for i, fold in enumerate(self.folds):
            lines.append(
                f"  Fold {fold.fold}: prec={fold.precision:.2f}  "
                f"rec={fold.recall:.2f}  signals={fold.n_signals}"
            )
        lines.append(f"  Time: {self.total_time_s:.1f}s")
        lines.append("="*52)
        return "\n".join(lines)


class WalkForwardValidator:
    """
    Validates ensemble model performance using strict walk-forward methodology.
    Run this before going live to confirm model is production-ready.
    """

    def __init__(
        self,
        n_folds: int = 5,
        min_train_bars: int = 200,
        gap_bars: int = 5,             # Gap between train/test to prevent leakage
        confluence_threshold: float = 0.70,
    ):
        self.n_folds   = n_folds
        self.min_train_bars = min_train_bars
        self.gap_bars  = gap_bars
        self.conf_threshold = confluence_threshold
        self.fp = AdvancedFeaturePipeline()

    def validate(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        asset_class: str = "crypto",
        forward_periods: int = 4,
        rr_ratio: float = 2.0,
    ) -> WalkForwardReport:
        """
        Run full walk-forward validation on OHLCV data.

        Args:
            df:             OHLCV DataFrame (minimum 500 bars recommended)
            symbol:         Symbol name for report
            asset_class:    crypto / forex / commodity
            forward_periods: Label lookahead (4h default)
            rr_ratio:       Assumed R:R for Sharpe calc
        """
        t0 = time.time()
        report = WalkForwardReport(symbol=symbol, n_folds=self.n_folds, total_bars=len(df))

        # Extract features + labels once (no leakage — labels use future data anyway)
        X_all, y_all = self.fp.prepare_training_data(df, asset_class=asset_class)
        n = len(X_all)

        if n < self.min_train_bars + 50:
            logger.warning(f"Only {n} samples — need {self.min_train_bars + 50}+ for valid WF")
            report.oos_precision = 0.5
            report.performance_trend = "insufficient_data"
            return report

        # Calculate fold sizes
        fold_size = n // (self.n_folds + 1)
        if fold_size < 30:
            self.n_folds = max(3, n // 60)
            fold_size    = n // (self.n_folds + 1)
            report.n_folds = self.n_folds

        logger.info(f"Walk-Forward: {n} samples, {self.n_folds} folds, "
                    f"{fold_size} bars/fold")

        all_y_true = []
        all_y_pred = []
        all_y_prob = []
        fold_results: List[FoldResult] = []
        equity_curve = [1.0]

        for fold in range(self.n_folds):
            train_end   = fold_size * (fold + 1)
            test_start  = train_end + self.gap_bars
            test_end    = min(test_start + fold_size, n)

            if test_start >= n or test_end - test_start < 10:
                break

            X_train = X_all[:train_end]
            y_train = y_all[:train_end]
            X_test  = X_all[test_start:test_end]
            y_test  = y_all[test_start:test_end]

            if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
                continue

            # Train fresh model on train window
            model = StackingEnsemble(symbol=symbol)
            model.train(X_train, y_train, walk_forward_folds=3, auto_tune=False)

            # Predict on test window (out-of-sample)
            probs_list = []
            preds_list = []
            for i in range(len(X_test)):
                d, conf, _ = model.predict(X_test[i:i+1])
                probs_list.append(float(conf) if d == 1 else 1 - float(conf))
                preds_list.append(1 if d == 1 else 0)

            y_prob_arr = np.array(probs_list)
            y_pred_arr = np.array(preds_list)

            # ── Equity simulation ─────────────────────────────────────────────
            for pred, true in zip(y_pred_arr, y_test):
                if pred == 1:  # Signal fired
                    if true == 1:
                        equity_curve.append(equity_curve[-1] * (1 + 0.01 * rr_ratio))
                    else:
                        equity_curve.append(equity_curve[-1] * (1 - 0.01))

            # ── Fold metrics ──────────────────────────────────────────────────
            n_signals = int(y_pred_arr.sum())
            try:
                auc = roc_auc_score(y_test, y_prob_arr)
            except Exception:
                auc = 0.5

            fold_res = FoldResult(
                fold=fold + 1,
                train_size=len(X_train),
                test_size=len(X_test),
                accuracy=round(accuracy_score(y_test, y_pred_arr), 4),
                precision=round(precision_score(y_test, y_pred_arr, zero_division=0), 4),
                recall=round(recall_score(y_test, y_pred_arr, zero_division=0), 4),
                f1=round(f1_score(y_test, y_pred_arr, zero_division=0), 4),
                auc=round(auc, 4),
                n_signals=n_signals,
                signal_rate=round(n_signals / len(y_test), 3),
            )
            fold_results.append(fold_res)
            all_y_true.extend(y_test.tolist())
            all_y_pred.extend(y_pred_arr.tolist())
            all_y_prob.extend(y_prob_arr.tolist())

            logger.info(
                f"Fold {fold+1}/{self.n_folds}: "
                f"prec={fold_res.precision:.3f} rec={fold_res.recall:.3f} "
                f"auc={fold_res.auc:.3f} signals={n_signals}"
            )

        if not fold_results:
            report.oos_precision = 0.5
            return report

        # ── Aggregate OOS metrics ─────────────────────────────────────────────
        y_t = np.array(all_y_true)
        y_p = np.array(all_y_pred)
        y_pr = np.array(all_y_prob)

        try:
            report.oos_accuracy  = round(accuracy_score(y_t, y_p), 4)
            report.oos_precision = round(precision_score(y_t, y_p, zero_division=0), 4)
            report.oos_recall    = round(recall_score(y_t, y_p, zero_division=0), 4)
            report.oos_f1        = round(f1_score(y_t, y_p, zero_division=0), 4)
            report.oos_auc       = round(roc_auc_score(y_t, y_pr), 4) if len(np.unique(y_t)) > 1 else 0.5
        except Exception as e:
            logger.warning(f"Metric calc failed: {e}")

        # ── Stability analysis ────────────────────────────────────────────────
        precisions = [f.precision for f in fold_results]
        report.precision_std = round(float(np.std(precisions)), 4)
        report.folds = fold_results

        # Trend: is performance improving or degrading across folds?
        if len(precisions) >= 3:
            slope = np.polyfit(range(len(precisions)), precisions, 1)[0]
            report.performance_trend = (
                "improving ↑" if slope > 0.01 else
                "degrading ↓" if slope < -0.01 else
                "stable →"
            )
        else:
            report.performance_trend = "stable →"

        # ── Trading simulation stats ──────────────────────────────────────────
        signals_mask = y_p == 1
        report.simulated_trades = int(signals_mask.sum())
        if report.simulated_trades > 0:
            wins = int((y_p[signals_mask] == y_t[signals_mask]).sum())
            report.win_rate = round(wins / report.simulated_trades, 4)

        # Sharpe ratio from equity curve
        ec = np.array(equity_curve)
        returns = np.diff(ec) / ec[:-1]
        if len(returns) > 1 and returns.std() > 0:
            report.sharpe_ratio = round(float(returns.mean() / returns.std() * np.sqrt(252)), 2)

        # Max drawdown
        peak = ec[0]; max_dd = 0.0
        for v in ec:
            peak = max(peak, v)
            max_dd = max(max_dd, (peak - v) / peak * 100)
        report.max_drawdown_pct = round(max_dd, 2)
        report.total_return_pct = round((ec[-1] - ec[0]) / ec[0] * 100, 2)
        report.total_time_s = round(time.time() - t0, 1)

        logger.info(
            f"WF Complete [{symbol}]: "
            f"OOS precision={report.oos_precision:.1%} "
            f"win_rate={report.win_rate:.1%} "
            f"sharpe={report.sharpe_ratio:.2f} "
            f"max_dd={report.max_drawdown_pct:.1f}%"
        )
        return report

    def is_production_ready(self, report: WalkForwardReport) -> Tuple[bool, str]:
        """
        Gate check: is model ready for live trading?
        Returns (ready, reason).
        """
        checks = [
            (report.oos_precision >= 0.58, f"OOS precision {report.oos_precision:.1%} < 58%"),
            (report.oos_auc >= 0.55,        f"AUC {report.oos_auc:.3f} < 0.55"),
            (report.precision_std <= 0.15,  f"Precision instability ±{report.precision_std:.3f} > 0.15"),
            (report.max_drawdown_pct <= 25, f"Max DD {report.max_drawdown_pct:.1f}% > 25%"),
            (report.simulated_trades >= 10, f"Too few signals ({report.simulated_trades})"),
            ("degrading" not in report.performance_trend,
             f"Performance is {report.performance_trend}"),
        ]
        failures = [reason for passed, reason in checks if not passed]
        if failures:
            return False, " | ".join(failures)
        return True, "All checks passed ✅"
