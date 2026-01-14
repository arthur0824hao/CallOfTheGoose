
import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from music_utils import log_message, scan_and_update_musicsheet, init_musicsheet_system
from initiative_utils import load_tracker
import shared_state

# 加載環境變數
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ 錯誤: 未找到 DISCORD_BOT_TOKEN 環境變數")
    TOKEN = ""

LOG_DIR = "logs"
SONG_DIR = "song/"

# 初始化 Discord 設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

class GooseBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # 載入 Cogs
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.dice")
        await self.load_extension("cogs.initiative")
        
        # 同步 Slash Commands
        await self.tree.sync()
        print("✅ Slash commands synced!")

    async def on_ready(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(SONG_DIR, exist_ok=True)
        
        # 清空 log
        with open(os.path.join(LOG_DIR, "log.txt"), "w", encoding="utf-8") as f:
            f.write("")
            
        shared_state.playback_mode = "循環播放清單"
        
        log_message(f"✅ 機器人已上線：{self.user}")
        print(f"✅ 機器人已上線：{self.user}")
        
        init_musicsheet_system()
        scan_and_update_musicsheet()
        load_tracker()

    async def on_error(self, event, *args, **kwargs):
        import traceback
        error_info = traceback.format_exc()
        log_message(f"❌ 未捕捉錯誤發生於事件 `{event}`\n{error_info}")
        print(f"❌ 未捕捉錯誤發生於事件 `{event}`")

bot = GooseBot()

@bot.tree.command(name="sync", description="手動同步應用指令")
async def sync(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("✅ 指令已同步！", ephemeral=True)

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
