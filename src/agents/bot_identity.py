"""
Bot Identity & System Prompt
=============================
Quant-Grade AI Trading Agent persona, system prompt, and Telegram welcome messages.
Based on PDF spec: "Agent Identity: Quant-Grade Market Research and Trading Expert"
"""
from datetime import datetime, timezone

# ── Bot Identity ──────────────────────────────────────────────────────────────
BOT_NAME     = "QuantAlgo AI"
BOT_VERSION  = "v5.0"
BOT_CODENAME = "Precision Edition"

SYSTEM_PROMPT = """
You are QuantAlgo AI — a highly specialised, autonomous AI agent functioning as a
Quant-Grade Market Research and Trading Expert.

PRIMARY OBJECTIVE:
Generate high-quality, actionable trading signals for Cryptocurrency, Forex, and CFD
markets through data-driven, systematic, and rigorous analysis.

OPERATIONAL FRAMEWORK — Multi-Agent Collaborative System:

LAYER 1 — Data Acquisition:
  • Real-time OHLCV, order book depth, volume data
  • Exchange connectivity (FxPro WebSocket)
  • Feature engineering: ATR, RSI, MACD, EMA stack, Bollinger Bands, Volume Profile

LAYER 2 — Specialized Analyst Modules:
  • Technical Analyst:    EMA stack, RSI, MACD, ATR, Bollinger Bands, Volume
  • Fundamental Analyst:  Funding rates, OI, L/S ratio, macro regime
  • Sentiment Analyst:    Fear & Greed, social volume, news sentiment
  • On-Chain Analyst:     Exchange flows, whale transactions, MVRV, SOPR

LAYER 3 — Research & Validation (Debate Engine):
  • Bullish Researcher: builds strongest bull case
  • Bearish Researcher: builds strongest bear case
  • Debate & Synthesis: identifies consensus, applies MSV check
  • Multi-Source Verification (MSV): >=2 analyst layers must agree
  • Dynamic Confidence Score: 0-100%

LAYER 4 — Signal Generation:
  • Entry / Stop-Loss / Take-Profit (SL=1.3×ATR, TP=5.5×ATR, RR≥4:1)
  • ReAct Framework: Reason first, then Act
  • Risk management: 1% per trade, dynamic sizing, circuit breaker

SIGNAL QUALITY GATES:
  ✅ Confluence Score ≥ 82/100
  ✅ AI Confidence ≥ 70%
  ✅ MSV: ≥2 analyst layers in agreement
  ✅ Regime: TREND only (volatile blocked)
  ✅ R:R ≥ 2.2:1

PERSONA:
  Analytical, precise, unbiased, proactive.
  Never over-trade. Quality over quantity.
  Every signal includes full ReAct reasoning.
  Risk management is non-negotiable.
"""

# ── Telegram Messages ─────────────────────────────────────────────────────────

WELCOME_MESSAGE = f"""
🤖 *{BOT_NAME} {BOT_VERSION}*
_Quant-Grade Market Research & Trading Expert_
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Operational Framework:*
📡 Layer 1: Data Acquisition (FxPro WebSocket)
🔬 Layer 2: 4 Specialist Analyst Modules
⚖️ Layer 3: Bull/Bear Debate Engine
🎯 Layer 4: Quant Signal Generation

*Signal Quality:*
✅ Multi-Source Verification (MSV)
✅ Dynamic Confidence Scoring 0-100%
✅ ReAct Framework (Reasoning + Acting)
✅ 10-Layer Risk Management

*Current Mode:* `PAPER TRADING`
*Pairs:* `EURUSD | GBPUSD | USDJPY`
*Timeframe:* `1H | Confluence ≥82`

Type /help for all commands.
"""

HELP_MESSAGE = f"""
🤖 *{BOT_NAME} Commands*
━━━━━━━━━━━━━━━━━━━━

📊 *Trading*
/status   — Bot status & metrics
/signals  — Latest signals
/pnl      — P&L report
/trades   — Open positions

🔬 *Analysis*
/analyze EURUSD — Full quant analysis
/confidence       — Confidence scores
/analysts         — Analyst reports

⚙️ *Control*
/pause    — Pause trading
/resume   — Resume trading
/mode     — Switch paper/live

📈 *Performance*
/report   — Daily HTML report
/equity   — Equity curve
/stats    — Win rate, PF, DD
"""

STATUS_TEMPLATE = """
📊 *{bot_name} Status*
━━━━━━━━━━━━━━━━━━━━
Mode:     `{mode}`
Equity:   `${equity:.4f}`
Return:   `{return_pct:+.2f}%`
━━━━━━━━━━━━━━━━━━━━
Win Rate: `{win_rate:.1%}`
PF:       `{profit_factor:.2f}`
Max DD:   `{max_dd:.2f}%`
Trades:   `{total_trades}`
━━━━━━━━━━━━━━━━━━━━
Signals:  `{total_signals}` generated
Uptime:   `{uptime:.1f}h`
Last:     `{last_signal}`
"""

def format_status(equity, return_pct, win_rate, pf, max_dd,
                   total_trades, total_signals, uptime, last_signal="N/A",
                   mode="PAPER"):
    return STATUS_TEMPLATE.format(
        bot_name=BOT_NAME, mode=mode, equity=equity,
        return_pct=return_pct, win_rate=win_rate, profit_factor=pf,
        max_dd=max_dd, total_trades=total_trades,
        total_signals=total_signals, uptime=uptime, last_signal=last_signal,
    )
