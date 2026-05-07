"""
QuantAlpha Startup Script
==========================
Checks environment, runs DB migrations, then starts the bot.
Usage: python scripts/start.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    print("✅ .env loaded")
except ImportError:
    print("⚠️  python-dotenv not installed")


def check_env():
    """Verify required environment variables are set."""
    required = ["TELEGRAM_BOT_TOKEN"]
    missing = [k for k in required if not os.getenv(k) or os.getenv(k) == f"your_{k.lower()}"]
    if missing:
        print(f"❌ Missing required env vars: {', '.join(missing)}")
        print(f"   Copy .env.example to .env and fill in the values")
        sys.exit(1)

    mode = os.getenv("TRADING_MODE", "paper")
    broker = os.getenv("BROKER_MODE", "paper")
    print(f"✅ Trading mode: {mode.upper()} | Broker: {broker.upper()}")

    if mode == "live" and broker == "mt5":
        mt5_login = os.getenv("MT5_LOGIN", "0")
        if mt5_login == "0" or not mt5_login:
            print("❌ TRADING_MODE=live + BROKER_MODE=mt5 requires MT5_LOGIN, MT5_PASSWORD, MT5_SERVER")
            sys.exit(1)
        print(f"✅ MT5 configured: login={mt5_login} server={os.getenv('MT5_SERVER')}")

    escrow = os.getenv("ESCROW_CONTRACT_ADDRESS", "")
    if not escrow:
        print("⚠️  ESCROW_CONTRACT_ADDRESS not set — deposit/withdraw in mock mode")
    else:
        print(f"✅ Escrow contract: {escrow[:10]}...")


def check_dependencies():
    """Check critical packages are installed."""
    packages = {
        "telegram": "python-telegram-bot",
        "sqlalchemy": "sqlalchemy",
        "asyncpg": "asyncpg",
        "cryptography": "cryptography",
    }
    missing = []
    for module, pkg in packages.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"   Run: pip install -r requirements.txt")
        sys.exit(1)

    # Optional packages
    try:
        import MetaTrader5
        print("✅ MetaTrader5 package available")
    except ImportError:
        print("⚠️  MetaTrader5 not installed — MT5 live trading unavailable (paper mode OK)")

    try:
        import web3
        print("✅ web3 package available")
    except ImportError:
        print("⚠️  web3 not installed — BSC escrow in mock mode")

    print("✅ Core dependencies OK")


def main():
    print("\n" + "="*50)
    print("  QuantAlpha — Starting Up")
    print("="*50 + "\n")

    check_env()
    check_dependencies()

    print("\n🚀 Starting bot...\n")

    import asyncio
    from src.main import main as bot_main
    asyncio.run(bot_main())


if __name__ == "__main__":
    main()
