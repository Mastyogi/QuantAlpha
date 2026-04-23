"""
Monitoring & Telemetry
=======================
Prometheus metrics + custom health tracking for the trading platform.

Metrics collected:
  - Signals generated (counter, by symbol/direction)
  - Trades executed (counter, by symbol/result)
  - P&L in USD (gauge, current value)
  - Equity curve (gauge)
  - Drawdown % (gauge)
  - API latency (histogram)
  - Exchange request latency (histogram)
  - Error rate (counter, by component)
  - Model inference time (histogram)
  - Queue depths (gauge)
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Prometheus is optional — gracefully degrade if not installed
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
        start_http_server,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed — metrics disabled")


@dataclass
class HealthStatus:
    """System health snapshot."""
    status:          str        # "healthy" / "degraded" / "critical"
    uptime_seconds:  float
    equity:          float
    drawdown_pct:    float
    open_positions:  int
    signals_today:   int
    trades_today:    int
    errors_last_hour: int
    exchange_ok:     bool
    db_ok:           bool
    telegram_ok:     bool
    last_signal_ago: Optional[float]  # seconds since last signal

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"

    def to_dict(self) -> Dict:
        return {
            "status":           self.status,
            "uptime_seconds":   self.uptime_seconds,
            "equity":           self.equity,
            "drawdown_pct":     self.drawdown_pct,
            "open_positions":   self.open_positions,
            "signals_today":    self.signals_today,
            "trades_today":     self.trades_today,
            "errors_last_hour": self.errors_last_hour,
            "components":       {
                "exchange":  self.exchange_ok,
                "database":  self.db_ok,
                "telegram":  self.telegram_ok,
            },
            "last_signal_seconds_ago": self.last_signal_ago,
        }


class Telemetry:
    """
    Central telemetry hub.
    Collects metrics, tracks health, exposes Prometheus endpoint.
    """

    def __init__(self, enable_prometheus: bool = True, prometheus_port: int = 9090):
        self._start_time = time.monotonic()
        self._enable_prom = enable_prometheus and PROMETHEUS_AVAILABLE
        self._prometheus_port = prometheus_port

        # Internal counters (always available regardless of Prometheus)
        self._counts:   Dict[str, int]   = defaultdict(int)
        self._gauges:   Dict[str, float] = defaultdict(float)
        self._timings:  Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self._errors:   Deque[Dict]      = deque(maxlen=500)

        # Component health tracking
        self._exchange_ok  = True
        self._db_ok        = True
        self._telegram_ok  = True
        self._last_signal_time: Optional[float] = None

        if self._enable_prom:
            self._setup_prometheus()
        else:
            self._prom = None

        logger.info(f"Telemetry initialized (Prometheus: {self._enable_prom})")

    # ── Signal / Trade tracking ───────────────────────────────────────────────

    def record_signal(self, symbol: str, direction: str, score: float):
        """Record a trade signal being generated."""
        self._counts["signals_total"] += 1
        self._counts[f"signals_{symbol}_{direction}"] += 1
        self._gauges["last_signal_score"] = score
        self._last_signal_time = time.monotonic()

        if self._prom:
            self._prom["signals_total"].labels(symbol=symbol, direction=direction).inc()

    def record_trade_opened(self, symbol: str, side: str, size_usd: float):
        """Record a trade being opened."""
        self._counts["trades_opened_total"] += 1
        self._gauges["open_positions"] += 1

        if self._prom:
            self._prom["trades_total"].labels(symbol=symbol, side=side, result="open").inc()

    def record_trade_closed(self, symbol: str, pnl_usd: float, win: bool):
        """Record a trade being closed."""
        self._counts["trades_closed_total"] += 1
        self._counts["wins_total" if win else "losses_total"] += 1
        self._gauges["open_positions"] = max(0, self._gauges["open_positions"] - 1)
        self._gauges["realized_pnl"] += pnl_usd

        if self._prom:
            result = "win" if win else "loss"
            self._prom["trades_total"].labels(symbol=symbol, side="closed", result=result).inc()
            self._prom["pnl_gauge"].set(self._gauges["realized_pnl"])

    def update_equity(self, equity: float, drawdown_pct: float):
        """Update equity and drawdown metrics."""
        self._gauges["equity"] = equity
        self._gauges["drawdown_pct"] = drawdown_pct

        if self._prom:
            self._prom["equity_gauge"].set(equity)
            self._prom["drawdown_gauge"].set(drawdown_pct)

    def record_error(self, component: str, error: str, critical: bool = False):
        """Record an error event."""
        self._counts["errors_total"] += 1
        self._counts[f"errors_{component}"] += 1
        self._errors.append({
            "time":      time.monotonic(),
            "component": component,
            "error":     str(error)[:200],
            "critical":  critical,
        })

        if self._prom:
            self._prom["errors_total"].labels(component=component).inc()

    # ── Latency tracking ──────────────────────────────────────────────────────

    @contextmanager
    def measure(self, operation: str):
        """Context manager to measure operation latency."""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._timings[operation].append(elapsed_ms)

            if self._prom and "latency" in self._prom:
                self._prom["latency"].labels(operation=operation).observe(elapsed_ms / 1000)

    def record_latency(self, operation: str, latency_ms: float):
        """Directly record a latency measurement."""
        self._timings[operation].append(latency_ms)

    def get_p99_latency(self, operation: str) -> float:
        """Get 99th percentile latency for an operation."""
        times = list(self._timings[operation])
        if not times:
            return 0.0
        return sorted(times)[int(len(times) * 0.99)]

    # ── Component health ──────────────────────────────────────────────────────

    def set_exchange_health(self, ok: bool):
        self._exchange_ok = ok
        if self._prom:
            self._prom["component_health"].labels(component="exchange").set(1 if ok else 0)

    def set_db_health(self, ok: bool):
        self._db_ok = ok

    def set_telegram_health(self, ok: bool):
        self._telegram_ok = ok

    # ── Health snapshot ───────────────────────────────────────────────────────

    def get_health(self) -> HealthStatus:
        """Get current system health snapshot."""
        uptime   = time.monotonic() - self._start_time
        errors_1h = sum(
            1 for e in self._errors
            if time.monotonic() - e["time"] < 3600
        )

        # Determine overall status
        if not self._exchange_ok or not self._db_ok:
            status = "critical"
        elif errors_1h > 10 or self._gauges.get("drawdown_pct", 0) > 12:
            status = "degraded"
        else:
            status = "healthy"

        last_sig = None
        if self._last_signal_time:
            last_sig = time.monotonic() - self._last_signal_time

        return HealthStatus(
            status           = status,
            uptime_seconds   = uptime,
            equity           = self._gauges.get("equity", 0),
            drawdown_pct     = self._gauges.get("drawdown_pct", 0),
            open_positions   = int(self._gauges.get("open_positions", 0)),
            signals_today    = self._counts.get("signals_total", 0),
            trades_today     = self._counts.get("trades_closed_total", 0),
            errors_last_hour = errors_1h,
            exchange_ok      = self._exchange_ok,
            db_ok            = self._db_ok,
            telegram_ok      = self._telegram_ok,
            last_signal_ago  = last_sig,
        )

    def get_metrics_dict(self) -> Dict:
        """All metrics as a plain dict (for /api/metrics endpoint)."""
        latency_summary = {}
        for op, times in self._timings.items():
            if times:
                arr = sorted(times)
                latency_summary[op] = {
                    "avg_ms":  sum(arr) / len(arr),
                    "p50_ms":  arr[len(arr) // 2],
                    "p99_ms":  arr[int(len(arr) * 0.99)],
                    "samples": len(arr),
                }

        return {
            "counters": dict(self._counts),
            "gauges":   dict(self._gauges),
            "latency":  latency_summary,
            "health":   self.get_health().to_dict(),
        }

    def start_prometheus_server(self):
        """Start standalone Prometheus HTTP server."""
        if not self._enable_prom:
            return
        try:
            start_http_server(self._prometheus_port)
            logger.info(f"Prometheus metrics server started on :{self._prometheus_port}")
        except Exception as e:
            logger.warning(f"Could not start Prometheus server: {e}")

    # ── Private ───────────────────────────────────────────────────────────────

    def _setup_prometheus(self):
        """Initialize Prometheus collectors."""
        if not PROMETHEUS_AVAILABLE:
            self._prom = None
            return

        try:
            self._prom = {
                "signals_total": Counter(
                    "trading_signals_total", "Trade signals generated",
                    ["symbol", "direction"]
                ),
                "trades_total": Counter(
                    "trading_trades_total", "Trades executed",
                    ["symbol", "side", "result"]
                ),
                "errors_total": Counter(
                    "trading_errors_total", "Errors by component",
                    ["component"]
                ),
                "equity_gauge": Gauge(
                    "trading_equity_usd", "Current portfolio equity in USD"
                ),
                "pnl_gauge": Gauge(
                    "trading_realized_pnl_usd", "Total realized P&L in USD"
                ),
                "drawdown_gauge": Gauge(
                    "trading_drawdown_pct", "Current drawdown percentage"
                ),
                "component_health": Gauge(
                    "trading_component_health", "Component health (1=ok, 0=down)",
                    ["component"]
                ),
                "latency": Histogram(
                    "trading_operation_latency_seconds", "Operation latency",
                    ["operation"],
                    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
                ),
            }
        except Exception as e:
            logger.warning(f"Prometheus setup failed: {e}")
            self._prom = None


# ── Singleton ─────────────────────────────────────────────────────────────────
telemetry = Telemetry()
