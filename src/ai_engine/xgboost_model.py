import numpy as np
import os
import joblib
from typing import Tuple, Optional
from src.utils.logger import get_logger
from src.core.exceptions import ModelNotTrainedError

logger = get_logger(__name__)


class XGBoostSignalClassifier:
    """XGBoost-based trading signal classifier."""

    MODEL_DIR = "models"

    def __init__(self, symbol: str = "default"):
        self.symbol = symbol.replace("/", "_")
        self.model = None
        self.scaler = None
        self._trained = False

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train the XGBoost classifier. Returns training metrics."""
        try:
            from xgboost import XGBClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import cross_val_score
        except ImportError:
            logger.warning("XGBoost not installed, using sklearn fallback")
            return self._train_fallback(X, y)

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            use_label_encoder=False,
            random_state=42,
        )
        self.model.fit(X_scaled, y)
        self._trained = True

        scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring="accuracy")
        metrics = {
            "cv_accuracy_mean": float(scores.mean()),
            "cv_accuracy_std": float(scores.std()),
            "n_samples": len(X),
        }
        logger.info(f"XGBoost trained for {self.symbol}: accuracy={scores.mean():.3f}")
        return metrics

    def _train_fallback(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Fallback to RandomForest if XGBoost not available."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_scaled, y)
        self._trained = True

        scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring="accuracy")
        logger.info(f"RandomForest (fallback) trained: accuracy={scores.mean():.3f}")
        return {"cv_accuracy_mean": float(scores.mean()), "cv_accuracy_std": float(scores.std())}

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Return (predictions, probabilities)."""
        if not self._trained or self.model is None:
            raise ModelNotTrainedError(f"Model for {self.symbol} not trained")
        X_scaled = self.scaler.transform(X)
        preds = self.model.predict(X_scaled)
        probs = self.model.predict_proba(X_scaled)
        return preds, probs

    def predict_latest(self, X: np.ndarray) -> Tuple[int, float]:
        """Predict on the most recent row. Returns (direction, confidence)."""
        if not self._trained:
            raise ModelNotTrainedError(f"Model for {self.symbol} not trained")
        preds, probs = self.predict(X[-1:])
        direction = int(preds[0])
        confidence = float(probs[0][direction])
        return direction, confidence

    def save(self, path: Optional[str] = None):
        """Save model and scaler to disk."""
        if not self._trained:
            return
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        save_path = path or os.path.join(self.MODEL_DIR, f"xgb_{self.symbol}.joblib")
        joblib.dump({"model": self.model, "scaler": self.scaler}, save_path)
        logger.info(f"Model saved to {save_path}")

    def load(self, path: Optional[str] = None) -> bool:
        """Load model from disk. Returns True if successful."""
        load_path = path or os.path.join(self.MODEL_DIR, f"xgb_{self.symbol}.joblib")
        if not os.path.exists(load_path):
            return False
        try:
            data = joblib.load(load_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._trained = True
            logger.info(f"Model loaded from {load_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
