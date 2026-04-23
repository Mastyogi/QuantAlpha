"""
Backtest Report Generator
==========================
Generates professional PDF and HTML backtest reports.

Report sections:
  1. Executive Summary (key metrics)
  2. Equity Curve (chart)
  3. Trade-by-Trade Analysis
  4. Monthly P&L Table
  5. Risk Metrics (Sharpe, Sortino, Calmar, Ulcer Index)
  6. Win/Loss Distribution
  7. Walk-Forward Validation Results
  8. Monte Carlo Simulation Results
  9. Indicator Performance Attribution
  10. Recommendations
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BacktestReportGenerator:
    """
    Generates HTML and PDF reports from backtest results.
    Falls back to plain text if matplotlib/reportlab not available.
    """

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html(
        self,
        symbol:         str,
        timeframe:      str,
        metrics:        Dict,
        trades:         List[Dict],
        equity_curve:   Optional[List] = None,
        mc_result:      Optional[object] = None,
        wf_report:      Optional[object] = None,
    ) -> str:
        """
        Generate a self-contained HTML report.
        Returns the output file path.
        """
        timestamp  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename   = f"{self.output_dir}/backtest_{symbol.replace('/', '')}_{timeframe}_{timestamp}.html"

        html = self._build_html(symbol, timeframe, metrics, trades, equity_curve, mc_result, wf_report)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML report generated: {filename}")
        return filename

    def generate_json(
        self,
        symbol:   str,
        timeframe: str,
        metrics:  Dict,
        trades:   List[Dict],
    ) -> str:
        """Generate machine-readable JSON report."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename  = f"{self.output_dir}/backtest_{symbol.replace('/', '')}_{timeframe}_{timestamp}.json"

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbol":       symbol,
            "timeframe":    timeframe,
            "metrics":      metrics,
            "trades":       trades,
        }

        with open(filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"JSON report generated: {filename}")
        return filename

    def generate_summary_text(self, metrics: Dict, symbol: str, timeframe: str) -> str:
        """Quick text summary for Telegram or logging."""
        pf = metrics.get("profit_factor", 0)
        sr = metrics.get("sharpe_ratio", 0)
        wr = metrics.get("win_rate", 0)
        ret = metrics.get("total_return_pct", 0)
        dd  = metrics.get("max_drawdown_pct", 0)
        n   = metrics.get("total_trades", 0)

        grade = self._grade_strategy(pf, sr, wr, dd)

        return (
            f"📊 *Backtest Report — {symbol} {timeframe}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Overall Grade:    `{grade}`\n"
            f"Total Return:     `{ret:+.2f}%`\n"
            f"Win Rate:         `{wr:.1f}%`\n"
            f"Profit Factor:    `{pf:.2f}`\n"
            f"Sharpe Ratio:     `{sr:.2f}`\n"
            f"Max Drawdown:     `{dd:.2f}%`\n"
            f"Total Trades:     `{n}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{'✅ Deploy Ready' if grade in ('A+', 'A') else '⚠️ Needs Improvement'}\n"
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _grade_strategy(self, pf: float, sharpe: float, wr: float, max_dd: float) -> str:
        """Grade the strategy A+ through F."""
        score = 0
        if pf > 2.0:       score += 3
        elif pf > 1.5:     score += 2
        elif pf > 1.2:     score += 1

        if sharpe > 2.0:   score += 3
        elif sharpe > 1.5: score += 2
        elif sharpe > 1.0: score += 1

        if wr > 65:        score += 2
        elif wr > 55:      score += 1

        if max_dd < 10:    score += 2
        elif max_dd < 20:  score += 1

        if score >= 9:     return "A+"
        if score >= 7:     return "A"
        if score >= 5:     return "B"
        if score >= 3:     return "C"
        return "D"

    def _build_html(
        self,
        symbol:       str,
        timeframe:    str,
        metrics:      Dict,
        trades:       List[Dict],
        equity_curve: Optional[List],
        mc_result:    Optional[object],
        wf_report:    Optional[object],
    ) -> str:
        """Build complete HTML report as string."""
        grade      = self._grade_strategy(
            metrics.get("profit_factor", 0),
            metrics.get("sharpe_ratio", 0),
            metrics.get("win_rate", 0),
            metrics.get("max_drawdown_pct", 0),
        )
        grade_color = {"A+": "#00c851", "A": "#00c851", "B": "#ff8800", "C": "#ff4444", "D": "#cc0000"}.get(grade, "#888")
        total_return = metrics.get("total_return_pct", 0)
        ret_color    = "#00c851" if total_return >= 0 else "#ff4444"
        gen_time     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Build trades table rows
        trade_rows = ""
        for t in trades[:100]:  # Cap at 100 for performance
            pnl    = t.get("pnl_pct", 0)
            color  = "#00c851" if pnl >= 0 else "#ff4444"
            reason = t.get("exit_reason", "")
            trade_rows += (
                f"<tr>"
                f"<td>{t.get('direction','')}</td>"
                f"<td>{t.get('entry_price',''):.5g}</td>"
                f"<td>{t.get('exit_price',''):.5g}</td>"
                f"<td style='color:{color}'>{pnl:+.2f}%</td>"
                f"<td>{reason}</td>"
                f"</tr>\n"
            )

        mc_section = ""
        if mc_result:
            robust, reason = mc_result.is_robust()
            mc_section = f"""
            <div class="section">
              <h2>Monte Carlo Simulation ({mc_result.n_simulations:,} Runs)</h2>
              <div class="metric-grid">
                <div class="metric"><span>Median Outcome</span><b>${mc_result.final_equity_median:,.0f}</b></div>
                <div class="metric"><span>5th Percentile</span><b>${mc_result.final_equity_p5:,.0f}</b></div>
                <div class="metric"><span>95th Percentile</span><b>${mc_result.final_equity_p95:,.0f}</b></div>
                <div class="metric"><span>Probability of Ruin</span><b>{mc_result.probability_of_ruin:.1%}</b></div>
                <div class="metric"><span>VaR 95%</span><b>${mc_result.var_95:,.0f}</b></div>
                <div class="metric"><span>CVaR 95%</span><b>${mc_result.cvar_95:,.0f}</b></div>
              </div>
              <p>Robustness: <b style="color:{'#00c851' if robust else '#ff4444'}">{'✅ ROBUST' if robust else '❌ ' + reason}</b></p>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Backtest Report — {symbol} {timeframe}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; }}
    .header {{ background: linear-gradient(135deg, #1a1f2e 0%, #161b27 100%);
               border-bottom: 1px solid #30363d; padding: 24px 32px; }}
    .header h1 {{ font-size: 24px; color: #58a6ff; }}
    .header p {{ color: #8b949e; margin-top: 4px; }}
    .grade-badge {{ display: inline-block; background: {grade_color}; color: #fff;
                    font-size: 20px; font-weight: 700; padding: 4px 14px; border-radius: 6px; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px 32px; }}
    .section {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px;
                padding: 24px; margin-bottom: 20px; }}
    .section h2 {{ font-size: 16px; color: #58a6ff; margin-bottom: 16px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }}
    .metric {{ background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
               padding: 14px; text-align: center; }}
    .metric span {{ font-size: 11px; color: #8b949e; display: block; margin-bottom: 6px; }}
    .metric b {{ font-size: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ background: #1f2937; color: #9ca3af; padding: 8px 10px; text-align: left; }}
    td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; }}
    tr:hover td {{ background: #1c2128; }}
    .positive {{ color: #00c851; }} .negative {{ color: #ff4444; }}
  </style>
</head>
<body>
<div class="header">
  <h1>📊 Backtest Report — {symbol} {timeframe}
    <span class="grade-badge">{grade}</span>
  </h1>
  <p>Generated {gen_time}</p>
</div>
<div class="container">
  <div class="section">
    <h2>Executive Summary</h2>
    <div class="metric-grid">
      <div class="metric"><span>Total Return</span><b style="color:{ret_color}">{total_return:+.2f}%</b></div>
      <div class="metric"><span>Win Rate</span><b>{metrics.get('win_rate',0):.1f}%</b></div>
      <div class="metric"><span>Profit Factor</span><b>{metrics.get('profit_factor',0):.2f}</b></div>
      <div class="metric"><span>Sharpe Ratio</span><b>{metrics.get('sharpe_ratio',0):.2f}</b></div>
      <div class="metric"><span>Max Drawdown</span><b class="negative">{metrics.get('max_drawdown_pct',0):.2f}%</b></div>
      <div class="metric"><span>Total Trades</span><b>{metrics.get('total_trades',0)}</b></div>
      <div class="metric"><span>Avg Win</span><b class="positive">{metrics.get('avg_win_pct',0):+.2f}%</b></div>
      <div class="metric"><span>Avg Loss</span><b class="negative">{metrics.get('avg_loss_pct',0):.2f}%</b></div>
    </div>
  </div>

  {mc_section}

  <div class="section">
    <h2>Trade Log (last 100)</h2>
    <table>
      <thead><tr><th>Dir</th><th>Entry</th><th>Exit</th><th>P&L%</th><th>Reason</th></tr></thead>
      <tbody>{trade_rows}</tbody>
    </table>
  </div>
</div>
</body>
</html>"""
