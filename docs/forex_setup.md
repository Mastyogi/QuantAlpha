# Forex & Commodities Setup Guide

## Overview

AlphaBot supports three asset classes through a unified `BrokerClient`:

| Asset Class | Instruments | Backend |
|-------------|-------------|---------|
| Crypto | BTC/USDT, ETH/USDT, etc. | CCXT (Binance, Bybit, OKX) |
| Forex | EUR/USD, GBP/USD, USD/JPY, AUD/USD | MT5 (real or simulator) |
| Commodities | XAU/USD (Gold), XAG/USD (Silver), WTI Oil | MT5 (real or simulator) |

---

## Mode 1: Paper/Simulator (Default — No Dependencies)

Works out of the box with zero configuration. The built-in MT5 simulator generates
realistic OHLCV data using a Geometric Brownian Motion price model.

```bash
# .env
ENABLE_FOREX=true
ENABLE_COMMODITIES=true
BROKER_MODE=paper   # Uses simulator
FOREX_PAIRS=EURUSD,GBPUSD,USDJPY
COMMODITY_PAIRS=XAUUSD,XAGUSD,USOIL
```

---

## Mode 2: Real MetaTrader 5 Terminal (Windows)

Requirements:
- Windows 10/11 with MetaTrader 5 terminal installed
- `pip install MetaTrader5`
- A live or demo MT5 account (any broker)

Popular free demo brokers: **Pepperstone**, **ICMarkets**, **XM**, **FBS**

```bash
# .env
BROKER_MODE=mt5
MT5_LOGIN=12345678         # Your MT5 account number
MT5_PASSWORD=your-password
MT5_SERVER=Pepperstone-Demo  # Server from your broker
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe  # Optional
```

The `MT5Client` will automatically fall back to the simulator if:
- `MetaTrader5` package is not installed
- Login credentials are wrong
- Running on Linux/macOS

---

## Position Sizing (Pip-Based)

For forex trades, position size is calculated using the standard pip-risk formula:

```
lots = account_risk_USD / (stop_loss_pips × pip_value_per_lot_USD)
```

Example — EURUSD, $10,000 account, 1% risk, 50-pip stop:
```
account_risk = $10,000 × 1% = $100
lots = $100 / (50 pips × $10/pip) = 0.2 lots
```

Configure via:
```bash
RISK_PER_TRADE_PCT=1.0   # % of equity to risk
MAX_LOT_SIZE=0.5         # Hard lot cap
```

---

## Pip Values (per standard lot)

| Symbol | Pip Size | Pip Value (1 lot) |
|--------|----------|------------------|
| EURUSD | 0.0001  | $10.00 |
| GBPUSD | 0.0001  | $10.00 |
| USDJPY | 0.01    | ~$6.70 |
| XAUUSD | 0.01    | $1.00 |
| USOIL  | 0.01    | $1.00 |

---

## Supported Instruments

### Forex Majors
EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD, EURGBP, EURJPY, GBPJPY

### Metals
XAUUSD (Gold), XAGUSD (Silver), XPTUSD (Platinum)

### Energy
USOIL (WTI Crude), UKOIL (Brent Crude), NGAS (Natural Gas)
