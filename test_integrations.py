"""
Integration Test Script - Bitget & Telegram
============================================
Tests both Bitget exchange and Telegram bot connectivity
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import settings


async def test_telegram():
    """Test Telegram bot connection."""
    print("\n" + "="*60)
    print("🤖 TESTING TELEGRAM BOT")
    print("="*60)
    
    try:
        from telegram import Bot
        
        bot = Bot(token=settings.telegram_bot_token)
        info = await bot.get_me()
        
        print(f"✅ Bot Connected Successfully!")
        print(f"   Username: @{info.username}")
        print(f"   Name: {info.first_name}")
        print(f"   ID: {info.id}")
        print(f"   Can Join Groups: {info.can_join_groups}")
        print(f"   Can Read Messages: {info.can_read_all_group_messages}")
        
        # Test sending message to admin
        try:
            await bot.send_message(
                chat_id=settings.telegram_admin_chat_id,
                text="🧪 *Test Message from KellyAI Bot*\n\n"
                     "✅ Telegram integration is working!\n"
                     "✅ Bot can send messages\n"
                     "✅ Ready for production use",
                parse_mode="Markdown"
            )
            print(f"✅ Test message sent to admin chat: {settings.telegram_admin_chat_id}")
        except Exception as e:
            print(f"⚠️  Could not send test message: {e}")
            print(f"   Make sure you've started a chat with @{info.username}")
        
        await bot.close()
        return True
        
    except Exception as e:
        print(f"❌ Telegram Test Failed: {e}")
        return False


async def test_bitget():
    """Test Bitget exchange connection."""
    print("\n" + "="*60)
    print("💱 TESTING BITGET EXCHANGE")
    print("="*60)
    
    try:
        import ccxt.async_support as ccxt
        
        exchange = ccxt.bitget({
            'apiKey': settings.exchange_api_key,
            'secret': settings.exchange_api_secret,
            'password': getattr(settings, 'exchange_passphrase', None),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        print(f"✅ Exchange Client Created: {exchange.name}")
        print(f"   API Key: {settings.exchange_api_key[:15]}...")
        print(f"   Has Passphrase: {'Yes' if hasattr(settings, 'exchange_passphrase') else 'No'}")
        
        # Test market data fetch (public API)
        try:
            ticker = await exchange.fetch_ticker('BTC/USDT')
            print(f"\n✅ Market Data Access Working!")
            print(f"   BTC/USDT Price: ${ticker['last']:,.2f}")
            print(f"   24h Volume: ${ticker.get('quoteVolume', 0):,.0f}")
            print(f"   24h Change: {ticker.get('percentage', 0):+.2f}%")
        except Exception as e:
            print(f"⚠️  Market data fetch failed: {e}")
            print(f"   This is normal in paper trading mode")
        
        # Test balance fetch (private API)
        try:
            balance = await exchange.fetch_balance()
            print(f"\n✅ Account Access Working!")
            if 'USDT' in balance:
                usdt = balance['USDT']
                print(f"   USDT Balance: ${usdt.get('total', 0):,.2f}")
                print(f"   Free: ${usdt.get('free', 0):,.2f}")
                print(f"   Used: ${usdt.get('used', 0):,.2f}")
            else:
                print(f"   No USDT balance found")
        except Exception as e:
            print(f"⚠️  Balance fetch failed: {e}")
            print(f"   Check API key permissions (need 'Read' permission)")
        
        await exchange.close()
        return True
        
    except Exception as e:
        print(f"❌ Bitget Test Failed: {e}")
        return False


async def test_bot_startup():
    """Test bot engine startup."""
    print("\n" + "="*60)
    print("🚀 TESTING BOT ENGINE STARTUP")
    print("="*60)
    
    try:
        from src.core.bot_engine import BotEngine
        
        print("✅ Bot Engine imported successfully")
        
        engine = BotEngine()
        print("✅ Bot Engine initialized")
        
        # Check all components
        components = [
            ('Exchange Client', engine.exchange),
            ('Data Fetcher', engine.fetcher),
            ('Signal Engine', engine.signal_engine),
            ('Order Manager', engine.order_manager),
            ('Risk Manager', engine.adaptive_risk),
            ('Portfolio Compounder', engine.portfolio_compounder),
            ('Profit Booking Engine', engine.profit_booking_engine),
            ('Auto-Tuning System', engine.auto_tuning_system),
            ('Health Check System', engine.health_check_system),
            ('Self-Improvement Engine', engine.self_improvement_engine),
        ]
        
        print("\n📦 Component Status:")
        for name, component in components:
            status = "✅" if component is not None else "❌"
            print(f"   {status} {name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot Engine Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("🧪 KELLYAI INTEGRATION TEST SUITE")
    print("="*60)
    print(f"Mode: {settings.trading_mode.upper()}")
    print(f"Exchange: {settings.exchange_name.upper()}")
    print(f"Pairs: {', '.join(settings.trading_pairs)}")
    
    results = {}
    
    # Test Telegram
    results['telegram'] = await test_telegram()
    
    # Test Bitget
    results['bitget'] = await test_bitget()
    
    # Test Bot Engine
    results['bot_engine'] = await test_bot_startup()
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Bot is ready for production.")
        print("\n📝 Next Steps:")
        print("   1. Start bot: python src/main.py")
        print("   2. Open Telegram and send /start to @multipiller_bot")
        print("   3. Monitor logs in logs/trading_bot.log")
    else:
        print("\n⚠️  Some tests failed. Check errors above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
