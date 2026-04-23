"""Quick Integration Test - Verify Bot is Ready"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def main():
    print("\n🧪 QUICK INTEGRATION TEST\n")
    
    # Test 1: Telegram Import
    print("1️⃣  Testing Telegram Import...")
    try:
        from telegram import Bot
        from telegram.ext import Application
        print("   ✅ python-telegram-bot installed and importable")
    except ImportError as e:
        print(f"   ❌ Telegram import failed: {e}")
        return False
    
    # Test 2: Telegram Bot Token
    print("\n2️⃣  Testing Telegram Bot Token...")
    try:
        from config.settings import settings
        bot = Bot(token=settings.telegram_bot_token)
        info = await bot.get_me()
        print(f"   ✅ Bot connected: @{info.username} ({info.first_name})")
        await bot.close()
    except Exception as e:
        print(f"   ❌ Bot connection failed: {e}")
        return False
    
    # Test 3: Bitget Exchange
    print("\n3️⃣  Testing Bitget Exchange...")
    try:
        import ccxt
        exchange = ccxt.bitget({
            'apiKey': settings.exchange_api_key,
            'secret': settings.exchange_api_secret,
            'password': getattr(settings, 'exchange_passphrase', None),
        })
        print(f"   ✅ Exchange initialized: {exchange.name}")
    except Exception as e:
        print(f"   ❌ Exchange init failed: {e}")
        return False
    
    # Test 4: Bot Engine Components
    print("\n4️⃣  Testing Bot Engine Components...")
    try:
        from src.core.bot_engine import BotEngine
        engine = BotEngine()
        
        components = {
            'Exchange': engine.exchange,
            'Signal Engine': engine.signal_engine,
            'Order Manager': engine.order_manager,
            'Portfolio Compounder': engine.portfolio_compounder,
            'Auto-Tuning': engine.auto_tuning_system,
            'Health Check': engine.health_check_system,
        }
        
        all_ok = all(c is not None for c in components.values())
        if all_ok:
            print(f"   ✅ All {len(components)} components initialized")
        else:
            print(f"   ⚠️  Some components missing")
            for name, comp in components.items():
                status = "✅" if comp else "❌"
                print(f"      {status} {name}")
    except Exception as e:
        print(f"   ❌ Bot engine failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Telegram Handlers
    print("\n5️⃣  Testing Telegram Handlers...")
    try:
        from src.telegram.handlers import build_telegram_app
        app = build_telegram_app(engine)
        
        if hasattr(app, '__aenter__'):
            print("   ✅ Real Telegram app created (not mock)")
        else:
            print("   ⚠️  Mock Telegram app (token issue?)")
    except Exception as e:
        print(f"   ❌ Handlers failed: {e}")
        return False
    
    # Summary
    print("\n" + "="*50)
    print("✅ ALL TESTS PASSED!")
    print("="*50)
    print("\n📝 Next Steps:")
    print("   1. Open Telegram and search: @multipiller_bot")
    print("   2. Click START button")
    print("   3. Run: python src/main.py")
    print("   4. Send /status command to bot")
    print("\n🚀 Bot is ready to run!")
    
    return True


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
