"""Test handlers.py directly"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

# Load .env
from dotenv import load_dotenv
load_dotenv()

print("Testing handlers.py...")

try:
    from src.telegram.handlers import build_telegram_app
    from src.core.bot_engine import BotEngine
    
    print("✅ Imports successful")
    
    # Create mock engine
    engine = BotEngine()
    print("✅ Engine created")
    
    # Build app
    app = build_telegram_app(engine)
    print(f"✅ App created: {type(app)}")
    
    if hasattr(app, '__aenter__'):
        print("✅ Real Telegram app!")
    else:
        print("⚠️  Mock Telegram app")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
