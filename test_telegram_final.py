"""Final Telegram Test - Single API Call"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load .env
from dotenv import load_dotenv
load_dotenv()


async def main():
    print("\n🤖 TELEGRAM BOT VERIFICATION\n")
    
    try:
        from telegram import Bot
        from config.settings import settings
        
        print(f"Token from .env: {settings.telegram_bot_token[:20]}...")
        print(f"Admin Chat ID: {settings.telegram_admin_chat_id}")
        
        bot = Bot(token=settings.telegram_bot_token)
        
        # Single API call to verify
        info = await bot.get_me()
        
        print("\n✅ TELEGRAM BOT WORKING!\n")
        print(f"Bot Username: @{info.username}")
        print(f"Bot Name: {info.first_name}")
        print(f"Bot ID: {info.id}")
        print(f"Can Join Groups: {info.can_join_groups}")
        
        print("\n📝 Next Steps:")
        print(f"1. Open Telegram and search: @{info.username}")
        print("2. Click START button")
        print("3. Send /start command")
        print("4. Run: python src/main.py")
        print("5. Bot will send you notifications!")
        
        await bot.close()
        
        print("\n🎉 Bot is ready to use!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
        if "Flood control" in str(e):
            print("\n⏳ Telegram rate limit hit.")
            print("Wait 5-10 minutes and try again.")
            print("This is normal after multiple tests.")
        elif "Not Found" in str(e):
            print("\n⚠️  Token is invalid.")
            print("Create new bot with @BotFather")
        else:
            print("\n⚠️  Check your .env file:")
            print("   - TELEGRAM_BOT_TOKEN should have no spaces")
            print("   - Format: 123456789:ABCdefGHI...")
        
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
