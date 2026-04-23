"""
QuantAlpha Trading Bot - Proper Starter
========================================
This script ensures .env is loaded BEFORE any imports
"""
import asyncio
import signal
import sys
from pathlib import Path

# Step 1: Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Step 2: Load .env FIRST before ANY other imports
from dotenv import load_dotenv
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)
print(f"✅ Loaded .env from: {env_path}")

# Step 3: Verify Telegram token is loaded
import os
token = os.getenv('TELEGRAM_BOT_TOKEN')
if token and token != 'placeholder_token':
    print(f"✅ Telegram token loaded: {token[:20]}...")
else:
    print(f"⚠️  Telegram token not found in .env")

# Step 4: NOW import bot components (after .env is loaded)
from src.core.bot_engine import BotEngine
from src.telegram.handlers import build_telegram_app
from src.utils.logger import setup_logging, get_logger
from src.api.server import create_api_server
from config.settings import settings

logger = get_logger(__name__)


async def run_api_server(engine):
    """Run the FastAPI server in the background."""
    try:
        import uvicorn
        app = create_api_server(engine)
        config = uvicorn.Config(
            app, host="0.0.0.0", port=settings.api_port, log_level="warning"
        )
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        logger.warning(f"API server failed to start: {e}")


async def main():
    """Main application entry point."""
    setup_logging(level=settings.log_level, format=settings.log_format)
    logger.info("=" * 60)
    logger.info("  QuantAlpha Trading Bot — Starting Up")
    logger.info(f"  Mode: {settings.trading_mode.upper()}")
    logger.info(f"  Pairs: {', '.join(settings.trading_pairs)}")
    logger.info("=" * 60)

    engine = BotEngine()
    telegram_app = build_telegram_app(engine)

    # Check if Telegram is working
    if hasattr(telegram_app, "__aenter__"):
        logger.info("✅ Telegram app created successfully")
    else:
        logger.warning("⚠️  Running in mock mode (Telegram not configured)")

    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, frame):
        print("\n🛑 Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        # Start API server in background (disabled for now - port conflict)
        # api_task = asyncio.create_task(run_api_server(engine))
        api_task = None

        # Start Telegram bot
        if hasattr(telegram_app, "__aenter__"):
            # Real Telegram app with async context manager
            async with telegram_app:
                await telegram_app.initialize()
                logger.info("✅ Telegram app initialized")
                
                await telegram_app.start()
                logger.info("✅ Telegram app started")
                
                if hasattr(telegram_app, "updater") and hasattr(telegram_app.updater, "start_polling"):
                    await telegram_app.updater.start_polling(drop_pending_updates=True)
                    logger.info("✅ Telegram polling started")

                # Start main bot engine
                engine_task = asyncio.create_task(engine.start())

                print("\n" + "="*60)
                print("🎉 BOT IS RUNNING!")
                print("="*60)
                print("\n📱 Test in Telegram:")
                print("   1. Open @multipiller_bot")
                print("   2. Send: /status")
                print("   3. You should get bot status!")
                print("\n⏹  Press Ctrl+C to stop\n")

                # Wait for shutdown signal
                await shutdown_event.wait()

                # Graceful shutdown
                print("\n🛑 Shutting down...")
                engine_task.cancel()
                if api_task:
                    api_task.cancel()
                await engine.stop()
                try:
                    await telegram_app.updater.stop()
                    await telegram_app.stop()
                    await telegram_app.shutdown()
                except Exception:
                    pass
        else:
            # Mock telegram — run engine directly
            logger.warning("Running without Telegram (mock mode)")
            engine_task = asyncio.create_task(engine.start())
            
            print("\n" + "="*60)
            print("⚠️  BOT RUNNING IN CONSOLE MODE")
            print("="*60)
            print("\nTelegram is not configured.")
            print("Bot will run but won't respond to Telegram commands.")
            print("\n⏹  Press Ctrl+C to stop\n")
            
            await shutdown_event.wait()
            engine_task.cancel()
            if api_task:
                api_task.cancel()
            await engine.stop()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    print("\n🤖 QuantAlpha Trading Bot")
    print("="*60)
    asyncio.run(main())
