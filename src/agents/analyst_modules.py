"""
Layer 2: Specialized Analyst Modules
=====================================
Implements PDF spec: Fundamental, Sentiment, Technical, On-Chain analysts
Each returns a structured AnalystReport used by the Debate Engine.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from src.utils.logger import get_logger
logger = get_logger(__name__)


@dataclass
class AnalystReport:
    """Unified report from any analyst module."""
    analyst_type:  str          # "fundamental" | "sentiment" | "technical" | "on_chain"
    symbol:        str
    direction:     str          # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence:    float        # 0.0 – 1.0
    key_insight:   str          # One-liner for Telegram
    detail:        str          # Full reasoning
    score:         float        # 0–100 contribution score
    timestamp:     str = ""
    supporting:    List[str] = field(default_factory=list)
    risks:         List[str]    = field(default_factory=list)

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def is_bullish(self) -> bool: return self.direction == "BULLISH"
    @property
    def is_bearish(self) -> bool: return self.direction == "BEARISH"


# ── Technical Analyst ─────────────────────────────────────────────────────────

class TechnicalAnalystModule:
    """
    Analyses: EMAs, RSI, MACD, Bollinger Bands, Volume Profile, ATR, trend.
    Outputs structured AnalystReport with entry/sl/tp suggestions.
    """

    def analyze(self, df: pd.DataFrame, symbol: str) -> AnalystReport:
        if len(df) < 65:
            return self._neutral(symbol, "Insufficient data")
        try:
            return self._full_analysis(df, symbol)
        except Exception as e:
            logger.warning(f"TechnicalAnalyst {symbol}: {e}")
            return self._neutral(symbol, f"Analysis error: {e}")

    def _full_analysis(self, df: pd.DataFrame, symbol: str) -> AnalystReport:
        c = df["close"]; h = df["high"]; l = df["low"]; v = df["volume"]
        w = df.tail(100)
        cw = w["close"]; hw = w["high"]; lw = w["low"]; vw = w["volume"]

        # EMAs
        e9  = float(cw.ewm(span=9,  adjust=False).mean().iloc[-1])
        e21 = float(cw.ewm(span=21, adjust=False).mean().iloc[-1])
        e50 = float(cw.ewm(span=50, adjust=False).mean().iloc[-1])
        e200= float(c.ewm(span=200, adjust=False).mean().iloc[-1]) if len(c) >= 200 else e50
        curr = float(cw.iloc[-1])

        # RSI
        d    = cw.diff()
        gain = d.clip(lower=0).rolling(14).mean()
        loss = -d.clip(upper=0).rolling(14).mean().replace(0, 1e-10)
        rsi  = float((100 - 100 / (1 + gain / loss)).iloc[-1])

        # MACD
        macd_line   = cw.ewm(span=12).mean() - cw.ewm(span=26).mean()
        macd_signal = macd_line.ewm(span=9).mean()
        macd_hist   = float((macd_line - macd_signal).iloc[-1])
        macd_val    = float(macd_line.iloc[-1])

        # ATR
        hl_  = hw - lw
        hc_  = (hw - cw.shift()).abs()
        lc_  = (lw - cw.shift()).abs()
        atr  = float(pd.concat([hl_, hc_, lc_], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
        atr_pct = atr / curr * 100

        # Bollinger Bands
        sma20   = float(cw.rolling(20).mean().iloc[-1])
        std20   = float(cw.rolling(20).std().iloc[-1])
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_pos   = (curr - bb_lower) / max(bb_upper - bb_lower, 1e-10)  # 0=lower, 1=upper

        # Volume
        vol_ratio = float(vw.iloc[-1] / max(vw.rolling(20).mean().iloc[-1], 1e-10))

        # Trend
        ema_stack_bull = e9 > e21 > e50
        ema_stack_bear = e9 < e21 < e50
        above_200      = curr > e200

        # Scoring
        score = 0.0
        supporting = []; risks = []

        if ema_stack_bull:
            score += 25; supporting.append(f"EMA stack bullish (9>{21}>{50})")
        elif ema_stack_bear:
            score -= 25; risks.append(f"EMA stack bearish")

        if above_200:
            score += 10; supporting.append("Price above EMA200 (macro bull)")
        else:
            score -= 10; risks.append("Price below EMA200")

        if 30 < rsi < 50:
            score += 15; supporting.append(f"RSI={rsi:.0f} (oversold pullback)")
        elif 50 < rsi < 70:
            score += 10; supporting.append(f"RSI={rsi:.0f} (bullish momentum)")
        elif rsi < 30:
            score += 20; supporting.append(f"RSI={rsi:.0f} oversold — reversal watch")
        elif rsi > 70:
            score -= 15; risks.append(f"RSI={rsi:.0f} overbought")

        if macd_hist > 0:
            score += 12; supporting.append(f"MACD histogram positive (+{macd_hist:.2f})")
        else:
            score -= 12; risks.append(f"MACD histogram negative ({macd_hist:.2f})")

        if vol_ratio > 1.5:
            score += 10; supporting.append(f"Volume spike {vol_ratio:.1f}x avg")
        elif vol_ratio > 1.2:
            score += 5; supporting.append(f"Volume elevated {vol_ratio:.1f}x avg")

        # Determine direction
        if score > 15:
            direction = "BULLISH"
            key = f"EMA bullish stack + RSI={rsi:.0f} + MACD {'↑' if macd_hist>0 else '↓'}"
        elif score < -15:
            direction = "BEARISH"
            key = f"EMA bearish stack + RSI={rsi:.0f} + MACD {'↑' if macd_hist>0 else '↓'}"
        else:
            direction = "NEUTRAL"
            key = f"Mixed signals: RSI={rsi:.0f} MACD={macd_hist:+.2f}"

        sl_dist = atr * 1.3
        tp_dist = atr * 5.5
        sl = curr - sl_dist if direction == "BULLISH" else curr + sl_dist
        tp = curr + tp_dist if direction == "BULLISH" else curr - tp_dist

        detail = (
            f"Price={curr:.4g} | EMA(9/21/50)={e9:.4g}/{e21:.4g}/{e50:.4g} | "
            f"RSI={rsi:.1f} | MACD_hist={macd_hist:+.4f} | BB_pos={bb_pos:.2f} | "
            f"ATR={atr:.4g}({atr_pct:.2f}%) | VolRatio={vol_ratio:.2f}x | "
            f"Suggested: Entry={curr:.4g} SL={sl:.4g} TP={tp:.4g}"
        )

        conf = min(abs(score) / 60, 1.0)
        return AnalystReport(
            analyst_type="technical", symbol=symbol, direction=direction,
            confidence=conf, key_insight=key, detail=detail,
            score=float(np.clip(score + 50, 0, 100)),
            supporting=supporting, risks=risks,
        )

    def _neutral(self, symbol, reason):
        return AnalystReport("technical", symbol, "NEUTRAL", 0.3, reason, reason, 50.0)


# ── Fundamental Analyst ───────────────────────────────────────────────────────

class FundamentalAnalystModule:
    """
    Simulates macro analysis for crypto: market cap dominance, funding rates,
    long/short ratio, open interest trends, macro regime.
    In live deployment would pull real data from CoinGlass, Glassnode, etc.
    """

    def analyze(self, df: pd.DataFrame, symbol: str,
                market_context: Optional[dict] = None) -> AnalystReport:
        try:
            return self._analyze_impl(df, symbol, market_context or {})
        except Exception as e:
            return AnalystReport("fundamental", symbol, "NEUTRAL", 0.3,
                                  f"Fundamental: {e}", str(e), 50.0)

    def _analyze_impl(self, df, symbol, ctx):
        c = df["close"]; v = df["volume"]

        # Simulated fundamental signals (in prod: real API calls)
        funding_rate   = ctx.get("funding_rate",    float(np.random.default_rng(hash(symbol)%999).uniform(-0.003, 0.003)))
        oi_change      = ctx.get("oi_change_pct",   float(np.random.default_rng(hash(symbol)%777).uniform(-5, 5)))
        btc_dominance  = ctx.get("btc_dominance",   float(np.random.default_rng(42).uniform(48, 55)))
        long_short_ratio = ctx.get("long_short_ratio", float(np.random.default_rng(hash(symbol)%555).uniform(0.8, 1.6)))
        # Volume trend 7d
        vol_7d_avg  = float(v.tail(84).mean()) if len(v) >= 84 else float(v.mean())
        vol_1d_avg  = float(v.tail(12).mean()) if len(v) >= 12 else float(v.mean())
        vol_trend   = vol_1d_avg / max(vol_7d_avg, 1e-10) - 1

        # Price trend 30d
        price_30d = float(c.iloc[-min(len(c), 360)] if len(c) > 360 else c.iloc[0])
        price_now = float(c.iloc[-1])
        pct_30d   = (price_now - price_30d) / max(price_30d, 1e-10) * 100

        score = 50.0
        supporting = []; risks = []

        # Funding rate: negative = bearish bets = contrarian bullish signal
        if funding_rate < -0.001:
            score += 12; supporting.append(f"Negative funding {funding_rate*100:.3f}% (shorts dominant → squeeze risk)")
        elif funding_rate > 0.002:
            score -= 10; risks.append(f"High positive funding {funding_rate*100:.3f}% (longs heavy → flush risk)")

        # Long/Short ratio
        if long_short_ratio < 0.9:
            score += 10; supporting.append(f"L/S ratio {long_short_ratio:.2f} — shorts dominant")
        elif long_short_ratio > 1.3:
            score -= 8; risks.append(f"L/S ratio {long_short_ratio:.2f} — longs crowded")

        # OI change
        if oi_change > 2:
            score += 8; supporting.append(f"OI rising +{oi_change:.1f}% — new money in")
        elif oi_change < -3:
            score -= 10; risks.append(f"OI falling {oi_change:.1f}% — deleveraging")

        # Volume trend
        if vol_trend > 0.3:
            score += 8; supporting.append(f"Volume surging +{vol_trend*100:.0f}% vs 7d avg")
        elif vol_trend < -0.3:
            score -= 5; risks.append(f"Volume declining {vol_trend*100:.0f}% vs 7d avg")

        # Macro 30d trend
        if pct_30d > 10:
            score += 6; supporting.append(f"30d performance +{pct_30d:.1f}%")
        elif pct_30d < -15:
            score -= 8; risks.append(f"30d down {pct_30d:.1f}%")

        if score > 60:
            direction, conf = "BULLISH", min((score-50)/30, 1.0)
        elif score < 40:
            direction, conf = "BEARISH", min((50-score)/30, 1.0)
        else:
            direction, conf = "NEUTRAL", 0.3

        key = f"Fund: funding={funding_rate*100:.3f}% L/S={long_short_ratio:.2f} OI={oi_change:+.1f}%"
        detail = (
            f"Funding={funding_rate*100:.4f}% | OI_chg={oi_change:+.1f}% | "
            f"L/S={long_short_ratio:.2f} | BTC.dom={btc_dominance:.1f}% | "
            f"VolTrend={vol_trend*100:+.0f}% | 30d={pct_30d:+.1f}%"
        )

        return AnalystReport(
            analyst_type="fundamental", symbol=symbol, direction=direction,
            confidence=conf, key_insight=key, detail=detail, score=float(score),
            supporting=supporting, risks=risks,
        )


# ── Sentiment Analyst ─────────────────────────────────────────────────────────

class SentimentAnalystModule:
    """
    Analyses market sentiment: Fear & Greed index, social volume,
    news sentiment, momentum. In prod: real API feeds.
    """

    def analyze(self, df: pd.DataFrame, symbol: str,
                sentiment_data: Optional[dict] = None) -> AnalystReport:
        try:
            return self._analyze_impl(df, symbol, sentiment_data or {})
        except Exception as e:
            return AnalystReport("sentiment", symbol, "NEUTRAL", 0.3,
                                  f"Sentiment: {e}", str(e), 50.0)

    def _analyze_impl(self, df, symbol, sd):
        rng = np.random.default_rng(hash(symbol) % 8888)
        fear_greed     = sd.get("fear_greed_index", float(rng.integers(20, 80)))
        social_volume  = sd.get("social_volume_change", float(rng.uniform(-30, 60)))
        news_sentiment = sd.get("news_sentiment", float(rng.uniform(-0.3, 0.5)))  # -1 to 1
        twitter_mentions = sd.get("twitter_mentions_change", float(rng.uniform(-20, 50)))

        # Price momentum as proxy
        c = df["close"]
        ret_1h  = float((c.iloc[-1] - c.iloc[-2]) / max(c.iloc[-2], 1e-10) * 100) if len(c) >= 2 else 0
        ret_24h = float((c.iloc[-1] - c.iloc[-min(len(c),25)]) / max(c.iloc[-min(len(c),25)], 1e-10) * 100)
        ret_7d  = float((c.iloc[-1] - c.iloc[-min(len(c),169)]) / max(c.iloc[-min(len(c),169)], 1e-10) * 100)

        score = 50.0
        supporting = []; risks = []

        # Fear & Greed (contrarian beyond extremes)
        if fear_greed < 25:
            score += 15; supporting.append(f"Fear & Greed={fear_greed:.0f} (Extreme Fear → contrarian BUY)")
        elif fear_greed < 40:
            score += 8; supporting.append(f"Fear & Greed={fear_greed:.0f} (Fear zone)")
        elif fear_greed > 75:
            score -= 12; risks.append(f"Fear & Greed={fear_greed:.0f} (Extreme Greed → caution)")
        elif fear_greed > 60:
            score += 5; supporting.append(f"Fear & Greed={fear_greed:.0f} (Greed zone)")

        # Social volume
        if social_volume > 30:
            score += 8; supporting.append(f"Social buzz +{social_volume:.0f}%")
        elif social_volume < -20:
            score -= 6; risks.append(f"Social volume declining {social_volume:.0f}%")

        # News sentiment
        if news_sentiment > 0.2:
            score += 10; supporting.append(f"Positive news sentiment {news_sentiment:+.2f}")
        elif news_sentiment < -0.2:
            score -= 10; risks.append(f"Negative news sentiment {news_sentiment:+.2f}")

        # Price momentum
        if ret_24h > 3:
            score += 6; supporting.append(f"24h +{ret_24h:.1f}% momentum")
        elif ret_24h < -5:
            score -= 8; risks.append(f"24h {ret_24h:.1f}% sell-off")

        if score > 60:
            direction, conf = "BULLISH", min((score-50)/25, 1.0)
        elif score < 40:
            direction, conf = "BEARISH", min((50-score)/25, 1.0)
        else:
            direction, conf = "NEUTRAL", 0.3

        key = f"Sent: F&G={fear_greed:.0f} Social={social_volume:+.0f}% News={news_sentiment:+.2f}"
        detail = (
            f"FearGreed={fear_greed:.0f} | SocialVol={social_volume:+.0f}% | "
            f"NewsSent={news_sentiment:+.2f} | TwitterChg={twitter_mentions:+.0f}% | "
            f"1h={ret_1h:+.2f}% 24h={ret_24h:+.1f}% 7d={ret_7d:+.1f}%"
        )

        return AnalystReport(
            analyst_type="sentiment", symbol=symbol, direction=direction,
            confidence=conf, key_insight=key, detail=detail, score=float(score),
            supporting=supporting, risks=risks,
        )


# ── On-Chain Analyst (Crypto) ─────────────────────────────────────────────────

class OnChainAnalystModule:
    """
    Analyses: whale movements, exchange flows, MVRV, NVT, active addresses.
    In prod: Glassnode / Nansen API. In sandbox: calibrated simulation.
    """

    CRYPTO_SYMBOLS = {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
                       "BTC/USD", "ETH/USD", "SOL/USD"}

    def analyze(self, df: pd.DataFrame, symbol: str,
                chain_data: Optional[dict] = None) -> AnalystReport:
        if symbol not in self.CRYPTO_SYMBOLS:
            return AnalystReport("on_chain", symbol, "NEUTRAL", 0.5,
                                  "N/A — not a tracked crypto", "N/A", 50.0)
        try:
            return self._analyze_impl(df, symbol, chain_data or {})
        except Exception as e:
            return AnalystReport("on_chain", symbol, "NEUTRAL", 0.3,
                                  f"OnChain: {e}", str(e), 50.0)

    def _analyze_impl(self, df, symbol, cd):
        rng = np.random.default_rng(hash(symbol) % 5555)

        # Simulated on-chain metrics (prod: Glassnode API)
        exchange_inflow_chg  = cd.get("exchange_inflow_change", float(rng.uniform(-20, 20)))   # % chg vs 7d avg
        exchange_outflow_chg = cd.get("exchange_outflow_change", float(rng.uniform(-15, 25)))  # bullish if outflow rising
        whale_txns           = cd.get("whale_transactions_count", int(rng.integers(10, 80)))   # >100K USD
        active_addr_chg      = cd.get("active_addresses_change", float(rng.uniform(-5, 15)))   # % chg 24h
        mvrv_z_score         = cd.get("mvrv_z_score", float(rng.uniform(-1, 4)))
        sopr                 = cd.get("sopr", float(rng.uniform(0.97, 1.05)))                  # >1 = profit, <1 = loss
        net_flow             = exchange_outflow_chg - exchange_inflow_chg                       # positive = accumulation

        score = 50.0
        supporting = []; risks = []

        # Exchange flows: outflow > inflow = accumulation = bullish
        if net_flow > 10:
            score += 15; supporting.append(f"Net exchange outflow +{net_flow:.0f}% (accumulation)")
        elif net_flow > 5:
            score += 8; supporting.append(f"Slight accumulation (outflow > inflow)")
        elif net_flow < -10:
            score -= 15; risks.append(f"Net exchange inflow {net_flow:.0f}% (distribution/selling)")
        elif net_flow < -5:
            score -= 8; risks.append(f"Mild distribution (inflow > outflow)")

        # Whale transactions
        if whale_txns > 60:
            score += 10; supporting.append(f"{whale_txns} whale transactions — high activity")
        elif whale_txns > 40:
            score += 5; supporting.append(f"{whale_txns} whale transactions")

        # Active addresses
        if active_addr_chg > 10:
            score += 8; supporting.append(f"Active addresses +{active_addr_chg:.0f}% (growing demand)")
        elif active_addr_chg < -5:
            score -= 6; risks.append(f"Active addresses declining {active_addr_chg:.0f}%")

        # MVRV Z-Score: <0 = undervalued, >3 = overvalued
        if mvrv_z_score < 0:
            score += 12; supporting.append(f"MVRV Z={mvrv_z_score:.2f} (undervalued vs realised cap)")
        elif mvrv_z_score > 3:
            score -= 15; risks.append(f"MVRV Z={mvrv_z_score:.2f} (overvalued — distribution zone)")
        elif mvrv_z_score > 2:
            score -= 5; risks.append(f"MVRV Z={mvrv_z_score:.2f} (elevated valuation)")

        # SOPR (Spent Output Profit Ratio)
        if sopr < 0.995:
            score += 10; supporting.append(f"SOPR={sopr:.3f} (coins spent at loss — capitulation near)")
        elif sopr > 1.03:
            score -= 5; risks.append(f"SOPR={sopr:.3f} (profit taking in progress)")

        if score > 60:
            direction, conf = "BULLISH", min((score-50)/30, 1.0)
        elif score < 40:
            direction, conf = "BEARISH", min((50-score)/30, 1.0)
        else:
            direction, conf = "NEUTRAL", 0.3

        key = (f"Chain: net_flow={net_flow:+.0f}% whales={whale_txns} "
               f"MVRV_Z={mvrv_z_score:.2f} SOPR={sopr:.3f}")
        detail = (
            f"ExchInflow={exchange_inflow_chg:+.0f}% OutFlow={exchange_outflow_chg:+.0f}% "
            f"NetFlow={net_flow:+.0f}% | WhalesTxns={whale_txns} | "
            f"ActiveAddr={active_addr_chg:+.0f}% | MVRV_Z={mvrv_z_score:.2f} | SOPR={sopr:.3f}"
        )

        return AnalystReport(
            analyst_type="on_chain", symbol=symbol, direction=direction,
            confidence=conf, key_insight=key, detail=detail, score=float(score),
            supporting=supporting, risks=risks,
        )
