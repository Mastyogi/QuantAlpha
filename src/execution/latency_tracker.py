"""Millisecond execution latency tracker"""
from __future__ import annotations
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple
import numpy as np
from src.utils.logger import get_logger
logger = get_logger(__name__)

@dataclass
class LatencyStats:
    operation: str; n_samples: int; avg_ms: float; p50_ms: float
    p95_ms: float; p99_ms: float; max_ms: float; target_ms: float

    @property
    def is_healthy(self): return self.p99_ms < self.target_ms * 3

    def to_telegram_str(self):
        ok = "✅" if self.p95_ms < self.target_ms else "⚠️"
        return f"{ok} {self.operation}: avg={self.avg_ms:.1f}ms p95={self.p95_ms:.1f}ms target={self.target_ms:.0f}ms"

class LatencyTracker:
    TARGETS = {"signal_to_order":50,"order_confirmation":200,"total_round_trip":250,
               "data_fetch":500,"indicator_compute":100,"ws_feed":50}
    WINDOW = 1000

    def __init__(self):
        self._measurements: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=self.WINDOW))
        self._start_times: Dict[str, float] = {}
        logger.info("LatencyTracker initialized")

    @contextmanager
    def measure(self, operation):
        start = time.perf_counter()
        try: yield
        finally: self._record(operation, (time.perf_counter()-start)*1000)

    def record_ms(self, operation, ms): self._record(operation, ms)
    def start_timer(self, key): self._start_times[key] = time.perf_counter()
    def stop_timer(self, key, operation):
        start = self._start_times.pop(key, None)
        if start is None: return 0.0
        ms = (time.perf_counter()-start)*1000
        self._record(operation, ms); return ms

    def record_execution(self, trade_id, symbol, side, signal_time_ms,
                         order_sent_ms, order_confirmed_ms,
                         expected_price, actual_price, size_usd):
        self._record("signal_to_order",    order_sent_ms - signal_time_ms)
        self._record("order_confirmation", order_confirmed_ms - order_sent_ms)
        self._record("total_round_trip",   order_confirmed_ms - signal_time_ms)
        slip = abs(actual_price - expected_price)/max(expected_price,1e-10)*100
        return slip

    def get_stats(self, operation) -> LatencyStats:
        data = list(self._measurements[operation])
        target = self.TARGETS.get(operation, 500)
        if not data:
            return LatencyStats(operation, 0, 0, 0, 0, 0, 0, target)
        arr = np.array(data)
        return LatencyStats(operation=operation, n_samples=len(arr),
            avg_ms=float(np.mean(arr)), p50_ms=float(np.percentile(arr,50)),
            p95_ms=float(np.percentile(arr,95)), p99_ms=float(np.percentile(arr,99)),
            max_ms=float(np.max(arr)), target_ms=target)

    def get_all_stats(self): return {op: self.get_stats(op) for op in self.TARGETS}

    def get_ux_report(self):
        lines = ["⚡ *Execution Performance*\n━━━━━━━━━━━━━━━━━━━━"]
        for op in ["signal_to_order","order_confirmation","total_round_trip","data_fetch"]:
            s = self.get_stats(op)
            if s.n_samples > 0: lines.append(s.to_telegram_str())
        return "\n".join(lines)

    def get_metrics_dict(self):
        r = {}
        for op, s in self.get_all_stats().items():
            r[f"latency_{op}_avg_ms"] = s.avg_ms
            r[f"latency_{op}_p99_ms"] = s.p99_ms
        return r

    def _record(self, op, ms): self._measurements[op].append(ms)

latency_tracker = LatencyTracker()
