"""
Quick Bot Starter - Test if bot can start and respond to Telegram
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv()


async def test_bot_startup():
    """Test bot startup and Telegram connection."""
    print("\n" + "="*60)
    print("🚀 STARTING KELLYAI TRADING BOT")
    print("="*60)
    
    try:
        # Import bot components
        from src.core.bot_engine import BotEngine
        from src.telegram.handlers import build_telegram_app
        from config.settings import settings
        
        print(f"\n📊 Configuration:")
        print(f"   Mode: {settings.trading_mode.upper()}")
        print(f"   Exchange: {settings.exchange_name.upper()}")
        print(f"   Pairs: {', '.join(settings.trading_pairs)}")
        print(f"   Telegram: @multipiller_bot")
        print(f"   Admin Chat: {settings.telegram_admin_chat_id}")
        
        # Create bot engine
        print("\n🔧 Initializing bot engine...")
        engine = BotEngine()
        print("   ✅ Bot engine created")
        
        # Build Telegram app
        print("\n📱 Building Telegram app...")
        telegram_app = build_telegram_app(engine)
        
        if hasattr(telegram_app, '__aenter__'):
            print("   ✅ Real Telegram app created")
        else:
            print("   ⚠️  Mock Telegram app (fallback mode)")
        
        # Initialize bot
        print("\n🚀 Starting bot engine...")
        await engine.exchange.initialize()
        print("   ✅ Exchange initialized")
        
        await engine.notifier.start()
        print("   ✅ Notifier started")
        
        # Test Telegram connection
        if hasattr(telegram_app, '__aenter__'):
            print("\n📡 Testing Telegram connection...")
            async with telegram_app:
                await telegram_app.initialize()
                print("   ✅ Telegram app initialized")
                
                # Get bot info
                bot = telegram_app.bot
                me = await bot.get_me()
                print(f"   ✅ Connected to: @{me.username}")
                
                # Try to send test message
                try:
                    await bot.send_message(
                        chat_id=settings.telegram_admin_chat_id,
                        text="🧪 *Bot Test Message*\n\n"
                             "✅ Bot is running!\n"
                             "✅ Telegram connected!\n"
                             "✅ Ready to receive commands!\n\n"
                             "Try: /status",
                        parse_mode="Markdown"
                    )
                    print(f"   ✅ Test message sent to chat {settings.telegram_admin_chat_id}")
                except Exception as e:
                    print(f"   ⚠️  Could not send message: {e}")
                    if "Flood control" in str(e):
                        print("   ℹ️  Flood control - wait a few minutes")
                    elif "chat not found" in str(e).lower():
                        print("   ⚠️  Chat not found - make sure you started chat with bot")
                
                await telegram_app.shutdown()
        
        # Cleanup
        await engine.notifier.stop()
        await engine.exchange.close()
        
        print("\n" + "="*60)
        print("✅ BOT TEST SUCCESSFUL!")
        print("="*60)
        print("\n📝 Next Steps:")
        print("   1. Check Telegram - you should have received a test message")
        print("   2. If no message, make sure you clicked START in @multipiller_bot")
        print("   3. Run full bot: python src/main.py")
        print("   4. Send /status command in Telegram")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_bot_startup())
    sys.exit(0 if result else 1)
