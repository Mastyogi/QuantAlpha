#!/usr/bin/env python3
"""
QuantAlpha Pipeline Test Script
Tests: Config Loading → Data Fetch → Signal Generation → Trade Execution
"""
import sys
import os
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("  QuantAlpha Pipeline Test")
print("=" * 60)

# Test 1: Load .env
print("\n[1/5] Testing .env loading...")
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
    print(f"  ✅ .env loaded from: {env_path}")
except Exception as e:
    print(f"  ❌ .env load failed: {e}")

# Test 2: Load settings
print("\n[2/5] Testing config/settings...")
try:
    from config.settings import settings
    print(f"  ✅ Settings loaded:")
    print(f"     - TRADING_MODE: {settings.trading_mode}")
    print(f"     - TRADING_PAIRS: {settings.trading_pairs}")
    print(f"     - CONFLUENCE_THRESHOLD: {settings.confluence_threshold}")
    print(f"     - TELEGRAM_BOT_TOKEN: {settings.telegram_bot_token[:20] if settings.telegram_bot_token else 'NOT SET'}...")
except Exception as e:
    print(f"  ❌ Settings load failed: {e}")

# Test 3: Initialize broker client
print("\n[3/5] Testing BrokerClient (Data Fetch)...")
try:
    from src.data.forex.broker_client import BrokerClient
    import asyncio
    
    async def test_broker():
        broker = BrokerClient()
        await broker.initialize()
        # Try to fetch data for EURUSD (forex) or BTCUSDT (crypto)
        try:
            df = await broker.fetch_ohlcv("EURUSD", "1h", 50)
            print(f"  ✅ EURUSD data: {len(df)} candles fetched")
        except Exception as e:
            print(f"  ⚠️  EURUSD fetch failed: {e}")
        
        try:
            df = await broker.fetch_ohlcv("BTCUSDT", "1h", 50)
            print(f"  ✅ BTCUSDT data: {len(df)} candles fetched")
        except Exception as e:
            print(f"  ⚠️  BTCUSDT fetch failed: {e}")
        
        return broker
    
    broker = asyncio.run(test_broker())
except Exception as e:
    print(f"  ❌ BrokerClient failed: {e}")

# Test 4: Signal Engine
print("\n[4/5] Testing Signal Engine...")
try:
    from src.signals.signal_engine import FineTunedSignalEngine
    
    engine = FineTunedSignalEngine(
        model_dir="models",
        confluence_threshold=float(getattr(settings, 'confluence_threshold', 65)),
        max_risk_pct=2.0,
        account_equity=10000.0,
    )
    print(f"  ✅ Signal Engine initialized")
    print(f"     - confluence_threshold: {engine.confluence_threshold}")
except Exception as e:
    print(f"  ❌ Signal Engine failed: {e}")

# Test 5: Telegram Config
print("\n[5/5] Testing Telegram Configuration...")
try:
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_chat_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '')
    
    if telegram_token and telegram_token != 'YOUR_BOT_TOKEN_HERE':
        print(f"  ✅ Telegram configured")
        print(f"     - Token: {telegram_token[:15]}...")
        print(f"     - Chat ID: {telegram_chat_id}")
    else:
        print(f"  ❌ Telegram NOT configured")
        print(f"     - Add TELEGRAM_BOT_TOKEN in .env")
except Exception as e:
    print(f"  ❌ Telegram check failed: {e}")

print("\n" + "=" * 60)
print("  Test Complete")
print("=" * 60)
print("""
Next Steps:
1. Edit .env and add your TELEGRAM_BOT_TOKEN
2. Rebuild container: docker-compose -f docker-compose.prod.yml up -d --build
3. Check logs: docker logs -f quantalpha-trading-bot
4. Send /pnl command on Telegram
""")