"""
Create base database tables for trading bot.
Run this before applying Alembic migrations.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_tables():
    """Create all base tables."""
    from src.database.connection import create_tables as create_db_tables
    
    print("Creating base database tables...")
    await create_db_tables()
    print("✅ Base tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())
