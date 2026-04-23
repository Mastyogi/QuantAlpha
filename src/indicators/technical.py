import pandas as pd
import numpy as np
from typing import Tuple
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalIndicators:
    """
    Computes 20+ technical indicators on OHLCV DataFrames.
    All computations are vectorized — no loops for performance.
    """

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all indicators. Returns DataFrame with NaN rows dropped."""
        df = df.copy()

        # ── Moving Averages ─────────────────────────────────────
        for period in [9, 21, 50, 200]:
            df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
        df["sma_20"] = df["close"].rolling(20).mean()

        # ── VWAP ────────────────────────────────────────────────
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

        # ── RSI ─────────────────────────────────────────────────
        df["rsi_14"] = TechnicalIndicators._rsi(df["close"], 14)
        df["rsi_7"] = TechnicalIndicators._rsi(df["close"], 7)

        # ── MACD ────────────────────────────────────────────────
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # ── Bollinger Bands ─────────────────────────────────────
        bb_mid = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        df["bb_upper"] = bb_mid + 2 * bb_std
        df["bb_lower"] = bb_mid - 2 * bb_std
        df["bb_middle"] = bb_mid
        df["bb_bandwidth"] = (df["bb_upper"] - df["bb_lower"]) / bb_mid
        df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        # ── ATR ─────────────────────────────────────────────────
        df["atr_14"] = TechnicalIndicators._atr(df, 14)
        df["atr_pct"] = df["atr_14"] / df["close"]

        # ── Stochastic ──────────────────────────────────────────
        low_14 = df["low"].rolling(14).min()
        high_14 = df["high"].rolling(14).max()
        df["stoch_k"] = 100 * (df["close"] - low_14) / (high_14 - low_14 + 1e-10)
        df["stoch_d"] = df["stoch_k"].rolling(3).mean()

        # ── Volume ──────────────────────────────────────────────
        df["volume_sma"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"].replace(0, np.nan)

        # ── OBV ─────────────────────────────────────────────────
        price_diff = df["close"].diff()
        obv = np.where(price_diff > 0, df["volume"],
               np.where(price_diff < 0, -df["volume"], 0))
        df["obv"] = pd.Series(obv, index=df.index).cumsum()

        # ── ADX / DMI ───────────────────────────────────────────
        adx_data = TechnicalIndicators._adx(df, 14)
        df["adx"] = adx_data["adx"]
        df["dmi_plus"] = adx_data["dmi_plus"]
        df["dmi_minus"] = adx_data["dmi_minus"]

        # ── Market Structure ────────────────────────────────────
        df["higher_high"] = df["high"] > df["high"].shift(1)
        df["lower_low"] = df["low"] < df["low"].shift(1)
        df["trend_up"] = (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"])
        df["trend_down"] = (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"])

        # ── Composite Signal Score ──────────────────────────────
        df["signal_score"] = TechnicalIndicators._calculate_signal_score(df)

        return df.dropna(subset=["rsi_14", "macd", "atr_14", "bb_upper", "bb_middle", "bb_lower", "adx"])

    @staticmethod
    def _rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def _adx(df: pd.DataFrame, period: int) -> dict:
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr = TechnicalIndicators._atr(df, 1)
        tr_smooth = tr.rolling(period).sum()
        plus_smooth = plus_dm.rolling(period).sum()
        minus_smooth = minus_dm.rolling(period).sum()

        dmi_plus = 100 * plus_smooth / tr_smooth.replace(0, np.nan)
        dmi_minus = 100 * minus_smooth / tr_smooth.replace(0, np.nan)

        dx = 100 * (dmi_plus - dmi_minus).abs() / (dmi_plus + dmi_minus).replace(0, np.nan)
        adx = dx.rolling(period).mean()

        return {"adx": adx, "dmi_plus": dmi_plus, "dmi_minus": dmi_minus}

    @staticmethod
    def _calculate_signal_score(df: pd.DataFrame) -> pd.Series:
        """
        Composite bullish/bearish score from -100 (strong bear) to +100 (strong bull).
        """
        score = pd.Series(0.0, index=df.index)

        # RSI contribution (±25 points)
        score += np.where(df["rsi_14"] < 30, 25,
                 np.where(df["rsi_14"] > 70, -25,
                 np.where(df["rsi_14"] < 45, 10,
                 np.where(df["rsi_14"] > 55, -10, 0))))

        # MACD contribution (±20 points)
        score += np.where(
            (df["macd"] > df["macd_signal"]) & (df["macd_hist"] > 0), 20,
            np.where(
                (df["macd"] < df["macd_signal"]) & (df["macd_hist"] < 0), -20, 0
            )
        )

        # EMA trend (±25 points)
        score += np.where(df["trend_up"], 25, np.where(df["trend_down"], -25, 0))

        # Volume confirmation (±15 points)
        score += np.where(df["volume_ratio"] > 1.5, 15,
                 np.where(df["volume_ratio"] < 0.5, -5, 0))

        # Bollinger Band (±15 points)
        score += np.where(df["bb_pct"] < 0.2, 15,
                 np.where(df["bb_pct"] > 0.8, -15, 0))

        return score.clip(-100, 100)

    @staticmethod
    def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> Tuple[float, float]:
        """Calculate key S/R levels using rolling highs/lows."""
        recent = df.tail(window * 2)
        resistance = recent["high"].rolling(window).max().iloc[-1]
        support = recent["low"].rolling(window).min().iloc[-1]
        return float(support), float(resistance)

    @staticmethod
    def detect_divergence(df: pd.DataFrame) -> pd.Series:
        """Detect RSI divergence (bullish/bearish)."""
        divergence = pd.Series("none", index=df.index)
        for i in range(3, len(df)):
            price_higher_high = df["close"].iloc[i] > df["close"].iloc[i - 3]
            rsi_lower_high = df["rsi_14"].iloc[i] < df["rsi_14"].iloc[i - 3]
            if price_higher_high and rsi_lower_high and df["rsi_14"].iloc[i] > 60:
                divergence.iloc[i] = "bearish"

            price_lower_low = df["close"].iloc[i] < df["close"].iloc[i - 3]
            rsi_higher_low = df["rsi_14"].iloc[i] > df["rsi_14"].iloc[i - 3]
            if price_lower_low and rsi_higher_low and df["rsi_14"].iloc[i] < 40:
                divergence.iloc[i] = "bullish"
        return divergence
