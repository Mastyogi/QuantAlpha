"""Historical trend fine-tuning pipeline"""
from __future__ import annotations
import asyncio, os, time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np, pandas as pd
from src.utils.logger import get_logger
logger = get_logger(__name__)

@dataclass
class TrendPattern:
    regime: str; direction: str; strength: float
    best_features: List[str] = field(default_factory=list)
    avg_win_rate: float = 0.0; n_samples: int = 0; window_days: int = 30

@dataclass
class FineTuneJob:
    symbol: str; window_days: int; mode: str; scheduled_at: datetime
    completed_at: Optional[datetime] = None
    new_precision: float = 0.0; old_precision: float = 0.0
    deployed: bool = False; error: Optional[str] = None

class HistoricalTrendLearner:
    WINDOWS = {"short":30,"medium":90,"long":180}

    def __init__(self, model_dir="models", min_improvement_pct=0.02, auto_deploy=True):
        self.model_dir = model_dir; self.min_improvement_pct = min_improvement_pct
        self.auto_deploy = auto_deploy
        self._tune_history: List[FineTuneJob] = []
        self._last_tune: Dict[str, datetime] = {}
        os.makedirs(model_dir, exist_ok=True)

    async def fine_tune_model(self, symbol, df_recent, current_model,
                               window_days=90, mode="medium") -> Tuple[bool, str, float]:
        job = FineTuneJob(symbol, window_days, mode, datetime.now(timezone.utc))
        try:
            from src.ai_engine.advanced_features import AdvancedFeaturePipeline
            from src.ml.stacking_ensemble import EnhancedStackingEnsemble
            from src.ml.ab_testing import ABTestFramework
            pipeline = AdvancedFeaturePipeline()
            result = pipeline.prepare_training_data(df_recent)
            if len(result) < 2: return False, "Insufficient data", 0.0
            X, y = result
            if len(X) < 100: return False, "Need >=100 samples", 0.0
            split = int(len(X)*0.8)
            new_model = EnhancedStackingEnsemble(symbol=symbol, optuna_trials=0,
                                                  use_lightgbm=False, use_xgboost=False)
            metrics = new_model.train(X[:split], y[:split], tune=False)
            new_prec = metrics.get("precision", 0.0)
            if current_model and split < len(X)-20:
                ab = ABTestFramework()
                result = ab.run_test(symbol, current_model, new_model,
                                     X[split:], y[split:], "current", f"finetune_{mode}")
                deploy = result.winner == "challenger" and self.auto_deploy
            else:
                deploy = new_prec >= 0.60
            if deploy:
                new_model.save(self.model_dir)
                job.deployed = True
            job.new_precision = new_prec; job.completed_at = datetime.now(timezone.utc)
            self._tune_history.append(job)
            self._last_tune[symbol] = datetime.now(timezone.utc)
            return deploy, "Deployed" if deploy else "Not deployed", new_prec
        except Exception as e:
            job.error = str(e); self._tune_history.append(job)
            return False, f"Error: {e}", 0.0

    def should_retrain(self, symbol, mode="medium", interval_hours=24):
        last = self._last_tune.get(symbol)
        if last is None: return True
        return (datetime.now(timezone.utc)-last).total_seconds()/3600 >= interval_hours

    def get_stats(self):
        return {"total_retrain_jobs": len(self._tune_history),
                "models_deployed": sum(1 for j in self._tune_history if j.deployed),
                "symbols_tracked": list(self._last_tune.keys())}
