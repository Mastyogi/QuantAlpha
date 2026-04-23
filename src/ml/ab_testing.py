"""A/B Testing Framework for ensemble models"""
from __future__ import annotations
import json, os, time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
from src.utils.logger import get_logger
logger = get_logger(__name__)

@dataclass
class ModelResult:
    model_id: str; model_version: str
    precision: float = 0.0; auc: float = 0.0
    n_signals: int = 0; n_correct: int = 0

@dataclass
class ABTestResult:
    champion: ModelResult; challenger: ModelResult
    winner: str; precision_delta: float; auc_delta: float
    p_value: float; is_significant: bool; decision_reason: str; test_bars: int
    timestamp: str = ""

    def to_telegram_str(self):
        return (f"🧪 A/B Test: champion={self.champion.precision:.1%} "
                f"challenger={self.challenger.precision:.1%} "
                f"winner={self.winner} ({self.decision_reason})")

class ABTestFramework:
    MIN_PRECISION_DELTA = 0.02; MIN_AUC_DELTA = 0.005; SIGNIFICANCE = 0.05

    def __init__(self, results_dir="models/ab_tests"):
        os.makedirs(results_dir, exist_ok=True)
        self.results_dir = results_dir; self._history: List[ABTestResult] = []

    def run_test(self, symbol, champion, challenger, X_test, y_test,
                 champion_version="v1", challenger_version="v2") -> ABTestResult:
        cr = self._eval(champion,   X_test, y_test, symbol, champion_version)
        ch = self._eval(challenger, X_test, y_test, symbol, challenger_version)
        pd = ch.precision - cr.precision; ad = ch.auc - cr.auc
        p, sig = self._pvalue(cr.n_signals, cr.n_correct, ch.n_signals, ch.n_correct)
        winner, reason = self._decide(pd, ad, p, sig)
        r = ABTestResult(cr, ch, winner, pd, ad, p, sig, reason, len(X_test),
                         datetime.now(timezone.utc).isoformat())
        self._history.append(r)
        logger.info(f"A/B {symbol}: winner={winner} delta={pd:+.1%} {reason}")
        return r

    def run_multi_fold_test(self, symbol, champion, challenger, X, y, n_folds=5,
                            champion_version="v1", challenger_version="v2") -> ABTestResult:
        try:
            from sklearn.model_selection import TimeSeriesSplit
        except ImportError:
            return self.run_test(symbol, champion, challenger, X, y, champion_version, challenger_version)
        tscv = TimeSeriesSplit(n_splits=n_folds)
        cps, chs, cn, cc, hn, hc = [], [], 0, 0, 0, 0
        for _, ti in tscv.split(X):
            cr = self._eval(champion, X[ti], y[ti], symbol, champion_version)
            ch = self._eval(challenger, X[ti], y[ti], symbol, challenger_version)
            cps.append(cr.precision); chs.append(ch.precision)
            cn += cr.n_signals; cc += cr.n_correct
            hn += ch.n_signals; hc += ch.n_correct
        cma = ModelResult(symbol, champion_version, float(np.mean(cps)), 0, cn, cc)
        cha = ModelResult(symbol, challenger_version, float(np.mean(chs)), 0, hn, hc)
        pd = cha.precision - cma.precision
        p, sig = self._pvalue(cn, cc, hn, hc)
        winner, reason = self._decide(pd, 0, p, sig)
        r = ABTestResult(cma, cha, winner, pd, 0, p, sig,
                         f"[{n_folds}-fold] {reason}", len(X), datetime.now(timezone.utc).isoformat())
        self._history.append(r); return r

    def _eval(self, model, X, y, symbol, version) -> ModelResult:
        try:
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X)
                proba = proba[:,1] if len(proba.shape)==2 else proba
            elif hasattr(model, 'predict'):
                proba = model.predict(X).astype(float)
            else:
                return ModelResult(symbol, version)
            t = float(np.percentile(proba, 65))
            preds = (proba >= t).astype(int)
            n = int(preds.sum()); k = int((preds==y)[preds==1].sum()) if n>0 else 0
            prec = k/n if n>0 else 0.0
            try:
                from sklearn.metrics import roc_auc_score
                auc = float(roc_auc_score(y, proba))
            except Exception: auc = 0.5
            return ModelResult(symbol, version, prec, auc, n, k)
        except Exception: return ModelResult(symbol, version)

    def _pvalue(self, n_a, k_a, n_b, k_b) -> Tuple[float, bool]:
        try:
            from scipy.stats import chi2_contingency
            if n_a<5 or n_b<5: return 1.0, False
            _, p, _, _ = chi2_contingency([[k_a,n_a-k_a],[k_b,n_b-k_b]], correction=True)
            return float(p), p < self.SIGNIFICANCE
        except Exception: return 1.0, False

    def _decide(self, pd, ad, p, sig) -> Tuple[str, str]:
        if pd >= 0.05: return "challenger", f"Large gain {pd:+.1%}"
        if pd >= self.MIN_PRECISION_DELTA and sig: return "challenger", f"precision {pd:+.1%} p={p:.3f}"
        if pd < -0.02: return "champion", f"Challenger degraded {pd:+.1%}"
        return "no_change", f"Below threshold {pd:+.1%}"

    def get_history(self, symbol=None):
        return [r for r in self._history if symbol is None or r.champion.model_id==symbol]
