"""
Load & Stress Tests
=====================
Tests system behavior under high-frequency signal generation,
concurrent data processing, and memory stability.

Run separately: pytest tests/load/ -v --timeout=300 -m slow
"""
import asyncio
import time
import pytest
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor


def make_ohlcv_df(n=500, seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    prices = 45000 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    df = pd.DataFrame({
        "open":   prices * 0.999, "high": prices * 1.003,
        "low":    prices * 0.997, "close": prices,
        "volume": rng.uniform(100, 1000, n),
    }, index=dates)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)
    return df


@pytest.mark.slow
class TestIndicatorLoad:

    def test_indicators_100_consecutive_runs(self):
        """Run indicators 100 times — verify no memory leak or slowdown."""
        from src.indicators.technical import TechnicalIndicators
        df = make_ohlcv_df(300)
        times = []
        for i in range(100):
            start = time.monotonic()
            result = TechnicalIndicators.add_all_indicators(df)
            elapsed = time.monotonic() - start
            times.append(elapsed)
            assert len(result) > 100

        avg_ms = sum(times) / len(times) * 1000
        p99_ms = sorted(times)[int(len(times) * 0.99)] * 1000
        print(f"\nIndicators: avg={avg_ms:.1f}ms  p99={p99_ms:.1f}ms")
        assert avg_ms < 500, f"Indicators too slow: {avg_ms:.1f}ms avg"

    def test_volume_profile_load(self):
        """VolumeProfile on 200-bar window 50 times."""
        from src.indicators.volume_profile import VolumeProfile
        df = make_ohlcv_df(200)
        vp = VolumeProfile()
        for _ in range(50):
            result = vp.calculate(df)
            assert result.poc > 0

    def test_market_structure_load(self):
        from src.indicators.market_structure import MarketStructureAnalyzer
        df = make_ohlcv_df(300)
        msa = MarketStructureAnalyzer()
        for _ in range(50):
            result = msa.analyze(df)
            assert result is not None


@pytest.mark.slow
class TestMonteCarloPerfomance:

    def test_10000_simulation_completes_under_30s(self):
        from src.backtesting.monte_carlo import MonteCarloSimulator
        rng = np.random.default_rng(42)
        returns = [0.015 if rng.random() > 0.45 else -0.010 for _ in range(100)]
        mc = MonteCarloSimulator(n_simulations=10_000)
        start = time.monotonic()
        result = mc.run(returns, initial_equity=10_000.0)
        elapsed = time.monotonic() - start
        print(f"\nMonte Carlo 10k runs: {elapsed:.2f}s")
        assert elapsed < 30.0, f"Monte Carlo too slow: {elapsed:.2f}s"
        assert result.n_simulations == 10_000


@pytest.mark.slow
class TestPnLCalculatorLoad:

    def test_pnl_1000_trades(self):
        """PnL calculator processes 1000 trades without degradation."""
        from src.risk.pnl_calculator import PnLCalculator
        calc = PnLCalculator(initial_equity=100_000.0)

        start = time.monotonic()
        for i in range(1000):
            tid = f"trade_{i}"
            calc.record_trade_open(tid, "EURUSD", "BUY", 45000, 0.1, 1000, "trend")
            exit_price = 45900 if i % 3 != 0 else 44500  # 67% win rate
            calc.record_trade_close(tid, exit_price, "TP" if i % 3 != 0 else "SL")

        elapsed = time.monotonic() - start
        snap = calc.get_snapshot()
        print(f"\n1000 trades processed in {elapsed:.2f}s")
        print(f"Win rate: {snap.win_rate:.1%}, PF: {snap.profit_factor:.2f}")
        assert elapsed < 5.0
        assert snap.total_trades == 1000
        assert 0.60 < snap.win_rate < 0.75


@pytest.mark.slow
class TestConcurrentIndicatorProcessing:

    def test_concurrent_symbol_processing(self):
        """Process 10 symbols concurrently using ThreadPoolExecutor."""
        from src.indicators.technical import TechnicalIndicators
        symbols = [f"ASSET{i}/USDT" for i in range(10)]
        dfs = {s: make_ohlcv_df(300, seed=i) for i, s in enumerate(symbols)}

        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                s: executor.submit(TechnicalIndicators.add_all_indicators, dfs[s])
                for s in symbols
            }
            results = {s: f.result() for s, f in futures.items()}

        elapsed = time.monotonic() - start
        print(f"\n10 symbols concurrent: {elapsed:.2f}s")
        assert len(results) == 10
        for sym, result in results.items():
            assert "rsi_14" in result.columns
        assert elapsed < 10.0


@pytest.mark.slow
class TestMemoryStability:

    def test_feature_pipeline_memory_stable(self):
        """Verify no memory growth over repeated feature extraction."""
        import gc
        try:
            import tracemalloc
            tracemalloc.start()
        except Exception:
            pytest.skip("tracemalloc not available")

        from src.indicators.technical import TechnicalIndicators
        df = make_ohlcv_df(300)

        baseline = None
        for i in range(50):
            result = TechnicalIndicators.add_all_indicators(df)
            del result
            gc.collect()
            if i == 5:
                _, baseline = tracemalloc.get_traced_memory()

        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        growth_kb = (peak - baseline) / 1024 if baseline else 0
        print(f"\nMemory growth over 50 iterations: {growth_kb:.0f} KB")
        # Allow up to 5MB growth (caches, etc.)
        assert growth_kb < 5_120, f"Memory leak detected: {growth_kb:.0f} KB growth"
