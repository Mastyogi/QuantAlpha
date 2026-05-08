"""Continuous retraining daemon"""
from __future__ import annotations
import asyncio, os, time
from datetime import datetime, timezone
from typing import Dict, Optional
from src.utils.logger import get_logger
logger = get_logger(__name__)

SCHEDULE = {"light":12,"medium":72,"full":168}

class ContinuousTrainer:
    def __init__(self, data_feed=None, model_dir="models", symbols=None,
                 confluence_threshold=82, optuna_trials=50):
        self.feed = data_feed; self.model_dir = model_dir
        self.symbols = symbols or ["EURUSD","GBPUSD","USDJPY"]
        self.confluence_threshold = confluence_threshold
        self.optuna_trials = optuna_trials
        self._models: Dict[str,object] = {}
        self._last_run: Dict[str,Dict[str,float]] = {}
        self._retrain_log = []; self._running = False
        os.makedirs(model_dir, exist_ok=True)

    async def start(self):
        self._running = True
        asyncio.create_task(self._daemon_loop())
        logger.info(f"ContinuousTrainer started confluence>={self.confluence_threshold}")

    async def stop(self): self._running = False

    def register_model(self, sym, model): self._models[sym] = model

    async def _daemon_loop(self):
        while self._running:
            for sym in self.symbols:
                for mode, interval_h in SCHEDULE.items():
                    last = self._last_run.get(sym, {}).get(mode, 0)
                    if time.time() - last >= interval_h * 3600:
                        await self._retrain(sym, mode)
            await asyncio.sleep(600)

    async def _retrain(self, sym, mode):
        try:
            if self.feed is None: return {"success": False}
            from src.ai_engine.advanced_features import AdvancedFeaturePipeline
            from src.ml.stacking_ensemble import EnhancedStackingEnsemble
            bars = {"light":720,"medium":2160,"full":4320}[mode]
            df = self.feed.get_history_df(sym, bars=min(bars,600))
            if df is None or len(df) < 120: return {"success": False}
            pipeline = AdvancedFeaturePipeline()
            result = pipeline.prepare_training_data(df)
            if len(result) < 2: return {"success": False}
            X, y = result
            if len(X) < 100: return {"success": False}
            new_model = EnhancedStackingEnsemble(symbol=sym, optuna_trials=0,
                                                  use_lightgbm=False, use_xgboost=False)
            metrics = new_model.train(X[:int(len(X)*0.8)], y[:int(len(y)*0.8)], tune=False)
            new_prec = metrics.get("precision", 0.0)
            if new_prec >= 0.55:
                new_model.save(self.model_dir)
                self._models[sym] = new_model
                logger.info(f"Retrained {sym} mode={mode} prec={new_prec:.1%}")
            record = {"ts": datetime.now(timezone.utc).isoformat(), "sym":sym,
                      "mode":mode, "prec":new_prec}
            self._retrain_log.append(record)
            if sym not in self._last_run: self._last_run[sym] = {}
            self._last_run[sym][mode] = time.time()
            return record
        except Exception as e:
            logger.error(f"Retrain {sym}: {e}")
            return {"success": False}

    def get_stats(self):
        return {"total_runs": len(self._retrain_log),
                "symbols": list(self._models.keys()),
                "log": self._retrain_log[-5:]}
