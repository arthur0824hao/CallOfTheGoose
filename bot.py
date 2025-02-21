import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from discord.ui import View, Button
import math
MAX_QUEUE_SIZE = 30
QUEUE_PAGE_SIZE = 10
import re
import glob
from yt_dlp.utils import sanitize_filename
from discord.ext import commands

# 設定允許使用機器人的用戶 ID
AUTHORIZED_USERS = {368572601792069632, bbb, ccc} 
# ---- 設定 Bot ----
import os
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

is_fading_out = False  # ✅ 避免過快切歌
current_page = 0       # ✅ 記錄目前頁數
selected_song_index = ""  # ✅ 記錄選擇的曲目索引 (a.b)
last_page = 1  # ✅ `a` 從 1 開始，代表頁碼
last_selected_number = 1  # ✅ `b` 代表 1~10 的索引

# 音樂佇列
playlist = {
    "songs": [],  # 存放歌曲列表
    "current_index": 0  # 目前播放位置
}

# ---- 機器人啟動 ----
@bot.event
async def on_ready():
    print(f"機器人已上線：{bot.user}")


#---UI---
class ConfirmClearQueueView(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    @discord.ui.button(label="✅ 是，清除所有歌曲", style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: Button):
        """先停止播放，再刪除所有歌曲並初始化播放清單"""
        voice_client = self.ctx.voice_client

        if voice_client and voice_client.is_playing():
            voice_client.stop()  # ✅ 停止播放

        await asyncio.sleep(1)  # ✅ 等待 ffmpeg 釋放檔案

        # ✅ 刪除 `song/` 內所有音樂檔
        for file in glob.glob("song/*.mp3"):
            try:
                os.remove(file)
            except PermissionError:
                await asyncio.sleep(1)  # ✅ 短暫等待，再嘗試刪除
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"❌ 無法刪除 {file}: {e}")

        # ✅ 重置播放清單
        playlist["songs"] = []
        playlist["current_index"] = 0

        await interaction.response.send_message("🗑️ 播放清單已清空，並刪除所有音樂檔！")

    @discord.ui.button(label="❌ 否，回到清單", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: Button):
        """回到 `!list`"""
        await interaction.response.defer()
        await self.ctx.invoke(bot.get_command("list"))

class QueueView(View):
    def __init__(self, ctx, page=0):
        super().__init__()
        self.ctx = ctx
        self.page = page

        self.add_control_buttons()

    def get_queue_text(self):
        """取得當前播放清單的顯示內容"""
        if not queue:
            return "🎧 播放清單是空的！"

        total_pages = math.ceil(len(queue) / QUEUE_PAGE_SIZE)
        start = self.page * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, len(queue))
        queue_slice = queue[start:end]

        queue_text = f"🎼 播放清單 (第 {self.page+1} 頁 / {total_pages} 頁):\n"
        for i, (url, song_title) in enumerate(queue_slice):
            queue_text += f"{start+i+1}. {song_title}\n"

        return queue_text

    def add_control_buttons(self):
        """在底部加入 播放 / 移除 / 下一首 按鈕"""
        self.add_item(QueueControlButton("▶️ 播放", "play", self.ctx))
        self.add_item(QueueControlButton("🗑️ 移除", "remove", self.ctx))
        self.add_item(QueueControlButton("⏭ 下一首", "next", self.ctx))

class QueueActionView(View):
    def __init__(self, ctx, action, page):
        super().__init__()
        self.ctx = ctx
        self.action = action
        self.page = page

        for i in range(min(10, len(queue) - (page * QUEUE_PAGE_SIZE))):
            self.add_item(QueueActionButton(i + 1, ctx, page, action))  # ✅ 傳遞 `action`

class QueuePaginationView(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        global current_page  
        self.total_pages = max(1, math.ceil(len(playlist["songs"]) / QUEUE_PAGE_SIZE))

        self.add_page_buttons()  # ✅ 確保這行不會報錯
        self.add_control_buttons()  # ✅ 確保這行不會報錯

    def get_queue_text(self):
        """取得當前播放清單的顯示內容"""
        if not playlist["songs"]:
            return "🎧 播放清單是空的！"

        start = (current_page - 1) * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, len(playlist["songs"]))
        queue_slice = playlist["songs"][start:end]

        queue_text = f"📜 **播放清單 (第 {current_page} 頁 / {self.total_pages} 頁)**:\n"
        for song in queue_slice:
            page_number, track_number = map(int, song['index'].split('.'))
            adjusted_index = f"{page_number+1}.{track_number}"  # ✅ `a+1` 不能動 ❗
            queue_text += f"{adjusted_index}. {song['title']}\n"

        return queue_text

    def add_page_buttons(self):
        """✅ 新增 1~5 頁的按鈕，避免 `AttributeError`"""
        self.clear_items()  # ✅ 確保不重複添加
        for i in range(1, min(6, self.total_pages + 1)):  # ✅ 確保最多 5 頁
            self.add_item(QueuePageButton(f"第 {i} 頁", self.ctx, i))

    def add_control_buttons(self):
        """✅ 添加底部的 播放 / 移除 / 播放模式 按鈕"""
        self.add_item(QueueControlButton("▶️ 播放", "play", self.ctx)).row = 1
        self.add_item(QueueControlButton("🗑️ 移除", "remove", self.ctx)).row = 1
        self.add_item(PlaybackModeButton(self.ctx)).row = 2  # ✅ 播放模式按鈕

class NowPlayingView(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.loop_mode = "順序播放"
        self.paused = False

    @discord.ui.button(label="⏭ 跳至下一首", style=discord.ButtonStyle.primary)
    async def skip(self, interaction, button):
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.stop()
            await interaction.response.send_message("⏩ 已跳至下一首")

    @discord.ui.button(label="⏸ 暫停", style=discord.ButtonStyle.secondary)
    async def pause_resume(self, interaction, button):
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.pause()
            button.label = "▶️ 播放"
            self.paused = True
            await interaction.response.send_message("⏸ 已暫停")
        elif self.paused:
            self.ctx.voice_client.resume()
            button.label = "⏸ 暫停"
            self.paused = False
            await interaction.response.send_message("▶️ 繼續播放")

    @discord.ui.button(label="🔄 切換循環模式", style=discord.ButtonStyle.success)
    async def toggle_loop(self, interaction, button):
        self.loop_mode = "單曲循環" if self.loop_mode == "順序播放" else "順序播放"
        await interaction.response.send_message(f"🔄 模式切換為：{self.loop_mode}")

class NowPlayingControlView(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.is_paused = False  # 用來記錄目前是否暫停中

    @discord.ui.button(label="⏸ 暫停", style=discord.ButtonStyle.secondary)

    @discord.ui.button(label="⏭ 下一首", style=discord.ButtonStyle.primary)
    async def skip_song(self, interaction: discord.Interaction, button: Button):
        """使用 fadeout 後跳到下一首"""
        voice_client = self.ctx.voice_client
        if voice_client and voice_client.is_playing():
            # 先做fadeout
            await fade_out(voice_client, duration=0.5)
            # fadeout結束後再stop => 會觸發 play_next
            voice_client.stop()
            await interaction.response.send_message("⏩ 已跳至下一首 (含 fadeout)")
        else:
            await interaction.response.send_message("❌ 目前沒有音樂在播放！", ephemeral=True)

    @discord.ui.button(label="📜 清單", style=discord.ButtonStyle.success)
    async def show_list(self, interaction: discord.Interaction, button: Button):
        """呼叫內建的 !list 指令，顯示播放清單"""
        await interaction.response.defer()
        # 直接呼叫原本的 list 指令
        await self.ctx.invoke(bot.get_command("list"))

class SearchView(View):
    def __init__(self, ctx, results):
        super().__init__()
        self.ctx = ctx
        self.results = results

        for i, entry in enumerate(results[:20]):  # ✅ 確保最多 20 個
            button = SearchButton(entry, ctx)
            button.row = i // 4  # ✅ 每 4 個按鈕一行 (最多 5 行)
            self.add_item(button)

class PlaySelectionView(View):
    def __init__(self, ctx, page=0):
        super().__init__()
        self.ctx = ctx
        global current_page  
        current_page = page  # ✅ 記錄當前頁數

        total_songs = len(playlist["songs"])
        total_pages = max(1, math.ceil(total_songs / QUEUE_PAGE_SIZE))
        valid_page = min(current_page, total_pages - 1)  
        start = valid_page * QUEUE_PAGE_SIZE  
        end = min(start + QUEUE_PAGE_SIZE, total_songs)

        for i in range(1, min(QUEUE_PAGE_SIZE + 1, total_songs - start + 1)):  # ✅ 確保不超過範圍
            self.add_item(PlaySelectionButton(i, ctx))  # ✅ 只傳 `i` 和 `ctx`

# ---- 指令 ----
@bot.command()
async def list(ctx):
    """顯示播放清單，支援索引 (a.b)"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    global current_page
    current_page = 1  # ✅ 預設顯示第 1 頁

    if not playlist["songs"]:
        await ctx.send("🎧 播放清單是空的！")
        return

    view = QueuePaginationView(ctx)  
    queue_text = view.get_queue_text()

    try:
        await ctx.send(queue_text, view=view)
    except Exception as e:
        print(f"ERROR: list 發生錯誤: {e}")
        await ctx.send("❌ 顯示播放清單時發生錯誤！")

@bot.command()
async def play(ctx, url=None):
    """播放當前歌曲或顯示選擇清單"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    global playlist, is_fading_out

    if not playlist["songs"]:
        return await ctx.send("❌ 播放清單是空的！")

    # ✅ 如果沒有 URL，顯示選擇清單
    if url is None:
        view = PlaySelectionView(ctx)
        await ctx.send("🎵 選擇要播放的歌曲：", view=view)
        return

    # ✅ 取得 `voice_client`
    voice_client = ctx.voice_client

    # ✅ 確保機器人已加入語音頻道
    if not voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            voice_client = ctx.voice_client
        else:
            return await ctx.send("請先加入語音頻道！")

    # ✅ **檢查是否正在播放**
    if voice_client.is_playing():
        await ctx.send(f"⏳ 下載 `{url}`，準備切換歌曲...")
        song_file = find_downloaded_file(url) or await download_song(url, url)

        if not song_file:
            await ctx.send(f"❌ 無法下載 `{url}`，跳過！")
            return await play_next(ctx)

        await ctx.send("🔄 進行 0.5 秒 fade out，準備切歌...")
        await fade_out(voice_client, duration=0.5)  # ✅ **進行 0.5 秒 fade out**
        voice_client.stop()  # **確認前一首完全停止**

    else:
        await ctx.send(f"⏳ 下載 `{url}`...")
        song_file = find_downloaded_file(url) or await download_song(url, url)

        if not song_file:
            await ctx.send(f"❌ 無法下載 `{url}`，跳過！")
            return await play_next(ctx)

    # ✅ 播放新歌
    source = discord.FFmpegPCMAudio(song_file)
    voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

    embed = discord.Embed(title=f"▶️ 正在播放 `{url}`")
    await ctx.send(embed=embed)

@bot.command()
async def now(ctx):
    """顯示目前播放的歌曲，並提供暫停/播放切換、下一首(含fadeout)、叫出list 按鈕"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    voice_client = ctx.voice_client
    
    # 檢查是否有播放中的音樂
    if not voice_client or not voice_client.is_playing():
        await ctx.send("❌ 目前沒有正在播放的音樂！")
        return
    
    # 從 playlist 取得當前播放曲目（你原程式中的 playlist 與 current_index）
    if not playlist["songs"]:
        await ctx.send("❌ 播放清單是空的，沒有正在播放的音樂！")
        return

    current_song_info = playlist["songs"][playlist["current_index"]]
    current_title = current_song_info["title"]

    embed = discord.Embed(
        title="🎶 現在播放",
        description=f"**{current_title}**"
    )

    # 自訂一個 NowPlayingControlView，含有「暫停/播放」「下一首」「叫出list」按鈕
    view = NowPlayingControlView(ctx)
    await ctx.send(embed=embed, view=view)

@bot.command()
async def join(ctx):
    """讓機器人加入語音頻道"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"已加入 {channel}")
    else:
        await ctx.send("請先加入語音頻道！")

@bot.command()
async def leave(ctx):
    """讓機器人離開語音頻道"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("已離開語音頻道")
    else:
        await ctx.send("我不在語音頻道！")

@bot.command()
async def search(ctx, *, query):
    """搜尋 YouTube 音樂並提供選擇按鈕"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    ydl_opts = {
        'quiet': True,
        'nocheckcertificate': True,
        'extract_flat': True,
        'default_search': f'ytsearch20:{query}',
        'force_generic_extractor': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch20:{query}", download=False) or {}
            results = info.get('entries', []) or []
    except Exception as e:
        await ctx.send(f"❌ 搜尋時發生錯誤: `{e}`")
        return

    if not results:
        await ctx.send("❌ 找不到相關歌曲，請換個關鍵字試試")
        return

    # ✅ 只取得標題與網址，並確保索引符合 `a.b` 格式
    formatted_results = []
    current_total = len(playlist["songs"])

    for i, entry in enumerate(results[:20]):
        title = entry.get('title', '未知標題')
        url = entry.get('url', '')

        page = (current_total + i) // QUEUE_PAGE_SIZE
        track_number = ((current_total + i) % QUEUE_PAGE_SIZE) + 1
        index = f"{page}.{track_number}"

        formatted_results.append({
            'index': index,
            'url': url,
            'title': title,
            'downloaded': False
        })

    view = SearchView(ctx, formatted_results)
    await ctx.send("🔎 請選擇要加入播放清單的歌曲：", view=view)

@bot.command()
async def add(ctx, url):
    """將單首歌曲加入播放清單，並確保標題存在"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    ydl_opts = {'quiet': True, 'format': 'bestaudio/best'}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            song_title = info.get('title', '未知標題')
    except Exception as e:
        await ctx.send(f"❌ 無法取得歌曲資訊：{e}")
        return

    # 計算新的索引
    current_total = len(playlist["songs"])
    page = current_total // QUEUE_PAGE_SIZE
    track_number = (current_total % QUEUE_PAGE_SIZE) + 1
    index = f"{page}.{track_number}"  # `a.b` 格式

    # 加入播放清單
    playlist["songs"].append({
        "index": index,
        "url": url,
        "title": song_title,
        "downloaded": False
    })

    await ctx.send(f"✅ 已加入播放清單：{song_title} (索引：{index})")

@bot.command()
async def add_playlist(ctx, playlist_url):
    """批量加入 YouTube 播放清單，並添加索引 (a.b)"""
    if ctx.author.id not in AUTHORIZED_USERS:
        await ctx.send("🚫 你沒有權限使用這個指令！")
        return
    ydl_opts = {'quiet': True, 'extract_flat': True, 'playlist_items': '1-30'}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        if 'entries' in info:
            current_total = len(playlist["songs"])  # 目前播放清單長度
            for i, entry in enumerate(info['entries']):
                if entry and 'url' in entry:
                    song_title = entry.get('title', '未知標題')
                    page = current_total // QUEUE_PAGE_SIZE
                    track_number = (current_total % QUEUE_PAGE_SIZE) + 1
                    index = f"{page}.{track_number}"  # 產生索引 0.1, 1.1, 1.10
                    
                    playlist["songs"].append({  # ✅ 改為 playlist["songs"]
                        "index": index,
                        "url": entry['url'],
                        "title": song_title,
                        "downloaded": False
                    })
                    current_total += 1

    await ctx.send(f"✅ 已成功導入 {len(playlist['songs'])} 首歌至播放清單！")

#---下載音樂---
async def download_song(url, title):
    """下載歌曲，確保檔名正確"""

    existing_file = find_downloaded_file(title)
    if existing_file:
        print(f"✅ 已存在: {existing_file}")
        return existing_file

    sanitized_title = sanitize_filename(title).replace('.mp3', '')  # 確保不重複 `.mp3`
    output_path = f"song/{sanitized_title}.%(ext)s"  # `yt-dlp` 會自動決定副檔名

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': output_path,  # 讓 `yt-dlp` 自動選擇副檔名
        'quiet': True,
        'nocheckcertificate': True,
        'extractor-args': {'youtube': {'player_client': ['web']}},  # 強制 Web 解析
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        downloaded_file = find_downloaded_file(sanitized_title)
        
        # 🔹 若找不到，則尋找 `song/` 內最新的 `.mp3`
        if not downloaded_file:
            downloaded_file = get_latest_downloaded_mp3()

        # 🔹 確保不會出現 `mp3.mp3`
        if downloaded_file and downloaded_file.endswith(".mp3.mp3"):
            corrected_file = downloaded_file[:-4]
            os.rename(downloaded_file, corrected_file)
            downloaded_file = corrected_file

        if not downloaded_file:
            print(f"❌ 無法找到下載的檔案 `{title}`")
            return None

        print(f"✅ 下載完成: {downloaded_file}")
        return downloaded_file
    except yt_dlp.utils.DownloadError:
        return None

def find_downloaded_file(title):
    """在 `song/` 目錄內搜尋最接近 `title` 的 `.mp3` 檔案"""
    sanitized_title = sanitize_filename(title).replace('.mp3', '')  # 確保不重複 `.mp3`
    files = glob.glob(f"song/{sanitized_title}*.mp3")  # 搜尋所有 `.mp3` 結尾的檔案

    if not files:
        return None

    # 🔹 檢查是否有 `mp3.mp3` 問題，並修正
    for file in files:
        if file.endswith(".mp3.mp3"):
            corrected_file = file[:-4]
            os.rename(file, corrected_file)
            return corrected_file

    return files[0]  # 回傳第一個匹配的 `.mp3`

# 建立 song 目錄（如果不存在）
if not os.path.exists("song"):
    os.makedirs("song")

# ---- 播放音樂 ----
async def play_next(ctx):
    """播放下一首歌曲"""
    global is_playing

    if is_playing:
        return  # ✅ **防止短時間內重複播放**
    
    is_playing = True  # ✅ **標記播放狀態**
    
    if not playlist["songs"]:
        is_playing = False
        return await ctx.send("🎧 播放清單已空！")

    playlist["current_index"] += 1
    if playlist["current_index"] >= len(playlist["songs"]):  
        playlist["current_index"] = 0  # **循環播放**

    next_song = playlist["songs"][playlist["current_index"]]
    url = next_song["url"]

    # ✅ **確認這首歌還沒下載**
    song_file = find_downloaded_file(url)
    if not song_file:
        await ctx.send(f"⏳ 準備下載 `{next_song['title']}`...")
        song_file = await download_song(url, next_song["title"])

    if not song_file:
        is_playing = False
        return await ctx.send(f"❌ 無法下載 `{next_song['title']}`，跳過！")

    # ✅ **fade out 現在的歌**
    await fade_out(ctx.voice_client, 0.5)

    # ✅ **播放新歌**
    source = discord.FFmpegPCMAudio(song_file)
    ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

    embed = discord.Embed(title=f"▶️ 正在播放 `{next_song['title']}`")
    await ctx.send(embed=embed)

    await asyncio.sleep(0.5)
    ctx.voice_client.source.volume = 1.0
    is_playing = False  # ✅ **確保狀態重置**

# --- 雜項---
if not os.path.exists("song"):
    os.makedirs("song")

def get_latest_downloaded_mp3():
    """從 song/ 資料夾中尋找最新下載的 mp3 檔案"""
    files = sorted(glob.glob("song/*.mp3"), key=os.path.getctime, reverse=True)
    return files[0] if files else None

async def fade_out(voice_client, duration=0.5):
    """降低音量實現漸弱"""
    if not voice_client.is_playing():
        return  # 沒有播放則返回

    volume = 1.0  # 初始音量
    step = 0.1    # 每次降低的音量幅度
    delay = duration / (volume / step)  # 根據時間計算 delay

    # ✅ **確保 `source` 是 `PCMVolumeTransformer`**
    if not isinstance(voice_client.source, discord.PCMVolumeTransformer):
        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)

    while volume > 0:
        volume = max(0, volume - step)  # 確保音量不會小於 0
        voice_client.source.volume = volume
        await asyncio.sleep(delay)

    voice_client.stop()  # ✅ **完全靜音後，停止播放**

#---button---

class PlaySelectionButton(Button):
    def __init__(self, number, ctx):
        super().__init__(label=str(number), style=discord.ButtonStyle.primary)
        self.number = number
        self.ctx = ctx  

    async def callback(self, interaction):
        await interaction.response.defer()
        global playlist, current_page, selected_song_index  

        total_songs = len(playlist["songs"])
        total_pages = max(1, math.ceil(total_songs / QUEUE_PAGE_SIZE))

        # **按下按鈕時，確保使用最新的 `current_page`**
        valid_page = current_page - 1  # ✅ `current_page` 是從 1 開始的，要轉換回 0 基數

        index = (valid_page * QUEUE_PAGE_SIZE) + (self.number - 1)  # ✅ 修正 index 計算

        if index >= total_songs:  # ✅ 確保 index 不超出範圍
            await interaction.followup.send("❌ 此曲目不存在！", ephemeral=True)
            return

        # **記錄選擇的歌曲索引**
        selected_song_index = f"{valid_page+1}.{self.number}"  # ✅ (a+1).b 格式

        await play(self.ctx, playlist["songs"][index]["url"])
        await interaction.followup.send(f"🎶 播放 `{playlist['songs'][index]['title']}` (索引: {selected_song_index})！", ephemeral=True)

class SearchButton(Button):
    def __init__(self, entry, ctx):
        shortened_title = entry['title'][:20] + "..." if len(entry['title']) > 20 else entry['title']
        super().__init__(label=shortened_title, style=discord.ButtonStyle.primary)
        self.entry = entry
        self.ctx = ctx

    async def callback(self, interaction):
        if 'url' not in self.entry:
            await interaction.response.send_message("❌ 發生錯誤，請重試！", ephemeral=True)
            return

        # ✅ 加入播放清單
        playlist["songs"].append({
            "index": self.entry['index'],
            "url": self.entry['url'],
            "title": self.entry['title'],
            "downloaded": False
        })

        await interaction.response.send_message(f"✅ 已加入播放清單：{self.entry['title']} (索引：{self.entry['index']})")

class QueuePageButton(Button):
    def __init__(self, label, ctx, target_page):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.ctx = ctx
        self.target_page = target_page  

    async def callback(self, interaction):
        """✅ 點擊頁碼按鈕時，確保 `current_page` 更新"""
        global current_page, last_page  

        # ✅ **更新頁碼**
        last_page = self.target_page + 1  # ✅ `a+1` 不能動 ❗
        current_page = self.target_page  # ✅ `current_page` 繼續從 0 開始計算

        # ✅ **重新產生 UI**
        view = QueuePaginationView(self.ctx)
        queue_text = view.get_queue_text()

        try:
            await interaction.response.edit_message(content=queue_text, view=view)
        except discord.errors.NotFound:
            await interaction.followup.send("⚠️ 交互已失效，請重新輸入 `!list`", ephemeral=True)

class SongButton(Button):
    def __init__(self, label, action, index, ctx):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.action = action
        self.index = index
        self.ctx = ctx

    async def callback(self, interaction):
        if self.action == "loop":
            await interaction.response.send_message(f"🔄 已將歌曲 {queue[self.index]} 設為循環播放")
        elif self.action == "next":
            queue.append(queue.pop(self.index))  # 將此歌曲移至隊列尾部
            await interaction.response.send_message(f"⏩ 已將 {queue[self.index]} 移至下一首")
        elif self.action == "skip":
            queue.pop(self.index)  # 移除此歌曲
            await interaction.response.send_message(f"❌ 已從播放清單中移除 {queue[self.index]}")
        elif self.action == "remove":
            del queue[self.index]
            await interaction.response.send_message(f"🗑️ 已刪除 {queue[self.index]}")
        await self.ctx.invoke(show_queue)

class PlayButton(Button):
    def __init__(self, index, ctx):
        super().__init__(label="▶️ 播放", style=discord.ButtonStyle.success)
        self.index = index
        self.ctx = ctx

    async def callback(self, interaction):
        """播放這首歌，並將當前播放的歌曲放回 queue"""
        voice_client = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)

        if voice_client and voice_client.is_playing():
            now_playing_source = voice_client.source  # 取得當前音樂
            now_playing_title = "當前歌曲"  # 這裡可改成讀取 `queue` 存的標題
            queue.append((now_playing_source, now_playing_title))  # 送回 queue 尾部

        song_to_play = queue.pop(self.index)  # 取出選擇的歌曲
        await play(self.ctx, song_to_play[0])  # 播放
        await interaction.response.send_message(f"🎶 正在播放：{song_to_play[1]}")

class QueueControlButton(Button):
    def __init__(self, label, action, ctx):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.action = action
        self.ctx = ctx

    async def callback(self, interaction):
        await interaction.response.defer()

        if self.action == "play":
            if len(playlist["songs"]) == 0:
                await interaction.followup.send("❌ 播放清單是空的！", ephemeral=True)
                return
            view = PlaySelectionView(self.ctx, current_page)  
            await interaction.followup.send("🎵 選擇要播放的歌曲：", view=view, ephemeral=True)

        elif self.action == "remove":
            if len(playlist["songs"]) == 0:
                await interaction.followup.send("❌ 播放清單是空的！", ephemeral=True)
                return
            
            # ✅ 問使用者是否清空播放清單
            view = ConfirmClearQueueView(self.ctx)
            await interaction.followup.send("⚠️ 是否要清除整個播放清單？", view=view, ephemeral=True)

class QueueActionButton(Button):
    def __init__(self, number, ctx, page, action):
        super().__init__(label=str(number), style=discord.ButtonStyle.secondary)
        self.number = number
        self.ctx = ctx
        self.page = page
        self.action = action  # ✅ 確保區分播放/移除

    async def callback(self, interaction):
        """處理移除動作後將所有索引向前移動"""
        await interaction.response.defer()

        total_songs = len(playlist["songs"])
        total_pages = max(1, math.ceil(total_songs / QUEUE_PAGE_SIZE))
        valid_page = self.page % total_pages  # ✅ 確保頁數循環
        index = (valid_page * QUEUE_PAGE_SIZE) + (self.number - 1)  # ✅ 計算正確索引

        if index >= total_songs:  # ✅ 確保 index 不超出範圍
            await interaction.followup.send("❌ 此曲目不存在！", ephemeral=True)
            return

        if self.action == "remove":
            removed_song = playlist["songs"].pop(index)  # ✅ 直接移除該歌曲
            await interaction.followup.send(f"🗑️ 已移除 `{removed_song['title']}`！", ephemeral=True)

            # ✅ **更新索引，使後面歌曲往前移動**
            for i in range(index, len(playlist["songs"])):
                page, track = map(int, playlist["songs"][i]["index"].split("."))

                # ✅ `a+1` 不能動，確保索引與顯示一致
                new_page = page + 1  # `a+1` 不能動 ❗
                new_track = track - 1 if track > 1 else QUEUE_PAGE_SIZE  # ✅ 調整索引

                playlist["songs"][i]["index"] = f"{new_page}.{new_track}"  # ✅ `a+1` 不能動 ❗

            return await self.ctx.invoke(bot.get_command("list"))  # ✅ 立即更新顯示

class PlaybackModeButton(Button):
    def __init__(self, ctx):
        super().__init__(label="🔄 播放模式：循環整個資料夾", style=discord.ButtonStyle.success)
        self.ctx = ctx
        self.modes = ["循環整個資料夾", "單曲循環", "隨機播放", "播完當前即待機"]
        self.current_mode = 0  # 預設循環整個資料夾

    async def callback(self, interaction):
        """切換播放模式"""
        self.current_mode = (self.current_mode + 1) % len(self.modes)  # 切換模式
        self.label = f"🔄 播放模式：{self.modes[self.current_mode]}"  # 更新按鈕文字

        await interaction.response.defer()  # ✅ 確保不會出現 404 錯誤
        await interaction.message.edit(view=self.view)  # ✅ 確保 `view` 正確更新

# ---- 啟動機器人 ----
bot.run(TOKEN)