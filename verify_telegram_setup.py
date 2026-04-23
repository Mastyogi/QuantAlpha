"""Verify Telegram Setup Before Starting Bot"""
import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load .env
from dotenv import load_dotenv
load_dotenv()

print("\n🔍 VERIFYING TELEGRAM SETUP\n")

# Check 1: Environment variables
print("1️⃣  Checking .env file...")
import os
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID')

if token and token != 'placeholder_token':
    print(f"   ✅ TELEGRAM_BOT_TOKEN: {token[:20]}...")
else:
    print(f"   ❌ TELEGRAM_BOT_TOKEN not set or invalid")
    sys.exit(1)

if chat_id:
    print(f"   ✅ TELEGRAM_ADMIN_CHAT_ID: {chat_id}")
else:
    print(f"   ❌ TELEGRAM_ADMIN_CHAT_ID not set")
    sys.exit(1)

# Check 2: Settings loading
print("\n2️⃣  Checking settings.py...")
from config.settings import settings

if settings.telegram_bot_token and settings.telegram_bot_token != 'placeholder_token':
    print(f"   ✅ settings.telegram_bot_token: {settings.telegram_bot_token[:20]}...")
else:
    print(f"   ❌ settings.telegram_bot_token: {settings.telegram_bot_token}")
    sys.exit(1)

if settings.telegram_admin_chat_id:
    print(f"   ✅ settings.telegram_admin_chat_id: {settings.telegram_admin_chat_id}")
else:
    print(f"   ❌ settings.telegram_admin_chat_id not set")
    sys.exit(1)

# Check 3: Telegram library
print("\n3️⃣  Checking python-telegram-bot...")
try:
    from telegram import Bot
    from telegram.ext import Application
    print("   ✅ python-telegram-bot installed")
except ImportError as e:
    print(f"   ❌ python-telegram-bot not installed: {e}")
    sys.exit(1)

# Check 4: Telegram handlers
print("\n4️⃣  Checking Telegram handlers...")
try:
    from src.telegram.handlers import build_telegram_app
    from src.core.bot_engine import BotEngine
    
    # Create mock engine
    engine = BotEngine()
    app = build_telegram_app(engine)
    
    if hasattr(app, '__aenter__'):
        print("   ✅ Real Telegram app will be created")
    else:
        print("   ❌ Mock Telegram app (something wrong)")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Handler creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("✅ ALL CHECKS PASSED!")
print("="*60)
print("\n🚀 Ready to start bot:")
print("   python src/main.py")
print("\n📱 Then test in Telegram:")
print("   /status")
print()
