import asyncpg
import os
import asyncio
from dotenv import load_dotenv

# 加載 data/.env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, "data", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

class Database:
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            if not DATABASE_URL:
                # Fallback or error?
                # For development without DB, maybe we should warn?
                # But user asked for migration.
                raise ValueError("DATABASE_URL not set in .env")
            cls._pool = await asyncpg.create_pool(DATABASE_URL)
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    async def execute(cls, query, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def fetchrow(cls, query, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
            
    @classmethod
    async def fetchval(cls, query, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

async def init_db():
    print("🔄 Initializing Database Schema...")
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Characters Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    name TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Initiative Trackers Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS initiative_trackers (
                    channel_id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        print("✅ Database Schema Initialized.")
    except Exception as e:
        print(f"❌ Database Initialization Failed: {e}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(init_db())
