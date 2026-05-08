"""
Portfolio Manager
==================
Multi-position correlation guard and portfolio-level risk management.

Functions:
  - Correlation check: Don't hold too many correlated positions
  - Sector exposure limits: Max % in crypto / forex / commodity
  - Portfolio heat: Total risk-weighted exposure at any time
  - Concentration limits: No single position > X% of portfolio
  - Cross-margin: Estimate margin usage across all open trades

Correlation map (estimated, empirical):
  BTC/ETH: 0.85     → highly correlated (avoid both long at once)
  BTC/SOL: 0.80
  EUR/GBP: 0.65
  XAU/XAG: 0.70
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


# ── Asset correlation matrix (empirical estimates) ────────────────────────────
CORRELATION_MAP: Dict[Tuple[str, str], float] = {
    ("EURUSD", "GBPUSD"):  0.85,
    ("EURUSD", "USDJPY"):  0.40,
    ("EURUSD", "AUDUSD"):  0.78,
    ("GBPUSD", "AUDUSD"):  0.75,
    ("XAUUSD", "XAGUSD"):  0.88,
    ("XAUUSD", "EURUSD"):  0.45,
}


def get_correlation(sym_a: str, sym_b: str) -> float:
    """Get estimated correlation between two symbols."""
    if sym_a == sym_b:
        return 1.0
    key = (sym_a, sym_b) if (sym_a, sym_b) in CORRELATION_MAP else (sym_b, sym_a)
    return CORRELATION_MAP.get(key, 0.0)


@dataclass
class PositionSummary:
    symbol:     str
    direction:  str
    size_usd:   float
    risk_usd:   float     # Size * risk_pct
    risk_pct:   float


@dataclass
class PortfolioRiskResult:
    """Result of portfolio-level risk check."""
    approved:           bool
    reason:             str
    portfolio_heat:     float    # Total risk % of equity
    max_correlation:    float    # Highest correlation with existing positions
    correlated_symbol:  Optional[str] = None
    sector_exposure:    Dict[str, float] = field(default_factory=dict)
    concentration_pct:  float = 0.0


class PortfolioManager:
    """
    Guards portfolio-level risk across all open positions.
    Prevents over-concentration and correlated blowups.
    """

    # ── Limits ───────────────────────────────────────────────────────────────
    MAX_PORTFOLIO_HEAT_PCT   = 8.0    # Max total risk % of equity at any time
    MAX_CORRELATION_ALLOWED  = 0.75   # Block new trade if > this correlated
    MAX_SINGLE_SECTOR_PCT    = 40.0   # Max % of equity in one sector
    MAX_CONCENTRATION_PCT    = 25.0   # Max single position % of equity

    # Asset class mapping
    SECTOR_MAP = {
        "EURUSD": "forex",
        "GBPUSD": "forex",
        "USDJPY": "forex",
        "AUDUSD": "forex",
        "XAUUSD": "commodity",
        "XAGUSD": "commodity",
        "USOIL":  "commodity",
    }

    def __init__(self, equity: float = 10_000.0):
        self.equity = equity
        self._positions: Dict[str, PositionSummary] = {}

    def update_equity(self, equity: float):
        self.equity = equity

    def add_position(
        self,
        trade_id:   str,
        symbol:     str,
        direction:  str,
        size_usd:   float,
        risk_pct:   float,
    ):
        """Register an opened position."""
        self._positions[trade_id] = PositionSummary(
            symbol    = symbol,
            direction = direction,
            size_usd  = size_usd,
            risk_usd  = self.equity * risk_pct / 100,
            risk_pct  = risk_pct,
        )

    def remove_position(self, trade_id: str):
        """Deregister a closed position."""
        self._positions.pop(trade_id, None)

    def check_new_trade(
        self,
        symbol:    str,
        direction: str,
        size_usd:  float,
        risk_pct:  float,
    ) -> PortfolioRiskResult:
        """
        Perform full portfolio risk check before accepting a new trade.
        Returns PortfolioRiskResult with approved=False to block.
        """
        # 1. Portfolio heat check
        current_heat = self._get_portfolio_heat()
        new_heat     = current_heat + risk_pct
        if new_heat > self.MAX_PORTFOLIO_HEAT_PCT:
            return PortfolioRiskResult(
                approved        = False,
                reason          = (
                    f"Portfolio heat {new_heat:.1f}% would exceed max "
                    f"{self.MAX_PORTFOLIO_HEAT_PCT:.1f}%"
                ),
                portfolio_heat  = current_heat,
                max_correlation = 0.0,
            )

        # 2. Correlation check
        max_corr, corr_sym = self._get_max_correlation(symbol, direction)
        if max_corr > self.MAX_CORRELATION_ALLOWED:
            return PortfolioRiskResult(
                approved         = False,
                reason           = (
                    f"High correlation {max_corr:.0%} with open position {corr_sym}"
                ),
                portfolio_heat   = current_heat,
                max_correlation  = max_corr,
                correlated_symbol= corr_sym,
            )

        # 3. Sector concentration
        sector      = self.SECTOR_MAP.get(symbol, "other")
        sector_exp  = self._get_sector_exposure()
        sector_pct  = (sector_exp.get(sector, 0) + size_usd) / self.equity * 100
        if sector_pct > self.MAX_SINGLE_SECTOR_PCT:
            return PortfolioRiskResult(
                approved        = False,
                reason          = (
                    f"Sector {sector} exposure {sector_pct:.1f}% would exceed "
                    f"max {self.MAX_SINGLE_SECTOR_PCT:.1f}%"
                ),
                portfolio_heat  = current_heat,
                max_correlation = max_corr,
                sector_exposure = sector_exp,
            )

        # 4. Single position concentration
        concentration = size_usd / self.equity * 100
        if concentration > self.MAX_CONCENTRATION_PCT:
            return PortfolioRiskResult(
                approved          = False,
                reason            = (
                    f"Position size {concentration:.1f}% of equity exceeds "
                    f"max {self.MAX_CONCENTRATION_PCT:.1f}%"
                ),
                portfolio_heat    = current_heat,
                max_correlation   = max_corr,
                concentration_pct = concentration,
            )

        return PortfolioRiskResult(
            approved         = True,
            reason           = "Portfolio risk checks passed",
            portfolio_heat   = new_heat,
            max_correlation  = max_corr,
            correlated_symbol= corr_sym,
            sector_exposure  = sector_exp,
            concentration_pct= concentration,
        )

    def get_summary(self) -> Dict:
        """Summary of current portfolio state."""
        heat   = self._get_portfolio_heat()
        sector = self._get_sector_exposure()
        return {
            "open_positions":  len(self._positions),
            "portfolio_heat":  heat,
            "sector_exposure": sector,
            "total_usd_at_risk": self.equity * heat / 100,
            "positions": [
                {
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "size_usd": p.size_usd,
                    "risk_pct": p.risk_pct,
                }
                for p in self._positions.values()
            ],
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_portfolio_heat(self) -> float:
        """Total risk % of equity across all open positions."""
        return sum(p.risk_pct for p in self._positions.values())

    def _get_max_correlation(
        self, symbol: str, direction: str
    ) -> Tuple[float, Optional[str]]:
        """Find highest correlation between proposed trade and open positions."""
        max_corr = 0.0
        corr_sym = None
        for pos in self._positions.values():
            # Only flag if SAME direction (correlated longs are risky together)
            if pos.direction != direction:
                continue
            corr = get_correlation(symbol, pos.symbol)
            if corr > max_corr:
                max_corr = corr
                corr_sym = pos.symbol
        return max_corr, corr_sym

    def _get_sector_exposure(self) -> Dict[str, float]:
        """USD exposure per sector from open positions."""
        exposure: Dict[str, float] = {}
        for pos in self._positions.values():
            sec = self.SECTOR_MAP.get(pos.symbol, "other")
            exposure[sec] = exposure.get(sec, 0.0) + pos.size_usd
        return exposure
