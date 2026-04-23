"""
Layer 3: Research & Validation Module — Bullish/Bearish Debate Engine
=======================================================================
PDF Spec Implementation:
  - BullishResearcher: builds strongest bull case from analyst reports
  - BearishResearcher: builds strongest bear case
  - DebateEngine: structured debate → synthesised verdict + confidence score
  - Multi-Source Verification (MSV): >=2 analyst layers required
  - Dynamic Confidence Scoring: 0-100%
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
from src.agents.analyst_modules import AnalystReport
from src.utils.logger import get_logger
logger = get_logger(__name__)


@dataclass
class ResearchCase:
    """Bull or bear case built by a Researcher module."""
    side:           str           # "BULLISH" | "BEARISH"
    symbol:         str
    strength:       float         # 0-100
    core_argument:  str
    evidence:       List[str]     = field(default_factory=list)
    counter_risks:  List[str]     = field(default_factory=list)
    analyst_count:  int           = 0
    weighted_score: float         = 0.0


@dataclass
class DebateVerdict:
    """Final synthesised output from the Debate Engine."""
    symbol:             str
    direction:          str           # "BUY" | "SELL" | "NO_SIGNAL"
    confidence_score:   float         # 0-100 (PDF: dynamic confidence)
    msv_satisfied:      bool          # Multi-Source Verification passed
    analyst_consensus:  str           # "STRONG_BULL" | "BULL" | "NEUTRAL" | "BEAR" | "STRONG_BEAR"
    react_observation:  str           # What we see in market
    react_analysis:     Dict[str,str] # Per-analyst summary
    react_conclusion:   str           # Final reasoning
    bull_strength:      float
    bear_strength:      float
    supporting_count:   int
    contradicting_count:int
    risk_factors:       List[str]     = field(default_factory=list)
    timestamp:          str           = ""

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def is_actionable(self) -> bool:
        return self.msv_satisfied and self.direction != "NO_SIGNAL"

    @property
    def grade(self) -> str:
        if   self.confidence_score >= 88: return "A+"
        elif self.confidence_score >= 80: return "A"
        elif self.confidence_score >= 72: return "B"
        elif self.confidence_score >= 62: return "C"
        return "D"

    def to_react_string(self) -> str:
        """Format for Telegram (PDF output spec)."""
        lines = [
            f"🔍 *Obs:* {self.react_observation[:120]}",
            f"📊 *Tech:*  {self.react_analysis.get('technical','N/A')[:100]}",
            f"🏦 *Fund:*  {self.react_analysis.get('fundamental','N/A')[:100]}",
            f"💬 *Sent:*  {self.react_analysis.get('sentiment','N/A')[:100]}",
        ]
        if "on_chain" in self.react_analysis:
            lines.append(f"⛓ *Chain:* {self.react_analysis['on_chain'][:100]}")
        lines.append(f"📋 *Conclusion:* {self.react_conclusion[:150]}")
        return "\n".join(lines)


class BullishResearcherModule:
    """Builds strongest possible bull case from all analyst reports."""

    def build_case(self, reports: List[AnalystReport], symbol: str) -> ResearchCase:
        bull_reports = [r for r in reports if r.direction == "BULLISH"]
        neutral      = [r for r in reports if r.direction == "NEUTRAL"]

        evidence     = []
        counter_risk = []

        # Aggregate supporting evidence
        for r in bull_reports:
            evidence.extend(r.supporting[:2])
        for r in neutral:
            evidence.extend(r.supporting[:1])

        # Counter the bear risks
        bear_reports = [r for r in reports if r.direction == "BEARISH"]
        for r in bear_reports:
            counter_risk.extend(r.risks[:1])

        if not bull_reports:
            return ResearchCase("BULLISH", symbol, 10.0,
                                "No bullish signals found", evidence, counter_risk, 0)

        # Weighted strength
        weights = {"technical": 0.35, "fundamental": 0.25, "sentiment": 0.20, "on_chain": 0.20}
        strength = 0.0
        for r in bull_reports:
            w = weights.get(r.analyst_type, 0.15)
            strength += r.confidence * w * 100
        strength = min(strength * (len(bull_reports) / max(len(reports), 1) + 0.3), 100)

        core = (f"Bull case ({len(bull_reports)}/{len(reports)} analysts agree): "
                f"{'; '.join(evidence[:2]) if evidence else 'EMA/momentum alignment'}")

        return ResearchCase("BULLISH", symbol, strength, core,
                            evidence[:4], counter_risk[:2], len(bull_reports), strength)


class BearishResearcherModule:
    """Builds strongest possible bear case from all analyst reports."""

    def build_case(self, reports: List[AnalystReport], symbol: str) -> ResearchCase:
        bear_reports = [r for r in reports if r.direction == "BEARISH"]
        neutral      = [r for r in reports if r.direction == "NEUTRAL"]

        evidence     = []
        counter_risk = []

        for r in bear_reports:
            evidence.extend(r.risks[:2])
        for r in neutral:
            evidence.extend(r.risks[:1])

        bull_reports = [r for r in reports if r.direction == "BULLISH"]
        for r in bull_reports:
            counter_risk.extend(r.supporting[:1])

        if not bear_reports:
            return ResearchCase("BEARISH", symbol, 10.0,
                                "No bearish signals found", evidence, counter_risk, 0)

        weights = {"technical": 0.35, "fundamental": 0.25, "sentiment": 0.20, "on_chain": 0.20}
        strength = 0.0
        for r in bear_reports:
            w = weights.get(r.analyst_type, 0.15)
            strength += r.confidence * w * 100
        strength = min(strength * (len(bear_reports) / max(len(reports), 1) + 0.3), 100)

        core = (f"Bear case ({len(bear_reports)}/{len(reports)} analysts agree): "
                f"{'; '.join(evidence[:2]) if evidence else 'EMA/momentum weakness'}")

        return ResearchCase("BEARISH", symbol, strength, core,
                            evidence[:4], counter_risk[:2], len(bear_reports), strength)


class DebateEngine:
    """
    Facilitates structured Bullish vs Bearish debate.
    Implements PDF Layer 3: Research & Validation Module.
    Applies Multi-Source Verification (MSV) — requires >=2 aligned analyst layers.
    Produces Dynamic Confidence Score (0-100).
    """

    MIN_CONFIDENCE = 62.0          # Below this: NO_SIGNAL
    MSV_MIN_LAYERS = 2             # Multi-Source Verification minimum

    def __init__(self):
        self.bull_researcher = BullishResearcherModule()
        self.bear_researcher = BearishResearcherModule()

    def debate(self, reports: List[AnalystReport], symbol: str) -> DebateVerdict:
        """Run full debate and return DebateVerdict."""
        if not reports:
            return self._no_signal(symbol, "No analyst reports", [], [])

        # Build both cases
        bull_case = self.bull_researcher.build_case(reports, symbol)
        bear_case = self.bear_researcher.build_case(reports, symbol)

        # Count consensus
        bull_count = sum(1 for r in reports if r.direction == "BULLISH")
        bear_count = sum(1 for r in reports if r.direction == "BEARISH")
        neut_count = sum(1 for r in reports if r.direction == "NEUTRAL")
        total      = len(reports)

        # Determine consensus
        if   bull_count >= 3: consensus = "STRONG_BULL"
        elif bull_count == 2: consensus = "BULL"
        elif bear_count >= 3: consensus = "STRONG_BEAR"
        elif bear_count == 2: consensus = "BEAR"
        else:                 consensus = "NEUTRAL"

        # Multi-Source Verification
        msv_bull = bull_count >= self.MSV_MIN_LAYERS
        msv_bear = bear_count >= self.MSV_MIN_LAYERS

        # Base confidence from strength differential
        if bull_case.strength > bear_case.strength:
            direction  = "BUY"
            base_conf  = bull_case.strength
            msv_ok     = msv_bull
        elif bear_case.strength > bull_case.strength:
            direction  = "SELL"
            base_conf  = bear_case.strength
            msv_ok     = msv_bear
        else:
            return self._no_signal(symbol, "Equal bull/bear strength",
                                    [r for r in reports if r.is_bullish],
                                    [r for r in reports if r.is_bearish])

        # MSV penalty
        if not msv_ok:
            base_conf *= 0.70   # penalise single-layer signals

        # Volatility penalty (if atr > 3% of price it's risky)
        tech_report = next((r for r in reports if r.analyst_type == "technical"), None)
        if tech_report and "ATR" in tech_report.detail:
            try:
                atr_str = [x for x in tech_report.detail.split("|") if "atr" in x.lower()]
                if atr_str:
                    atr_pct_str = [x for x in atr_str[0].split("(") if "%" in x]
                    if atr_pct_str:
                        atr_pct = float(atr_pct_str[0].replace("%","").strip())
                        if atr_pct > 3.0:
                            base_conf *= 0.85
            except Exception:
                pass

        # Consensus boost
        if consensus in ("STRONG_BULL", "STRONG_BEAR"):
            base_conf = min(base_conf * 1.10, 97)
        elif consensus in ("BULL", "BEAR"):
            base_conf = min(base_conf * 1.05, 95)

        final_conf = float(np.clip(base_conf, 0, 97))

        # Check threshold
        if final_conf < self.MIN_CONFIDENCE:
            return self._no_signal(symbol,
                                    f"Confidence {final_conf:.0f}% < {self.MIN_CONFIDENCE}%",
                                    [r for r in reports if r.is_bullish],
                                    [r for r in reports if r.is_bearish])

        # Build ReAct analysis dict
        react_analysis = {}
        for r in reports:
            react_analysis[r.analyst_type] = r.key_insight

        active_case = bull_case if direction == "BUY" else bear_case
        react_obs   = (
            f"{symbol} showing {'bullish' if direction=='BUY' else 'bearish'} structure. "
            f"{bull_count} bull / {bear_count} bear / {neut_count} neutral analysts. "
            f"MSV: {'SATISFIED' if msv_ok else 'PARTIAL'}."
        )
        react_concl = (
            f"{direction} signal with {final_conf:.0f}% confidence. "
            f"{active_case.core_argument[:120]}. "
            f"Grade: {self._grade(final_conf)}."
        )

        # All risks
        all_risks = []
        for r in reports:
            all_risks.extend(r.risks[:1])

        return DebateVerdict(
            symbol=symbol,
            direction=direction,
            confidence_score=final_conf,
            msv_satisfied=msv_ok,
            analyst_consensus=consensus,
            react_observation=react_obs,
            react_analysis=react_analysis,
            react_conclusion=react_concl,
            bull_strength=bull_case.strength,
            bear_strength=bear_case.strength,
            supporting_count=bull_count if direction == "BUY" else bear_count,
            contradicting_count=bear_count if direction == "BUY" else bull_count,
            risk_factors=all_risks[:4],
        )

    def _no_signal(self, symbol, reason, bull_reports, bear_reports):
        return DebateVerdict(
            symbol=symbol, direction="NO_SIGNAL", confidence_score=0.0,
            msv_satisfied=False, analyst_consensus="NEUTRAL",
            react_observation=f"No actionable signal: {reason}",
            react_analysis={}, react_conclusion=reason,
            bull_strength=0.0, bear_strength=0.0,
            supporting_count=0, contradicting_count=0,
        )

    def _grade(self, conf):
        if   conf >= 88: return "A+"
        elif conf >= 80: return "A"
        elif conf >= 72: return "B"
        elif conf >= 62: return "C"
        return "D"
