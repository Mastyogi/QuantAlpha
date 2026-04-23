import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional
from src.ai_engine.feature_pipeline import FeaturePipeline
from src.ai_engine.xgboost_model import XGBoostSignalClassifier
from src.core.exceptions import ModelNotTrainedError
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class AIResult:
    direction: str       # "BUY" | "SELL" | "NEUTRAL"
    confidence: float    # 0.0 - 1.0
    raw_prediction: int  # 0 or 1
    features_used: int


class ModelPredictor:
    """
    Runs ML model inference to generate directional predictions with confidence scores.
    Auto-trains a simple model if no saved model exists.
    """

    def __init__(self):
        self.pipeline = FeaturePipeline()
        self._models: Dict[str, XGBoostSignalClassifier] = {}

    async def load_models(self):
        """Load all saved models for configured trading pairs."""
        for symbol in settings.trading_pairs:
            model = XGBoostSignalClassifier(symbol=symbol)
            if model.load():
                self._models[symbol] = model
                logger.info(f"Model loaded for {symbol}")
            else:
                logger.warning(f"No saved model for {symbol} — will auto-train on first data")

    async def predict(self, df: pd.DataFrame, symbol: str) -> AIResult:
        """
        Run inference on the latest data.
        Auto-trains if model not available.
        """
        try:
            model = self._get_or_create_model(symbol)
            if not model._trained:
                logger.info(f"Auto-training model for {symbol}...")
                X, y = self.pipeline.prepare_training_data(df)
                if len(X) < 50:
                    return AIResult(direction="NEUTRAL", confidence=0.0, raw_prediction=0, features_used=0)
                model.train(X, y)
                model.save()
                self._models[symbol] = model

            # Extract features for latest candle
            features = self.pipeline.extract_features(df)
            if features.empty:
                return AIResult(direction="NEUTRAL", confidence=0.0, raw_prediction=0, features_used=0)

            X_latest = features.values
            direction_int, confidence = model.predict_latest(X_latest)

            # Map to direction
            if confidence < settings.ai_confidence_threshold:
                direction = "NEUTRAL"
            else:
                direction = "BUY" if direction_int == 1 else "SELL"

            return AIResult(
                direction=direction,
                confidence=confidence,
                raw_prediction=direction_int,
                features_used=X_latest.shape[1],
            )

        except ModelNotTrainedError:
            return AIResult(direction="NEUTRAL", confidence=0.0, raw_prediction=0, features_used=0)
        except Exception as e:
            logger.error(f"Model prediction failed for {symbol}: {e}")
            return AIResult(direction="NEUTRAL", confidence=0.0, raw_prediction=0, features_used=0)

    def _get_or_create_model(self, symbol: str) -> XGBoostSignalClassifier:
        if symbol not in self._models:
            self._models[symbol] = XGBoostSignalClassifier(symbol=symbol)
        return self._models[symbol]

    async def retrain_all(self, data_fetcher, symbols: list):
        """Retrain all models with fresh data."""
        for symbol in symbols:
            try:
                df = await data_fetcher.get_dataframe(symbol, settings.primary_timeframe, limit=500)
                model = self._get_or_create_model(symbol)
                X, y = self.pipeline.prepare_training_data(df)
                if len(X) >= 50:
                    model.train(X, y)
                    model.save()
                    logger.info(f"Retrained model for {symbol}")
            except Exception as e:
                logger.error(f"Failed to retrain {symbol}: {e}")
