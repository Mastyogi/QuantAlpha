"""
Push database schema directly to Supabase using psycopg2/asyncpg.
No Supabase CLI needed.
Usage: python scripts/push_schema.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

def push_schema():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("❌ DATABASE_URL not set in .env")
        sys.exit(1)

    # Convert asyncpg URL to psycopg2 format
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print(f"🔗 Connecting to database...")
    print(f"   URL: {sync_url[:40]}...")

    # Read migration SQL
    migration_file = ROOT / "supabase" / "migrations" / "20260507000001_initial_schema.sql"
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    sql = migration_file.read_text(encoding="utf-8")
    print(f"📄 Migration file: {migration_file.name} ({len(sql)} chars)")

    try:
        import psycopg2
        conn = psycopg2.connect(sync_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("⚙️  Running migration...")
        cur.execute(sql)
        
        # Verify tables created
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        print(f"\n✅ Migration successful! Tables created:")
        for t in tables:
            print(f"   • {t}")
        print(f"\nTotal: {len(tables)} tables")
        
    except ImportError:
        print("psycopg2 not installed, trying asyncpg...")
        import asyncio
        asyncio.run(_push_async(sync_url, sql))


async def _push_async(db_url: str, sql: str):
    import asyncpg
    
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    conn = await asyncpg.connect(url)
    try:
        print("⚙️  Running migration via asyncpg...")
        await conn.execute(sql)
        
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        
        print(f"\n✅ Migration successful! Tables created:")
        for row in tables:
            print(f"   • {row['tablename']}")
        print(f"\nTotal: {len(tables)} tables")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    push_schema()
