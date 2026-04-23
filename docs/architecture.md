# AI Trading Bot — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                   BotEngine (main orchestrator)      │
│  State: INIT → READY → SCANNING → EXECUTING → PAUSED│
└────────────┬──────────────────────────────┬──────────┘
             │                              │
     ┌───────▼────────┐            ┌────────▼────────┐
     │  Data Pipeline  │            │  Risk Manager   │
     │  ─────────────  │            │  ─────────────  │
     │  ExchangeClient │            │  7 Layers:      │
     │  DataFetcher    │            │  • Circuit brk  │
     │  DataValidator  │            │  • AI confidence│
     │  Indicators     │            │  • R:R ratio    │
     └───────┬─────────┘            │  • Max positions│
             │                      │  • Size limit   │
     ┌───────▼─────────┐            │  • Daily loss   │
     │  AI Engine      │            │  • Max drawdown │
     │  ─────────────  │            └────────┬────────┘
     │  FeaturePipeline│                     │
     │  XGBoostModel   │            ┌────────▼────────┐
     │  ModelPredictor │            │  OrderManager   │
     └───────┬─────────┘            │  PaperTrader    │
             │                      │  LiveTrader     │
     ┌───────▼─────────┐            └────────┬────────┘
     │  Strategy Engine│                     │
     │  ─────────────  │            ┌────────▼────────┐
     │  Ensemble       │            │  Telegram Bot   │
     │  TrendFollowing │            │  Notifier       │
     │  MeanReversion  │            │  Handlers       │
     └─────────────────┘            └─────────────────┘
```

## Data Flow

1. **Exchange** → Raw OHLCV data
2. **Validator** → Clean, validated DataFrame
3. **Indicators** → 20+ technical indicators added
4. **FeaturePipeline** → 25 ML features extracted
5. **XGBoostModel** → Direction + Confidence score
6. **EnsembleStrategy** → Consensus signal (BUY/SELL/NEUTRAL)
7. **RiskManager** → 7-layer risk check
8. **OrderManager** → Paper/live order execution
9. **TelegramNotifier** → Real-time alerts

## Risk Management Layers

| Layer | Check | Action |
|-------|-------|--------|
| 1 | Circuit breaker active | Block all trades |
| 2 | AI confidence < 70% | Skip trade |
| 3 | R:R < 1.5 | Skip trade |
| 4 | Open positions >= 5 | Skip trade |
| 5 | Size > 2% equity | Reduce size |
| 6 | Daily loss >= 5% | Halt trading |
| 7 | Drawdown >= 15% | Emergency halt |
