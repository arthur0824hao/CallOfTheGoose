import discord
from discord.ext import commands
import asyncio
import os
import math
import json
import datetime
import traceback
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

# 引入新拆分的模組
from commands import register_commands
from views import (QueuePaginationView, SearchView, PlaySelectionView, 
                   NowPlayingView, QueueRemoveView, ConfirmClearQueueView)
from buttons import *
from music_utils import (load_musicsheet, convert_to_pcm, download_song,
                         find_downloaded_file, play_next, scan_and_update_musicsheet,
                         save_musicsheet, log_message, debug_log, log_error)
import shared_state  # 引入共享狀態模組

from dotenv import load_dotenv

# 加載環境變數
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)
print(f"🔧 Loading .env from: {ENV_PATH}")

# 設定常數
AUTHORIZED_USERS = {941536363751305296,881630843045544076,368572601792069632,617758239483756567,423816341796028416,358254177434206208} 
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ 錯誤: 未找到 DISCORD_BOT_TOKEN 環境變數，請檢查 .env 檔案")
    # 為避免崩潰，可設為空字串或拋出異常
    # raise ValueError("No DISCORD_TOKEN found")
    TOKEN = ""
LOG_DIR = "logs"
LOG_FILE_PATH = os.path.join(LOG_DIR, "log.txt")
SONG_DIR = "song/"
MAX_SONGS = 50
MAX_QUEUE_SIZE = 50
QUEUE_PAGE_SIZE = 10

# 初始化 Discord 設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
tree = bot.tree

# 全局變數
DEBUG_MODE = True
current_page = 0
selected_song_index = ""
last_page = 1
last_selected_number = 1
is_fading_out = False
executor = ThreadPoolExecutor(max_workers=4)

# 音樂佇列
playlist = {
    "songs": [],  # 存放歌曲列表
    "current_index": 0  # 目前播放位置
}

@bot.event
async def on_ready():
    """機器人啟動時，執行 `scan_and_update_musicsheet()`，確保 `musicsheet.json` 與 `song/` 同步"""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(SONG_DIR, exist_ok=True)

    # 清空 log.txt
    with open(LOG_FILE_PATH, "w", encoding="utf-8") as log_file:
        log_file.write("")

    # 設置預設播放模式到共享狀態
    shared_state.playback_mode = "循環播放清單"  
    
    log_message(f"✅ 機器人已上線：{bot.user}")
    print(f"✅ 機器人已上線：{bot.user}")

    print("加入的伺服器列表：")
    for guild in bot.guilds:
        print(f"- {guild.name} (ID: {guild.id})")

    # 初始化歌單系統
    from music_utils import init_musicsheet_system
    init_musicsheet_system()

    # 掃描 `song/` 並更新 `musicsheet.json`
    scan_and_update_musicsheet()

    # 載入先攻表資料
    from initiative_utils import load_tracker
    load_tracker()

    await tree.sync()

@bot.event
async def on_error(event, *args, **kwargs):
    """捕捉所有未處理的錯誤並記錄到 log.txt"""
    error_info = traceback.format_exc()
    log_message(f"❌ 未捕捉錯誤發生於事件 `{event}`\n{error_info}")
    print(f"❌ 未捕捉錯誤發生於事件 `{event}`，詳細資訊已記錄到 log.txt")

@tree.command(name="sync", description="手動同步應用指令")
async def sync(interaction: discord.Interaction):
    await tree.sync()
    await interaction.response.send_message("✅ 指令已同步！", ephemeral=True)

def check_authorization(ctx):
    """檢查使用者是否有權限使用機器人"""
    if ctx.author.id not in AUTHORIZED_USERS:
        log_message(f"🚫 `{ctx.author}` 嘗試使用 `{ctx.command}` 指令，但沒有權限")
        asyncio.create_task(ctx.send("🚫 你沒有權限使用這個指令！", ephemeral=True))
        return False
    return True

# 註冊命令
register_commands(bot, check_authorization)

# 啟動機器人
bot.run(TOKEN)
