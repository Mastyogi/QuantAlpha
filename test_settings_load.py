"""Test if settings loads token correctly"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings

print(f"Token: {settings.telegram_bot_token[:30]}...")
print(f"Is placeholder: {settings.telegram_bot_token == 'placeholder_token'}")
print(f"Is None: {settings.telegram_bot_token is None}")
print(f"Is empty: {settings.telegram_bot_token == ''}")
print(f"Chat ID: {settings.telegram_admin_chat_id}")
