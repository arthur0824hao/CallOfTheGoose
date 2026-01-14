
import asyncio
from music_utils import log_message

# 設定常數
AUTHORIZED_USERS = {941536363751305296,881630843045544076,368572601792069632,617758239483756567,423816341796028416,358254177434206208}

def check_authorization(ctx):
    """檢查使用者是否有權限使用機器人"""
    if ctx.author.id not in AUTHORIZED_USERS:
        log_message(f"🚫 `{ctx.author}` 嘗試使用 `{ctx.command}` 指令，但沒有權限")
        asyncio.create_task(ctx.send("🚫 你沒有權限使用這個指令！", ephemeral=True))
        return False
    return True
