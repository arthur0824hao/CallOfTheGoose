import os
from dotenv import load_dotenv

print("🔍 Debugging Environment Variables...")

# Use same path logic as bot.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")

print(f"📂 Looking for .env at: {env_path}")

if os.path.exists(env_path):
    print(f"✅ Found .env file!")
    
    # Read raw bytes
    with open(env_path, "rb") as f:
        raw_content = f.read()
    
    print(f"📄 File size: {len(raw_content)} bytes")
    print(f"📄 Raw bytes (first 100): {raw_content[:100]}")
    
    # Check for BOM
    if raw_content.startswith(b'\xef\xbb\xbf'):
        print("⚠️ WARNING: File has UTF-8 BOM! This might cause issues.")
    
    # Read as text
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"📄 Content repr: {repr(content)}")
        
        # Check each line
        for i, line in enumerate(content.splitlines()):
            print(f"   Line {i+1}: {repr(line)}")
            if "=" in line:
                key, _, value = line.partition("=")
                print(f"      Key: {repr(key.strip())}, Value length: {len(value)}")
    except Exception as e:
        print(f"❌ Failed to read as text: {e}")
else:
    print("❌ .env file NOT FOUND!")

# Try loading with dotenv
print("\n🔄 Loading with dotenv...")
load_dotenv(env_path)

token = os.getenv("DISCORD_TOKEN")
if token:
    print(f"✅ DISCORD_TOKEN found! Length: {len(token)}")
    print(f"🔑 Token preview: {token[:10]}...{token[-5:]}")
else:
    print("❌ DISCORD_TOKEN not found or empty after loading.")
    
    # Check all env vars for similar names
    print("\n🔍 Checking for similar env var names...")
    for key in os.environ:
        if "TOKEN" in key.upper() or "DISCORD" in key.upper():
            print(f"   Found: {key}")

print("\n🏁 Debug complete.")
