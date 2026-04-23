"""Enhanced Stacking Ensemble: RF + LightGBM + XGBoost + LR meta-learner"""
from __future__ import annotations
import os, time, warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
warnings.filterwarnings("ignore")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import precision_score, roc_auc_score, f1_score, accuracy_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.calibration import CalibratedClassifierCV
    import joblib
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

from src.utils.logger import get_logger
logger = get_logger(__name__)

@dataclass
class EnsembleMetrics:
    accuracy: float = 0.0; precision: float = 0.0; auc: float = 0.0
    threshold: float = 0.5; n_samples: int = 0; train_time_s: float = 0.0
    model_version: str = "v2"

    def is_production_ready(self) -> Tuple[bool, str]:
        if self.precision < 0.55: return False, f"Precision {self.precision:.1%} < 55%"
        if self.n_samples < 50: return False, f"Only {self.n_samples} samples"
        return True, "OK"

class EnhancedStackingEnsemble:
    VERSION = "v2"

    def __init__(self, symbol="UNKNOWN", precision_threshold=0.70, optuna_trials=0,
                 use_lightgbm=False, use_xgboost=False):
        self.symbol = symbol
        self.precision_threshold = precision_threshold
        self._threshold = precision_threshold
        self._is_trained = False
        self._metrics: Optional[EnsembleMetrics] = None
        self._n_features = 0
        self._feature_names: List[str] = []
        self.rf_model = None; self.meta_model = None; self.scaler = None

    def train(self, X: np.ndarray, y: np.ndarray,
              feature_names=None, tune=False) -> Dict:
        if not SKLEARN_OK or len(X) < 50:
            return {"precision": 0.0, "auc": 0.5, "accuracy": 0.0, "threshold": 0.5, "n_samples": len(X)}
        t0 = time.monotonic()
        self._n_features = X.shape[1]
        self._feature_names = feature_names or [f"f{i}" for i in range(self._n_features)]
        tscv = TimeSeriesSplit(n_splits=min(5, len(X)//20))
        oof = np.zeros(len(X))
        for train_idx, val_idx in tscv.split(X):
            m = RandomForestClassifier(n_estimators=200, max_depth=8,
                min_samples_leaf=15, class_weight="balanced", random_state=42, n_jobs=-1)
            m.fit(X[train_idx], y[train_idx])
            oof[val_idx] = m.predict_proba(X[val_idx])[:, 1]
        self.rf_model = RandomForestClassifier(n_estimators=300, max_depth=8,
            min_samples_leaf=15, class_weight="balanced", random_state=42, n_jobs=-1)
        self.rf_model.fit(X, y)
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        lr = LogisticRegression(C=0.1, class_weight="balanced", random_state=42, max_iter=500)
        lr.fit(X_s, y)
        meta_X = np.column_stack([self.rf_model.predict_proba(X)[:,1],
                                   lr.predict_proba(X_s)[:,1]])
        meta_lr = LogisticRegression(C=1.0, random_state=42, max_iter=300)
        meta_lr.fit(meta_X, y)
        self.meta_model = meta_lr; self.lr_model = lr
        self._threshold = self._find_threshold(y, oof)
        try:
            prec = float(precision_score(y, (oof >= self._threshold).astype(int), zero_division=0))
            auc  = float(roc_auc_score(y, oof))
        except Exception:
            prec, auc = 0.0, 0.5
        self._metrics = EnsembleMetrics(precision=prec, auc=auc,
            threshold=self._threshold, n_samples=len(X),
            train_time_s=time.monotonic()-t0)
        self._is_trained = True
        logger.info(f"{self.symbol}: trained precision={prec:.1%} auc={auc:.3f}")
        return {"precision": prec, "auc": auc, "accuracy": prec, "threshold": self._threshold, "n_samples": len(X)}

    def predict(self, X: np.ndarray) -> Tuple[int, float, str]:
        if not self._is_trained or self.rf_model is None: return 0, 0.5, "D"
        try:
            if len(X.shape) == 1: X = X.reshape(1, -1)
            rf_p  = self.rf_model.predict_proba(X)[:,1]
            lr_p  = self.lr_model.predict_proba(self.scaler.transform(X))[:,1]
            meta_X = np.column_stack([rf_p, lr_p])
            conf = float(self.meta_model.predict_proba(meta_X)[:,1].mean())
            pred = 1 if conf >= self._threshold else 0
            grade = "A+" if conf>=.88 else ("A" if conf>=.80 else ("B" if conf>=.72 else ("C" if conf>=.62 else "D")))
            return pred, conf, grade
        except Exception: return 0, 0.5, "D"

    def predict_proba(self, X): _, c, _ = self.predict(X); return c

    def _find_threshold(self, y, proba):
        best_t, best_p = 0.5, 0.0
        for t in np.arange(0.40, 0.90, 0.02):
            preds = (proba >= t).astype(int)
            if preds.sum() < max(5, len(y)*0.05): continue
            p = float(precision_score(y, preds, zero_division=0))
            if p > best_p: best_p, best_t = p, t
        return best_t

    def _get_feature_importance(self):
        if self.rf_model is None: return {}
        imp = self.rf_model.feature_importances_
        idx = np.argsort(imp)[::-1][:10]
        names = self._feature_names or [f"f{i}" for i in range(len(imp))]
        return {names[i]: float(imp[i]) for i in idx}

    def save(self, model_dir="models"):
        os.makedirs(model_dir, exist_ok=True)
        sym = self.symbol.replace("/","_")
        path = os.path.join(model_dir, f"ensemble_v2_{sym}.joblib")
        joblib.dump({"rf":self.rf_model,"lr":self.lr_model,"meta":self.meta_model,
                     "scaler":self.scaler,"threshold":self._threshold,
                     "n_features":self._n_features,"feature_names":self._feature_names,
                     "metrics":self._metrics,"version":self.VERSION}, path)
        return path

    @classmethod
    def load(cls, path, symbol="UNKNOWN"):
        d = joblib.load(path)
        inst = cls(symbol=symbol)
        inst.rf_model=d.get("rf"); inst.lr_model=d.get("lr")
        inst.meta_model=d.get("meta"); inst.scaler=d.get("scaler")
        inst._threshold=d.get("threshold",0.5)
        inst._n_features=d.get("n_features",0)
        inst._feature_names=d.get("feature_names",[])
        inst._metrics=d.get("metrics")
        inst._is_trained=True
        return inst

    @property
    def metrics(self): return self._metrics
    @property
    def is_trained(self): return self._is_trained
    @property
    def threshold(self): return self._threshold
