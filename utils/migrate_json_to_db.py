import json
import os
import asyncio
from utils.db import Database, init_db

async def migrate():
    await init_db()
    
    # 1. Initiative Tracker
    INIT_FILE = "initiative_tracker.json"
    if os.path.exists(INIT_FILE):
        print(f"📦 Migrating {INIT_FILE}...")
        try:
            with open(INIT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            channels = data.get("channels", {})
            # Also handle legacy "entries"
            if "entries" in data:
                channels["legacy"] = data
                
            count = 0
            for cid, cdata in channels.items():
                query = """
                    INSERT INTO initiative_trackers (channel_id, data) VALUES ($1, $2)
                    ON CONFLICT (channel_id) DO UPDATE SET data = $2
                """
                await Database.execute(query, str(cid), json.dumps(cdata))
                count += 1
            print(f"✅ Migrated {count} initiative trackers.")
        except Exception as e:
            print(f"❌ Migration failed for initiative: {e}")
            
    # 2. Characters
    CHAR_FILE = "data/characters.json"
    if os.path.exists(CHAR_FILE):
        print(f"📦 Migrating {CHAR_FILE}...")
        try:
            with open(CHAR_FILE, 'r', encoding='utf-8') as f:
                chars = json.load(f)
                
            count = 0
            for name, cdata in chars.items():
                query = """
                    INSERT INTO characters (name, data) VALUES ($1, $2)
                    ON CONFLICT (name) DO UPDATE SET data = $2
                """
                await Database.execute(query, name, json.dumps(cdata))
                count += 1
            print(f"✅ Migrated {count} characters.")
        except Exception as e:
            print(f"❌ Migration failed for characters: {e}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(migrate())
