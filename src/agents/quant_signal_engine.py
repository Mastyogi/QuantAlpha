"""
Layer 4: Quant-Grade Signal Generation Engine
==============================================
PDF Spec: Signal Generation + Risk Management + ReAct Output
Orchestrates all 4 analyst modules → Debate Engine → Final Signal
with Dynamic Confidence Score and Structured Telegram Output.

Bot Identity: Quant-Grade Market Research and Trading Expert
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.agents.analyst_modules import (
    TechnicalAnalystModule, FundamentalAnalystModule,
    SentimentAnalystModule, OnChainAnalystModule, AnalystReport,
)
from src.agents.debate_engine import DebateEngine, DebateVerdict
from src.utils.logger import get_logger
logger = get_logger(__name__)


# ── Bot Identity (PDF: Persona) ───────────────────────────────────────────────
BOT_IDENTITY = {
    "name":    "QuantAlgo AI",
    "version": "v5.0 | Quant-Grade",
    "persona": (
        "Highly specialised, autonomous AI agent functioning as a "
        "Quant-Grade Market Research and Trading Expert. "
        "Data-driven, systematic, and rigorous. "
        "Decisions based on comprehensive multi-source analysis."
    ),
    "framework": "Multi-Agent | ReAct | MSV | Dynamic Confidence",
    "markets":   ["Cryptocurrency", "Forex", "CFD"],
}


@dataclass
class QuantSignal:
    """Fully structured trading signal (PDF output format)."""
    # Identity
    symbol:          str
    market:          str
    direction:       str        # BUY | SELL
    # Scores
    confidence_score: float     # 0-100 (dynamic)
    signal_grade:    str        # A+/A/B/C/D
    msv_satisfied:   bool
    # ReAct Framework
    observation:     str
    fundamental:     str
    sentiment:       str
    technical:       str
    on_chain:        str
    research_validation: str
    conclusion:      str
    # Actionable Parameters
    entry:           float
    sl:              float
    tp:              float
    tp1:             float      # partial TP (50% of full move)
    rr_ratio:        float
    lot_size:        str
    validity:        str
    atr:             float
    # Risk
    risk_considerations: str
    risk_factors:    List[str]  = field(default_factory=list)
    # Meta
    timestamp:       str = ""
    analyst_consensus: str = ""

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.tp1 = self.entry + (self.tp - self.entry) * 0.5

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence_score >= 80

    def to_telegram_quant(self) -> str:
        """Full Quant-Grade Telegram message (PDF output format)."""
        emoji = "📈" if self.direction == "BUY" else "📉"
        fire  = "🔥" if self.confidence_score >= 85 else "⚡"
        lines = [
            f"{fire} *{BOT_IDENTITY['name']} — {self.symbol}*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📊 *Market:*       `{self.market}`",
            f"{emoji} *Direction:*   `{self.direction}`",
            f"🧠 *Confidence:*  `{self.confidence_score:.0f}%` _{self.signal_grade}_",
            f"✅ *MSV:*          `{'SATISFIED' if self.msv_satisfied else 'PARTIAL'}`",
            f"",
            f"*📋 ReAct Framework:*",
            f"• *Obs:* {self.observation[:120]}",
            f"• *Tech:* {self.technical[:120]}",
            f"• *Fund:* {self.fundamental[:100]}",
            f"• *Sent:* {self.sentiment[:100]}",
        ]
        if self.on_chain and self.on_chain != "N/A":
            lines.append(f"• *Chain:* {self.on_chain[:100]}")
        lines += [
            f"• *Debate:* {self.research_validation[:120]}",
            f"• *Conclusion:* {self.conclusion[:140]}",
            f"",
            f"*🎯 Actionable Parameters:*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"💰 *Entry:*  `{self.entry:.6g}`",
            f"🛑 *SL:*     `{self.sl:.6g}`",
            f"🎯 *TP1:*    `{self.tp1:.6g}`",
            f"🎯 *TP2:*    `{self.tp:.6g}`",
            f"📊 *R:R:*    `{self.rr_ratio:.2f}:1`",
            f"📦 *Size:*   `{self.lot_size}`",
            f"⏰ *Valid:*  `{self.validity}`",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"⚠️ *Risk:* {self.risk_considerations[:120]}",
            f"🕐 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`",
        ]
        return "\n".join(lines)


class QuantSignalEngine:
    """
    Master Signal Orchestrator — PDF Layer 4.
    Runs all analysts → Debate → generates QuantSignal.

    Usage:
        engine = QuantSignalEngine()
        signal = engine.generate(df, symbol="BTC/USDT", equity=100.0)
        if signal and signal.is_high_confidence:
            await notifier.send_quant_signal(signal.__dict__)
    """

    def __init__(self, confluence_threshold: float = 72.0):
        self.tech_analyst  = TechnicalAnalystModule()
        self.fund_analyst  = FundamentalAnalystModule()
        self.sent_analyst  = SentimentAnalystModule()
        self.chain_analyst = OnChainAnalystModule()
        self.debate_engine = DebateEngine()
        self.confluence_threshold = confluence_threshold
        self._signal_count = 0
        self._signal_log: List[dict] = []

    def generate(
        self,
        df: pd.DataFrame,
        symbol: str,
        market: str = "Cryptocurrency",
        equity: float = 10.0,
        market_context: Optional[dict] = None,
        sentiment_data: Optional[dict] = None,
        chain_data:     Optional[dict] = None,
        timeframe:      str = "1h",
    ) -> Optional[QuantSignal]:
        """
        Full signal generation pipeline:
        1. Run all 4 analyst modules
        2. Run Bullish/Bearish debate
        3. Apply MSV + Confidence scoring
        4. Build QuantSignal if threshold met
        """
        try:
            return self._generate_impl(
                df, symbol, market, equity,
                market_context, sentiment_data, chain_data, timeframe,
            )
        except Exception as e:
            logger.error(f"QuantSignalEngine.generate {symbol}: {e}")
            return None

    def _generate_impl(self, df, symbol, market, equity,
                        mctx, sdata, cdata, tf) -> Optional[QuantSignal]:
        if len(df) < 65:
            return None

        # ── Layer 2: Run all analysts ──────────────────────────────────────
        reports: List[AnalystReport] = [
            self.tech_analyst.analyze(df, symbol),
            self.fund_analyst.analyze(df, symbol, mctx),
            self.sent_analyst.analyze(df, symbol, sdata),
            self.chain_analyst.analyze(df, symbol, cdata),
        ]

        # ── Layer 3: Debate ────────────────────────────────────────────────
        verdict: DebateVerdict = self.debate_engine.debate(reports, symbol)

        if not verdict.is_actionable:
            return None

        if verdict.confidence_score < self.confluence_threshold:
            return None

        # ── Layer 4: Build actionable parameters ───────────────────────────
        tech_r = next((r for r in reports if r.analyst_type == "technical"), None)
        curr   = float(df["close"].iloc[-1])

        # Extract ATR from tech report detail
        atr = curr * 0.015  # default 1.5% of price
        if tech_r and "ATR=" in tech_r.detail:
            try:
                atr_part = [x for x in tech_r.detail.split("|") if "ATR=" in x][0]
                atr_val_str = atr_part.split("ATR=")[1].split("(")[0].strip()
                atr = float(atr_val_str)
            except Exception:
                pass

        # Entry / SL / TP
        sl_mult = 1.3; tp_mult = sl_mult * 4.2
        sl = curr - atr * sl_mult if verdict.direction == "BUY" else curr + atr * sl_mult
        tp = curr + atr * tp_mult if verdict.direction == "BUY" else curr - atr * tp_mult
        rr = abs(tp - curr) / max(abs(curr - sl), 1e-10)

        # Lot size suggestion based on equity and 1% risk
        risk_usd   = equity * 0.01
        stop_dist  = abs(curr - sl) / curr
        lot_usd    = risk_usd / max(stop_dist, 0.005)
        lot_size   = f"${lot_usd:.2f} USD (1% risk)"

        # Assemble per-analyst insights
        def _insight(analyst_type, default="N/A"):
            r = next((r for r in reports if r.analyst_type == analyst_type), None)
            return r.key_insight if r else default

        # Build risk considerations
        all_risks = [r for rpt in reports for r in rpt.risks[:1]]
        risk_text = "; ".join(all_risks[:3]) if all_risks else "Monitor price action closely"

        # Research & Validation summary
        rv_summary = (
            f"Debate: {verdict.analyst_consensus}. "
            f"Bull={verdict.bull_strength:.0f}% vs Bear={verdict.bear_strength:.0f}%. "
            f"{verdict.supporting_count}/{len(reports)} analysts aligned."
        )

        self._signal_count += 1
        sig = QuantSignal(
            symbol=symbol,
            market=market,
            direction=verdict.direction,
            confidence_score=verdict.confidence_score,
            signal_grade=verdict.grade,
            msv_satisfied=verdict.msv_satisfied,
            observation=verdict.react_observation,
            fundamental=_insight("fundamental"),
            sentiment=_insight("sentiment"),
            technical=_insight("technical"),
            on_chain=_insight("on_chain"),
            research_validation=rv_summary,
            conclusion=verdict.react_conclusion,
            entry=curr,
            sl=sl,
            tp=tp,
            tp1=curr + (tp - curr) * 0.5,
            rr_ratio=rr,
            lot_size=lot_size,
            validity="24h or until next major event",
            atr=atr,
            risk_considerations=risk_text,
            risk_factors=all_risks[:4],
            analyst_consensus=verdict.analyst_consensus,
        )

        self._signal_log.append({
            "ts": sig.timestamp, "symbol": symbol,
            "direction": sig.direction, "confidence": sig.confidence_score,
            "grade": sig.signal_grade,
        })

        logger.info(
            f"QuantSignal #{self._signal_count}: {symbol} {sig.direction} "
            f"conf={sig.confidence_score:.0f}% grade={sig.signal_grade} "
            f"MSV={'OK' if sig.msv_satisfied else 'PARTIAL'}"
        )
        return sig

    def get_stats(self) -> dict:
        return {
            "total_signals": self._signal_count,
            "recent": self._signal_log[-5:],
            "bot_identity": BOT_IDENTITY["name"],
        }
