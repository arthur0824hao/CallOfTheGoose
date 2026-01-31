import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load env to get target credentials
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, "data", ".env"))

TARGET_DB = "goose_db"
TARGET_USER = "user"
TARGET_PASSWORD = "password"

# Default connection to 'postgres' db to perform administrative tasks
# Assumes local postgres installation with default 'postgres' user
# You might need to change the password here if your local postgres 'postgres' user has a password
sys_conn_str = "postgres://postgres:password@localhost:5432/postgres"

async def setup_postgres():
    print(f"🔧 Connecting to system database to setup '{TARGET_DB}'...")
    
    try:
        # Try connecting with password 'password' first (common default)
        conn = await asyncpg.connect(sys_conn_str)
    except Exception as e:
        print(f"⚠️ Could not connect to default 'postgres' database with password 'password'.")
        print(f"   Error: {e}")
        print("   Please enter the password for the local 'postgres' superuser:")
        pwd = input("   Password: ").strip()
        try:
            conn = await asyncpg.connect(user='postgres', password=pwd, database='postgres', host='localhost')
        except Exception as e2:
            print(f"❌ Connection failed: {e2}")
            return

    try:
        # Create User
        try:
            await conn.execute(f"CREATE USER \"{TARGET_USER}\" WITH PASSWORD '{TARGET_PASSWORD}' SUPERUSER;")
            print(f"✅ User '{TARGET_USER}' created.")
        except asyncpg.DuplicateObjectError:
            print(f"ℹ️ User '{TARGET_USER}' already exists.")

        # Create Database
        # Asyncpg cannot execute CREATE DATABASE inside a transaction block, so we perform it separately if possible?
        # Actually asyncpg connection is not in transaction by default unless specified.
        # But CREATE DATABASE cannot run in a transaction block.
        
        # Check if DB exists
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TARGET_DB)
        if not exists:
            await conn.close()
            # Need strict isolation level for CREATE DATABASE? No, just no transaction.
            # Re-connect to execute CREATE DATABASE (auto-commit mode equivalent)
            
            # Note: asyncpg .execute() might implicitly use transactions? No.
            # But CREATE DATABASE is special.
            # Actually, standard psycopg2 requires set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT).
            # asyncpg doesn't have that exact concept, but it works if not in transaction.
            
            # Let's try creating it.
            # If it fails, we might need a different approach or manual step.
            print(f"⏳ Creating database '{TARGET_DB}'...")
            
            # We need a fresh connection for this probably?
            # Or just ensure we are not in a transaction.
            conn = await asyncpg.connect(user='postgres', password=pwd if 'pwd' in locals() else 'password', database='postgres', host='localhost')
            await conn.execute(f'CREATE DATABASE "{TARGET_DB}" OWNER "{TARGET_USER}"')
            print(f"✅ Database '{TARGET_DB}' created.")
        else:
            print(f"ℹ️ Database '{TARGET_DB}' already exists.")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(setup_postgres())
