"""Initialize database tables."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from src.database.connection import create_tables
    from src.utils.logger import setup_logging
    setup_logging()
    print("Creating database tables...")
    await create_tables()
    print("✅ Database tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
