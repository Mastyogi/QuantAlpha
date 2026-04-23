"""Train initial ML models using live or simulated data."""
import asyncio
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def train_with_synthetic_data(symbol: str):
    """Train model with synthetic data if exchange unavailable."""
    from src.ai_engine.feature_pipeline import FeaturePipeline
    from src.ai_engine.xgboost_model import XGBoostSignalClassifier

    print(f"  Training {symbol} with synthetic data...")
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    prices = 45000 * np.exp(np.cumsum(np.random.normal(0, 0.003, n)))

    df = pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.003,
        "low": prices * 0.997,
        "close": prices,
        "volume": np.random.uniform(100, 1000, n),
    }, index=dates)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)

    pipeline = FeaturePipeline()
    X, y = pipeline.prepare_training_data(df)
    if len(X) < 50:
        print(f"  Insufficient data for {symbol}")
        return

    model = XGBoostSignalClassifier(symbol=symbol)
    metrics = model.train(X, y)
    model.save()
    print(f"  ✅ {symbol}: accuracy={metrics.get('cv_accuracy_mean', 0):.3f}")


async def main():
    from config.settings import settings
    from src.utils.logger import setup_logging
    setup_logging()

    print("=" * 50)
    print("Training initial ML models...")
    print("=" * 50)

    os.makedirs("models", exist_ok=True)
    for symbol in settings.trading_pairs:
        await train_with_synthetic_data(symbol)

    print("\n✅ Model training complete!")


if __name__ == "__main__":
    asyncio.run(main())
