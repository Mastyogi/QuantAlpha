import asyncio
import signal
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file FIRST before importing anything else
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
    print(f"✅ Loaded .env from: {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed")
except Exception as e:
    print(f"⚠️  Could not load .env: {e}")

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
    logger.info("  AI Trading Bot — Starting Up")
    logger.info(f"  Mode: {settings.trading_mode.upper()}")
    logger.info(f"  Pairs: {', '.join(settings.trading_pairs)}")
    logger.info("=" * 60)

    engine = BotEngine()
    telegram_app = build_telegram_app(engine)

    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, frame):
        print("\n🛑 Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        # Start API server in background
        api_task = asyncio.create_task(run_api_server(engine))

        # Start Telegram bot
        if hasattr(telegram_app, "__aenter__"):
            # Real Telegram app with async context manager
            async with telegram_app:
                await telegram_app.start()
                if hasattr(telegram_app, "updater") and hasattr(telegram_app.updater, "start_polling"):
                    await telegram_app.updater.start_polling(drop_pending_updates=True)

                # Start main bot engine
                engine_task = asyncio.create_task(engine.start())

                # Wait for shutdown signal
                await shutdown_event.wait()

                # Graceful shutdown
                engine_task.cancel()
                api_task.cancel()
                await engine.stop()
                try:
                    await telegram_app.updater.stop()
                    await telegram_app.stop()
                except Exception:
                    pass
        else:
            # Mock telegram — run engine directly
            logger.info("Running without Telegram (mock mode)")
            engine_task = asyncio.create_task(engine.start())
            await shutdown_event.wait()
            engine_task.cancel()
            api_task.cancel()
            await engine.stop()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
