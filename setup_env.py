import os

DATA_DIR = "data"
ENV_PATH = os.path.join(DATA_DIR, ".env")


def setup():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    current_token = ""
    current_db = "postgres://user:password@localhost:5432/goose_db"

    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DISCORD_BOT_TOKEN="):
                        current_token = line.split("=", 1)[1].strip()
                    elif line.startswith("DATABASE_URL="):
                        current_db = line.split("=", 1)[1].strip()
        except Exception:
            pass

    print(f"📍 設定檔路徑: {os.path.abspath(ENV_PATH)}")
    print(
        f"🔑 當前 Token: {current_token[:5]}...{current_token[-5:] if len(current_token) > 10 else ''}"
    )
    print(f"🗄️ 當前資料庫: {current_db}")
    print("-" * 30)

    new_token = input("請輸入 Discord Bot Token (直接按 Enter 保留當前值): ").strip()
    if new_token:
        current_token = new_token

    new_db = input("請輸入 PostgreSQL 連線字串 (直接按 Enter 保留當前值): ").strip()
    if new_db:
        current_db = new_db

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(f"DISCORD_BOT_TOKEN={current_token}\n")
        f.write(f"DATABASE_URL={current_db}\n")

    print(f"\n✅ 設定已更新！請嘗試執行 python bot.py")


if __name__ == "__main__":
    setup()
