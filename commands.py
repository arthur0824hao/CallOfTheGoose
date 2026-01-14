import discord
import yt_dlp
import asyncio
import os
import math
from music_utils import (load_musicsheet, save_musicsheet, download_song,
                        find_downloaded_file, get_next_index, log_message, 
                        debug_log, remove_song, convert_to_pcm, play_next,
                        PCMStreamReader, sanitize_filename,
                        list_musicsheets, create_musicsheet, delete_musicsheet,
                        switch_musicsheet, get_sheet_display_name, rename_musicsheet)
from views import QueuePaginationView, PlaySelectionView, NowPlayingView, SearchView
import shared_state  # 引入共享狀態模組
from dice_utils import (parse_and_roll, format_dice_result, format_multiple_results,
                        DiceParseError, roll_coc_dice, format_coc_result)
from initiative_utils import (add_entry, add_entry_with_roll, remove_entry, get_entry,
                              next_turn, set_stats, modify_hp, modify_elements,
                              add_status, remove_status, reset_tracker, end_combat,
                              get_tracker_display, get_entry_names)

# 全局常量
MAX_SONGS = 50
QUEUE_PAGE_SIZE = 10


async def cmd_help(ctx, *, topic: str = None):
    """
    顯示詳細的幫助訊息
    """
    if topic is None:
        # 主選單
        help_text = """
🤖 **小鵝機器人 - 指令總覽**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 **分類指令說明**
`!help music` - 音樂播放指令
`!help dice` - 擲骰指令
`!help init` - 先攻表指令
`!help sheet` - 歌單管理指令

━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎵 **音樂播放**
`!play <歌名>` - 播放歌曲
`!list` - 顯示播放清單
`!search <關鍵字>` - 搜尋 YouTube
`!add <URL>` - 加入歌曲到清單

🎲 **擲骰系統**
`!r <公式>` - 擲骰 (例: `!r 1d20+5`)

⚔️ **先攻表**
`!init` - 開啟先攻表 (含按鈕操作)

📁 **歌單管理**
`!sheet` - 顯示/切換歌單
"""
        await ctx.send(help_text)
        return
    
    topic = topic.lower().strip()
    
    if topic in ["music", "音樂", "播放"]:
        help_text = """
🎵 **音樂播放指令**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**基本播放**
`!play <歌名>` - 播放清單中的歌曲
`!play <URL>` - 直接播放 YouTube 連結
`!list` - 顯示目前歌單 (含按鈕選擇)
`!now` - 顯示目前播放的歌曲

**搜尋與加入**
`!search <關鍵字>` - 搜尋 YouTube 音樂
`!add <URL>` - 加入單首歌曲到歌單
`!addplaylist <URL>` - 批量加入播放清單

**語音頻道**
`!join` - 加入你的語音頻道
`!leave` - 離開語音頻道並停止播放

**播放模式** (透過 !now 的按鈕切換)
🔁 循環播放清單 - 依序播放後重頭開始
🔂 單曲循環 - 重複播放同一首
🔀 隨機播放 - 隨機選擇下一首
⏹ 播完後待機 - 播完目前歌曲後停止
"""
        await ctx.send(help_text)
    
    elif topic in ["dice", "骰子", "擲骰", "roll", "r"]:
        help_text = """
🎲 **擲骰指令**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**基本格式**
`!r <公式>` - 擲骰一次
`!r .N <公式>` - 擲骰 N 次

**公式範例**
`!r 1d20` - 擲一顆 20 面骰
`!r 1d20+5` - 擲骰並加 5
`!r 2d6+3` - 擲兩顆 6 面骰再加 3
`!r .5 1d20` - 擲 5 次 1d20

**進階語法**
`!r 4d6kh3` - 擲 4 顆 d6，保留最高 3 顆
`!r 2d20kl` - 擲 2 顆 d20，保留最低
`!r 2d20kh` - 擲 2 顆 d20，保留最高

**CoC 擲骰**
`!r cc 65` - CoC 普通擲骰 (技能值 65)
`!r cc1 65` - 1 顆獎勵骰
`!r cc2 65` - 2 顆獎勵骰
`!r ccn1 65` - 1 顆懲罰骰
`!r ccn2 65` - 2 顆懲罰骰
"""
        await ctx.send(help_text)
    
    elif topic in ["init", "先攻", "先攻表", "initiative"]:
        help_text = """
⚔️ **先攻表指令**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**開啟介面**
`!init` - 顯示先攻表 (含完整按鈕操作)

**文字指令**
`!init 1d20+5 戰士` - 擲骰加入角色
`!init add 哥布林 12` - 直接指定先攻加入
`!init remove 哥布林` - 移除角色
`!init next` - 下一位行動者

**數值管理**
`!init stats 戰士 45 3 5 3` - 設定 HP/元素/ATK/DEF
`!init hp 戰士 -10` - 調整 HP
`!init elements 戰士 -1` - 調整元素

**狀態效果**
`!init status 法師 專注` - 新增狀態
`!init unstatus 法師 專注` - 移除狀態

**戰鬥控制**
`!init reset` - 重置回合數
`!init end` - 結束戰鬥

**按鈕功能**
介面提供完整的按鈕操作：
- 新增/移除角色
- 下一位/重置/結束
- 修改 HP/元素/Stats/狀態
- 常用骰 (可儲存每角色的骰子公式)
- 編輯先攻值
"""
        await ctx.send(help_text)
    
    elif topic in ["sheet", "歌單", "musicsheet"]:
        help_text = """
📁 **歌單管理指令**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**顯示歌單**
`!sheet` - 顯示所有歌單及目前選擇

**切換歌單**
`!sheet <名稱>` - 切換到指定歌單

**建立/刪除**
`!sheet new <名稱>` - 建立新歌單
`!sheet new party 派對音樂` - 建立並指定顯示名稱
`!sheet delete <名稱>` - 刪除歌單

**重命名**
`!sheet rename <名稱> <新顯示名>` - 重命名

**特點**
- 每個歌單獨立儲存 (最多 50 首)
- 切換歌單後，`!list` 和 `!play` 操作對應的歌單
- 所有歌單共用同一個 `song/` 音樂檔案庫
- 無法刪除預設歌單 (default)
"""
        await ctx.send(help_text)
    
    else:
        await ctx.send(f"❌ 找不到 `{topic}` 的說明。請使用 `!help` 查看所有分類")


async def cmd_list(ctx):
    """顯示播放清單，確保回應長度不超過 2000 字，並保持 UI"""
    musicsheet_data = load_musicsheet()
    
    if not musicsheet_data or "songs" not in musicsheet_data:
        await ctx.send("❌ 讀取播放清單失敗！請檢查 musicsheet.json", ephemeral=True)
        log_message(f"❌ 讀取 musicsheet.json 失敗，內容: {musicsheet_data}")
        return

    songs = musicsheet_data["songs"]

    if not songs:
        await ctx.send("❌ 播放清單是空的！")
        log_message("❌ `musicsheet.json` 內無歌曲，但應該有 50 首！")
        return

    total_pages = max(1, (len(songs) - 1) // QUEUE_PAGE_SIZE + 1)
    
    # 使用共享狀態模組而非直接引入bot
    shared_state.current_page = 1  # 預設顯示第 1 頁

    start = (shared_state.current_page - 1) * QUEUE_PAGE_SIZE
    end = min(start + QUEUE_PAGE_SIZE, len(songs))
    queue_slice = songs[start:end]

    queue_text = f"📜 **播放清單 (第 {shared_state.current_page} 頁 / {total_pages} 頁)**\n"
    for song in queue_slice:
        queue_text += f"{song['index']}. {song['title']}\n"

    view = QueuePaginationView(ctx)  # 這裡確保 UI 存在
    await ctx.send(queue_text, view=view)

    log_message(f"✅ {ctx.author} 查詢了播放清單，共 {len(songs)} 首歌")

async def cmd_play(ctx, *, title=None):
    """播放指定標題的歌曲。如果提供 URL，先添加到列表再播放"""
    voice_client = ctx.voice_client
    
    # 生成唯一操作ID
    operation_id = shared_state.generate_operation_id()
    shared_state.current_operation_id = operation_id
    log_message(f"🎯 收到播放請求: `{title}` [操作ID: {operation_id[:8]}]")
    
    # 標記這是手動播放，而非自動播放下一首
    shared_state.stop_reason = "manual"
    
    # 重置嘗試計數器
    if hasattr(ctx, 'next_song_attempts'):
        ctx.next_song_attempts = 0

    # 檢查是否提供了 URL 而非標題
    if title and (title.startswith("http://") or title.startswith("https://")):
        url = title
        # 處理URL和播放清單...
        # ...existing URL handling code...
    
    # 確保有標題可用
    if not title:
        await ctx.send("❌ 請提供歌曲標題或URL")
        return
        
    # 確保機器人連線
    if not voice_client or not voice_client.is_connected():
        # ...existing connection code...
        try:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                voice_client = ctx.voice_client
            else:
                log_message("❌ 使用者未在語音頻道，無法重新加入")
                await ctx.send("❌ 請先加入語音頻道！")
                return
        except Exception as e:
            log_message(f"❌ 無法重新加入語音頻道: {e}")
            await ctx.send("❌ 連接語音頻道失敗，請稍後再試")
            return

    # 讀取 `musicsheet.json`
    musicsheet_data = load_musicsheet()
    song_entry = next((s for s in musicsheet_data["songs"] if s["title"] == title), None)

    if not song_entry:
        log_message(f"❌ 找不到 `{title}` 在 `musicsheet.json` 中")
        await ctx.send(f"❌ 找不到歌曲 `{title}`！")
        return

    # 下載歌曲如果需要
    song_file = find_downloaded_file(song_entry["title"])
    if not song_file and song_entry.get("url"):
        # ...existing download code...
        log_message(f"📥 開始下載 `{title}`")
        await ctx.send(f"📥 正在下載 `{title}`，請稍候...")
        song_file = await download_song(song_entry["url"], song_entry["title"], ctx)
        
        if not song_file:
            log_message(f"❌ `{title}` 下載失敗")
            await ctx.send(f"❌ 下載 `{title}` 失敗，請稍後再試")
            return

    # 檢查檔案是否存在
    if not os.path.exists(song_file):
        log_message(f"❌ 檔案不存在: {song_file}")
        await ctx.send(f"❌ 檔案不存在，請重新下載: {title}")
        return
    
    # 設置當前操作狀態
    shared_state.current_operation = 'playing'
    shared_state.current_song_title = title
    
    # 停止當前播放的自訂函數
    async def stop_current_playback():
        if not voice_client:
            return
            
        if voice_client.is_playing() or voice_client.is_paused():
            log_message(f"⏹️ 停止當前播放，準備播放 {title} [手動切換]")
            # 明確標記這是手動停止
            shared_state.stop_reason = "manual"
            voice_client.stop()
            # 等待足夠長的時間確保完全停止
            await asyncio.sleep(1.5)
            
            # 如果仍在播放，進行第二次嘗試
            if voice_client.is_playing():
                log_message("⚠️ 播放尚未完全停止，強制第二次停止...")
                voice_client.stop()
                await asyncio.sleep(0.5)
                
    # 停止當前播放，確保完全停止後再繼續
    await stop_current_playback()

    # 更新 `is_playing`，標記當前歌曲
    for song in musicsheet_data["songs"]:
        song["is_playing"] = (song["title"] == title)
    save_musicsheet(musicsheet_data)

    log_message(f"🎵 播放 `{title}` [操作ID: {operation_id[:8]}]")
    await ctx.send(f"🎵 正在播放 `{title}`")

    # 定義新的播放結束回調，確保不會重複觸發
    def after_playback(error):
        # 確認當前操作ID，如果ID已變更，說明有新的播放請求
        if shared_state.current_operation_id != operation_id:
            log_message(f"🔍 操作ID已變更，跳過自動播放下一首 [舊ID: {operation_id[:8]}, 新ID: {shared_state.current_operation_id[:8]}]")
            return
            
        # 處理錯誤情況
        if error:
            log_message(f"❌ 播放回調發生錯誤: {error}")
            # 不要自動播放下一首
            return
            
        # 根據停止原因決定是否播放下一首
        if shared_state.stop_reason == "manual":
            log_message(f"⏸ 手動停止，不自動播放下一首 [操作ID: {operation_id[:8]}]")
            # 手動切換不自動播放
            return
        else:
            # 標記為自然結束
            shared_state.stop_reason = "finished"
            log_message(f"🎵 播放完成，準備下一首 [自然結束，操作ID: {operation_id[:8]}]")
            # 清理操作狀態
            shared_state.current_operation = None
            shared_state.current_song_title = None
            # 自然結束時自動播放下一首
            asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop)

    # 使用高品質 FFmpeg 參數（不在此處調整音量，統一由 PCMVolumeTransformer 處理）
    options = {
        'options': '-vn -b:a 320k -bufsize 8192k'
    }
    
    # 嘗試播放，加入重試機制
    retries = 3
    for attempt in range(retries):
        try:
            # 播放前再次確認當前沒有在播放
            if voice_client.is_playing():
                log_message(f"🛑 播放前發現聲道正在播放，嘗試強制停止 (嘗試 {attempt+1})")
                voice_client.stop()
                await asyncio.sleep(0.8)
            
            # 播放前確認操作ID未變更
            if shared_state.current_operation_id != operation_id:
                log_message(f"🛑 播放前發現操作ID已變更，放棄當前播放 [舊ID: {operation_id[:8]}]")
                return
                
            # 重置停止原因為自然結束，等待播放結束時的回調處理
            shared_state.stop_reason = "finished"
            
            # 創建音頻源並播放（音量統一在此處調整，避免多重壓縮損失動態範圍）
            source = discord.FFmpegPCMAudio(song_file, **options)
            transformed_source = discord.PCMVolumeTransformer(source, volume=0.5)
            voice_client.play(transformed_source, after=after_playback)
            log_message(f"✅ 開始播放 `{title}` (音量已調整) [操作ID: {operation_id[:8]}]")
            return  # 成功播放後立即返回
            
        except Exception as e:
            log_message(f"⚠ 播放嘗試 {attempt+1}/{retries} 失敗: {e}")
            await asyncio.sleep(1.0)
            
            if "Already playing audio" in str(e) and voice_client.is_playing():
                log_message("⚠️ 檢測到 'Already playing audio' 錯誤，強制停止...")
                voice_client.stop()
                await asyncio.sleep(1.0)
            
            if attempt == retries - 1:
                log_message(f"❌ 播放 `{title}` 失敗，所有嘗試都失敗")
                await ctx.send(f"❌ 播放 `{title}` 失敗: {e}")
                # 重置操作狀態
                shared_state.current_operation = None
                shared_state.current_song_title = None
                return

async def cmd_now(ctx):
    """顯示目前播放的歌曲，確保從 `musicsheet.json` 抓取 `is_playing`"""
    musicsheet_data = load_musicsheet()
    current_song = next((song for song in musicsheet_data["songs"] if song.get("is_playing")), None)

    if not current_song:
        await ctx.send("❌ 目前沒有正在播放的歌曲！")
        return

    embed = discord.Embed(
        title="🎵 現在播放",
        description=f"**{current_song['title']}**",
        color=discord.Color.green()
    )

    view = NowPlayingView(ctx)
    await ctx.send(embed=embed, view=view)

    debug_log(f"🎵 `!now` 取得當前播放歌曲: `{current_song['title']}`")

async def cmd_join(ctx):
    """讓機器人加入語音頻道"""
    if ctx.voice_client is not None:
        if ctx.voice_client.channel == ctx.author.voice.channel:
            await ctx.send("✅ 機器人已在此語音頻道！")
            return
        else:
            await ctx.voice_client.disconnect()
    
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"✅ 已加入 `{channel}`")
    else:
        await ctx.send("❌ 你必須先加入語音頻道！")

async def cmd_leave(ctx):
    """讓機器人停止播放並離開語音頻道"""
    voice_client = ctx.voice_client

    if not voice_client:
        await ctx.send("❌ 機器人不在語音頻道內！")
        return

    # 停止所有播放並清除 `is_playing`
    if voice_client.is_playing():
        log_message("⏹ 停止當前播放的音樂")
        voice_client.stop()

    # 重置 `is_playing` 屬性，避免 `play_next()` 再執行
    musicsheet_data = load_musicsheet()
    for song in musicsheet_data["songs"]:
        song["is_playing"] = False
    save_musicsheet(musicsheet_data)

    # 離開語音頻道
    await voice_client.disconnect()
    log_message(f"👋 `{ctx.author}` 讓機器人離開語音頻道")

    await ctx.send("👋 機器人已離開語音頻道！")

async def cmd_search(ctx, *, query):
    """搜尋 YouTube 音樂並提供選擇按鈕"""
    ydl_opts = {
        'quiet': True,
        'nocheckcertificate': True,
        'extract_flat': True,
        'default_search': f'ytsearch20:{query}',
        'force_generic_extractor': True,
    }

    await ctx.send(f"🔎 正在搜尋 `{query}`...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch20:{query}", download=False) or {}
            results = info.get('entries', []) or []
    except Exception as e:
        await ctx.send(f"❌ 搜尋時發生錯誤: `{e}`")
        return

    if not results:
        await ctx.send(f"❌ 找不到相關結果，請嘗試其他關鍵字", ephemeral=True)
        return

    # 只取得標題與網址，並確保索引符合 `a.b` 格式
    formatted_results = []
    musicsheet_data = load_musicsheet()
    current_total = len(musicsheet_data["songs"])

    for i, entry in enumerate(results[:20]):
        title = entry.get('title', '未知標題')
        url = entry.get('url', '')

        page = (current_total + i) // QUEUE_PAGE_SIZE + 1
        track_number = ((current_total + i) % QUEUE_PAGE_SIZE) + 1
        index = f"{page}.{track_number}"

        formatted_results.append({
            'index': index,
            'url': url,
            'title': title,
            'is_downloaded': False
        })

    view = SearchView(ctx, formatted_results)
    await ctx.send("🔎 請選擇要加入播放清單的歌曲：", view=view)

async def cmd_add(ctx, url):
    """將單首歌曲加入 `musicsheet.json`，但不影響當前播放。如果是播放清單則調用 add_playlist"""
    # 檢查 URL 是否為播放清單 (YouTube 播放清單通常包含 "list=" 參數)
    if "list=" in url or "playlist" in url:
        log_message(f"🔍 檢測到播放清單 URL: {url}")
        await ctx.send("📋 檢測到播放清單 URL，正在處理播放清單...")
        # 直接調用 cmd_add_playlist 處理播放清單
        return await cmd_add_playlist(ctx, playlist_url=url)
    
    musicsheet_data = load_musicsheet()

    if len(musicsheet_data["songs"]) >= MAX_SONGS:
        log_message(f"⚠ `{ctx.author}` 嘗試添加歌曲，但播放清單已滿")
        await ctx.send("❌ 播放清單已滿 (最多 50 首)！")
        return

    # 引入共享狀態的 cookies 配置
    import shared_state
    
    # 設置 yt-dlp 選項
    ydl_opts = {
        'quiet': True, 
        'format': 'bestaudio/best',
        'noplaylist': True  # 確保只下載單個視頻而不是整個播放清單
    }
    
    # 如果存在 cookies 檔案，則加入設定
    if shared_state.youtube_cookies_path:
        log_message(f"🍪 使用 cookies 檔案獲取影片資訊")
        ydl_opts['cookiefile'] = shared_state.youtube_cookies_path
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            song_title = info.get('title', '未知標題').strip()
    except Exception as e:
        log_message(f"❌ `{ctx.author}` 無法取得 `{url}` 的歌曲資訊: {e}")
        await ctx.send(f"❌ 無法取得歌曲資訊：{e}")
        return

    new_song = {
        "title": song_title,
        "is_downloaded": False,
        "url": url,
        "musicsheet": "default",
        "index": get_next_index(musicsheet_data),
        "is_playing": False,
        "is_previous": False,
        "sanitized_title": sanitize_filename(song_title)
    }

    musicsheet_data["songs"].append(new_song)
    save_musicsheet(musicsheet_data)

    log_message(f"✅ `{ctx.author}` 加入 `{song_title}` 到播放清單 (索引：{new_song['index']})")
    await ctx.send(f"✅ 已加入播放清單：{song_title} (索引：{new_song['index']})")

async def cmd_add_playlist(ctx, playlist_url):
    """批量加入 YouTube 播放清單 (寫入 `musicsheet.json`)，直到達到 50 首限制"""
    musicsheet_data = load_musicsheet()
    current_songs_count = len(musicsheet_data["songs"])

    if current_songs_count >= MAX_SONGS:
        await ctx.send("❌ 播放清單已滿 (最多 50 首)！")
        return

    available_slots = MAX_SONGS - current_songs_count
    await ctx.send(f"🔄 正在處理播放清單，還可添加 {available_slots} 首歌曲...")

    # 引入共享狀態的 cookies 配置
    import shared_state
    
    # 設置 yt-dlp 選項
    ydl_opts = {
        'quiet': True, 
        'extract_flat': True, 
        'playlist_items': f'1-{available_slots}'  # 只獲取能添加的數量
    }
    
    # 如果存在 cookies 檔案，則加入設定
    if shared_state.youtube_cookies_path:
        log_message(f"🍪 使用 cookies 檔案獲取播放清單資訊")
        ydl_opts['cookiefile'] = shared_state.youtube_cookies_path
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            
            # 檢查是否成功獲取播放清單資訊
            if not info or "entries" not in info:  # 修正「或」為「or」
                raise ValueError("無法解析播放清單資訊")
                
            entries = info.get('entries', [])
            playlist_title = info.get('title', '未知播放清單')
    except Exception as e:
        log_message(f"❌ 無法取得播放清單資訊：{e}")
        await ctx.send(f"❌ 無法取得播放清單資訊：{e}")
        return

    if not entries:
        await ctx.send("❌ 播放清單為空或無法存取！")
        return

    added_count = 0
    for entry in entries:
        if len(musicsheet_data["songs"]) >= MAX_SONGS:
            break  # 已達上限則停止添加
        
        if entry and 'url' in entry and 'title' in entry:
            title = entry.get('title', '未知標題')
            
            # 檢查這首歌是否已經在播放列表中
            if any(song["title"] == title for song in musicsheet_data["songs"]):
                log_message(f"⚠️ 歌曲 `{title}` 已存在於播放清單中，跳過")
                continue
            
            new_song = {
                "title": title,
                "is_downloaded": False,
                "url": entry['url'],
                "musicsheet": "default",
                "index": get_next_index(musicsheet_data),
                "is_playing": False,
                "is_previous": False,
                "sanitized_title": sanitize_filename(title)
            }
            musicsheet_data["songs"].append(new_song)
            added_count += 1

    save_musicsheet(musicsheet_data)

    log_message(f"✅ `{ctx.author}` 從播放清單 `{playlist_title}` 中加入了 {added_count} 首歌曲")
    await ctx.send(f"✅ 已從播放清單「{playlist_title}」成功加入 {added_count} 首歌曲！" +
                  (f"\n⚠️ 播放清單已達上限 (50 首)" if len(musicsheet_data["songs"]) >= MAX_SONGS else ""))

async def cmd_play_previous(ctx):
    """播放上一首歌曲（依照 `musicsheet.json` 索引）"""
    voice_client = ctx.voice_client

    # 確保 `musicsheet.json` 內有歌曲
    musicsheet_data = load_musicsheet()
    song_list = musicsheet_data["songs"]

    if not song_list:
        log_message("❌ 沒有歌曲可播放！")
        await ctx.send("❌ 播放清單是空的！")
        return

    # 找出目前 `is_playing=True` 的歌曲索引
    current_index = None
    for index, song in enumerate(song_list):
        if song.get("is_playing"):
            current_index = index
            break

    if current_index is None:
        log_message("⚠ 無法取得當前播放歌曲")
        await ctx.send("⚠ 目前沒有播放中的歌曲，將播放第一首")
        # 使用第一首作為默認值
        cmd_play = ctx.bot.get_command("play")
        if cmd_play:
            await ctx.invoke(cmd_play, song_list[0]["title"])
        return

    # 計算上一首的索引
    prev_index = (current_index - 1) % len(song_list)
    prev_song = song_list[prev_index]

    log_message(f"⏮ 切換至上一首: `{prev_song['title']}`")
    
    # 使用play命令播放上一首
    cmd_play = ctx.bot.get_command("play")
    if cmd_play:
        await ctx.invoke(cmd_play, title=prev_song["title"])  # 修改為使用關鍵字參數
    else:
        await ctx.send("❌ 找不到播放命令")

async def cmd_roll(ctx, *, formula: str):
    """
    擲骰命令
    格式：
    - 一般擲骰：!r <公式> 或 !r .N <公式>
    - CoC 擲骰：!r cc[n]N <技能值>

    例如：
    - !r 1d20+3
    - !r .5 2d6+3
    - !r cc1 65 (1顆獎勵骰)
    - !r ccn2 65 (2顆懲罰骰)
    - !r 2d50kh (2d50取最高)
    - !r 5d20kl (5d20取最低)
    """
    try:
        import re

        # 解析重複次數（.N 格式）- 先處理這個
        times = 1
        original_formula = formula

        if formula.startswith('.'):
            # 分離次數和公式
            parts = formula.split(None, 1)
            if len(parts) < 2:
                await ctx.send("❌ 格式錯誤！正確格式：`!r .次數 公式`（例如：`!r .5 1d20+3`）")
                return

            try:
                times_str = parts[0][1:]  # 移除開頭的 '.'
                times = int(times_str)
            except ValueError:
                await ctx.send("❌ 無效的擲骰次數格式！次數必須是整數（例如：`.5`）")
                return

            formula = parts[1]  # 實際的骰子公式

        # 驗證重複次數範圍
        if times < 1:
            await ctx.send("❌ 擲骰次數必須至少為 1！")
            return
        if times > 20:
            await ctx.send("❌ 擲骰次數不能超過 20！")
            return

        # 檢查是否是 CoC 擲骰命令
        # 支持格式：cc 65, cc1 65, ccn2 65, cc1 65 手槍 等
        coc_match = re.match(r'^cc(n)?(\d*)\s+(\d+)', formula.strip(), re.IGNORECASE)

        if coc_match:
            # CoC 擲骰
            is_penalty = coc_match.group(1) is not None  # 有 'n' 表示懲罰骰
            num_dice_str = coc_match.group(2)

            # 如果沒有指定數字，表示正常擲骰（0 = 無獎勵/懲罰）
            if num_dice_str == '':
                num_dice = 0
            else:
                num_dice = int(num_dice_str)

            skill_value = int(coc_match.group(3))

            # 驗證數值範圍
            if num_dice < 0 or num_dice > 3:
                await ctx.send("❌ 獎勵/懲罰骰數量必須在 0-3 之間！（cc = 正常擲骰，cc1-cc3 = 獎勵骰，ccn1-ccn3 = 懲罰骰）")
                return

            if skill_value < 1 or skill_value > 100:
                await ctx.send("❌ 技能值必須在 1-100 之間！")
                return

            # 執行 CoC 擲骰（支持重複）
            is_bonus = not is_penalty

            if times == 1:
                # 單次擲骰
                coc_result = roll_coc_dice(skill_value, num_dice, is_bonus)
                output = format_coc_result(coc_result)
            else:
                # 多次擲骰
                dice_type = "獎勵骰" if is_bonus else "懲罰骰"
                output = f"🎲 CoC 擲骰：技能值 {skill_value}，{dice_type} {num_dice} (重複 {times} 次)\n\n"

                for i in range(times):
                    coc_result = roll_coc_dice(skill_value, num_dice, is_bonus)

                    # 簡化每次的輸出
                    if coc_result.num_dice == 0:
                        rolls_info = f"十位數 {coc_result.tens_digit} | 個位數 {coc_result.ones_digit}"
                    else:
                        rolls_str = ', '.join(map(str, coc_result.bonus_penalty_rolls))
                        select_word = "最低" if coc_result.is_bonus else "最高"
                        rolls_info = f"十位數 [{rolls_str}] → {select_word} {coc_result.selected_tens} | 個位數 {coc_result.ones_digit}"

                    # 結果判定符號
                    if coc_result.is_critical:
                        status = "🌟 大成功"
                    elif coc_result.is_fumble:
                        status = "💀 大失敗"
                    elif coc_result.is_success:
                        status = "✅ 成功"
                    else:
                        status = "❌ 失敗"

                    output += f"第{i+1}次：{rolls_info} → {coc_result.result} ({status})\n"

            await ctx.send(output)

            # 記錄日誌
            dice_type = "獎勵骰" if is_bonus else "懲罰骰"
            log_message(f"🎲 {ctx.author} CoC擲骰：{dice_type}{num_dice} 技能{skill_value} ×{times}")
            return

        # 一般擲骰邏輯
        # 執行擲骰
        results = []
        for i in range(times):
            result, dice_rolls = parse_and_roll(formula)
            results.append((result, dice_rolls))

        # 格式化輸出
        if times == 1:
            # 單次擲骰 - 使用詳細格式
            result, dice_rolls = results[0]
            output = format_dice_result(formula, result, dice_rolls)
        else:
            # 多次擲骰 - 使用簡潔格式
            output = format_multiple_results(formula, results, times)

        # 檢查輸出長度（Discord 限制 2000 字符）
        if len(output) > 2000:
            # 分段發送
            chunks = []
            current_chunk = ""
            for line in output.split('\n'):
                if len(current_chunk) + len(line) + 1 > 1900:
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await ctx.send(chunk.rstrip('\n'))
        else:
            await ctx.send(output)

        # 記錄日誌
        log_message(f"🎲 {ctx.author} 擲骰：{original_formula}")

    except DiceParseError as e:
        # 用戶友好的錯誤訊息
        await ctx.send(f"❌ {str(e)}")
        log_message(f"❌ 擲骰解析錯誤：{formula} - {e}")

    except Exception as e:
        # 未預期的錯誤
        await ctx.send("❌ 發生未預期的錯誤，請稍後再試或檢查公式格式")
        log_message(f"❌ 擲骰未預期錯誤：{formula} - {e}")


async def cmd_init(ctx, *, args: str = None):
    """
    先攻表命令
    
    用法：
    - !init                      顯示先攻表
    - !init 1d20+5 戰士           擲骰加入
    - !init add 哥布林 12         直接加入
    - !init next                 下一位
    - !init remove 哥布林         移除
    - !init stats 戰士 45 3 5 3   設定 HP/元素/ATK/DEF
    - !init hp 戰士 -10           調整 HP
    - !init elements 戰士 -1      調整元素
    - !init status 法師 專注       新增狀態
    - !init unstatus 法師 專注     移除狀態
    - !init end                  結束戰鬥
    - !init reset                重置回合
    """
    from views import InitiativeTrackerView, FavoriteDiceOverviewView
    from initiative_utils import get_favorite_dice_display
    import shared_state

    async def display_init_ui(ctx, force_new=False):
        """
        顯示先攻表 UI (包含常用骰區)
        
        Args:
            ctx: Discord context
            force_new: 強制發送新訊息 (預設 False，嘗試編輯舊訊息)
        """
        channel_id = str(ctx.channel.id)
        display = get_tracker_display(channel_id)
        view = InitiativeTrackerView(ctx)
        
        # 取得現有訊息參考
        msg_refs = shared_state.initiative_messages.get(channel_id, {})
        tracker_msg = msg_refs.get("tracker_msg")
        dice_msg = msg_refs.get("dice_msg")
        
        # 如果強制新訊息，先刪除舊訊息
        if force_new:
            if tracker_msg:
                try:
                    await tracker_msg.delete()
                except Exception:
                    pass
            if dice_msg:
                try:
                    await dice_msg.delete()
                except Exception:
                    pass
            tracker_msg = None
            dice_msg = None
        
        # 嘗試編輯現有訊息，否則發送新訊息
        if tracker_msg:
            try:
                await tracker_msg.edit(content=display, view=view)
            except Exception:
                tracker_msg = await ctx.send(display, view=view)
        else:
            tracker_msg = await ctx.send(display, view=view)
        
        # 顯示常用骰區
        dice_display = get_favorite_dice_display(channel_id)
        if dice_display:
            dice_view = FavoriteDiceOverviewView(ctx)
            if dice_msg:
                try:
                    await dice_msg.edit(content=dice_display, view=dice_view)
                except Exception:
                    dice_msg = await ctx.send(dice_display, view=dice_view)
            else:
                dice_msg = await ctx.send(dice_display, view=dice_view)
        else:
            # 沒有常用骰，刪除舊的常用骰訊息（如果有的話）
            if dice_msg:
                try:
                    await dice_msg.delete()
                except Exception:
                    pass
            dice_msg = None
        
        # 儲存訊息參考
        shared_state.initiative_messages[channel_id] = {
            "tracker_msg": tracker_msg,
            "dice_msg": dice_msg
        }
    
    # 沒有參數時，顯示先攻表 (強制刷新)
    if not args:
        await display_init_ui(ctx, force_new=True)
        return

    
    args = args.strip()
    parts = args.split()
    subcommand = parts[0].lower()
    
    # 子命令處理
    if subcommand == "add":
        # !init add <名字> <先攻值>
        if len(parts) < 3:
            await ctx.send("❌ 格式錯誤！用法：`!init add 名字 先攻值`")
            return
        
        name = parts[1]
        try:
            initiative = int(parts[2])
        except ValueError:
            await ctx.send("❌ 先攻值必須是數字！")
            return
        
        success = add_entry(ctx.channel.id, name, initiative)
        if success:
            await ctx.send(f"✅ 已新增 **{name}** (先攻: {initiative})")
            await display_init_ui(ctx)
        else:
            await ctx.send(f"❌ 角色 **{name}** 已存在！")
    
    elif subcommand == "next":
        # !init next
        channel_id = ctx.channel.id
        name, new_round = next_turn(channel_id)
        if name:
            tracker = shared_state.get_tracker(channel_id)
            if new_round:
                await ctx.send(f"🔄 **第 {tracker['current_round']} 回合開始！** 輪到 **{name}** 行動")
            else:
                await ctx.send(f"⏭ 輪到 **{name}** 行動")
            await display_init_ui(ctx)
        else:
            await ctx.send("❌ 先攻表是空的！")
    
    elif subcommand == "remove":
        # !init remove <名字>
        if len(parts) < 2:
            await ctx.send("❌ 格式錯誤！用法：`!init remove 名字`")
            return
        
        name = parts[1]
        success = remove_entry(ctx.channel.id, name)
        if success:
            await ctx.send(f"✅ 已移除 **{name}**")
            await display_init_ui(ctx)
        else:
            await ctx.send(f"❌ 找不到 **{name}**")
    
    elif subcommand == "stats":
        # !init stats <名字> <HP> [元素] [ATK] [DEF]
        if len(parts) < 3:
            await ctx.send("❌ 格式錯誤！用法：`!init stats 名字 HP [元素] [ATK] [DEF]`")
            return
        
        name = parts[1]
        try:
            hp = int(parts[2]) if len(parts) > 2 else None
            elements = int(parts[3]) if len(parts) > 3 else None
            atk = int(parts[4]) if len(parts) > 4 else None
            def_ = int(parts[5]) if len(parts) > 5 else None
        except ValueError:
            await ctx.send("❌ 數值必須是數字！")
            return
        
        success = set_stats(ctx.channel.id, name, hp=hp, elements=elements, atk=atk, def_=def_)
        if success:
            stats_parts = []
            if hp is not None: stats_parts.append(f"HP: {hp}")
            if elements is not None: stats_parts.append(f"元素: {elements}")
            if atk is not None: stats_parts.append(f"ATK: {atk}")
            if def_ is not None: stats_parts.append(f"DEF: {def_}")
            await ctx.send(f"✅ 已設定 **{name}** 數值: {', '.join(stats_parts)}")
            await display_init_ui(ctx)
        else:
            await ctx.send(f"❌ 找不到 **{name}**")
    
    elif subcommand == "hp":
        # !init hp <名字> <±數值>
        if len(parts) < 3:
            await ctx.send("❌ 格式錯誤！用法：`!init hp 名字 ±數值`")
            return
        
        name = parts[1]
        try:
            delta = int(parts[2])
        except ValueError:
            await ctx.send("❌ 數值必須是數字！")
            return
        
        success, result = modify_hp(ctx.channel.id, name, delta)
        if success:
            await ctx.send(f"{'💚' if delta > 0 else '💔'} **{name}** HP {'+' if delta >= 0 else ''}{delta} → **{result}**")
        else:
            await ctx.send(f"❌ {result}")
    
    elif subcommand == "elements":
        # !init elements <名字> <±數值>
        if len(parts) < 3:
            await ctx.send("❌ 格式錯誤！用法：`!init elements 名字 ±數值`")
            return
        
        name = parts[1]
        try:
            delta = int(parts[2])
        except ValueError:
            await ctx.send("❌ 數值必須是數字！")
            return
        
        success, result = modify_elements(ctx.channel.id, name, delta)
        if success:
            await ctx.send(f"✨ **{name}** 元素 {'+' if delta >= 0 else ''}{delta} → **{result}**")
        else:
            await ctx.send(f"❌ {result}")
    
    elif subcommand == "status":
        # !init status <名字> <狀態>
        if len(parts) < 3:
            await ctx.send("❌ 格式錯誤！用法：`!init status 名字 狀態`")
            return
        
        name = parts[1]
        status = parts[2]
        success = add_status(ctx.channel.id, name, status, "")
        if success:
            await ctx.send(f"✨ **{name}** 獲得狀態 **{status}**")
        else:
            await ctx.send(f"❌ 找不到 **{name}**")
    
    elif subcommand == "unstatus":
        # !init unstatus <名字> <狀態>
        if len(parts) < 3:
            await ctx.send("❌ 格式錯誤！用法：`!init unstatus 名字 狀態`")
            return
        
        name = parts[1]
        status = parts[2]
        success = remove_status(ctx.channel.id, name, status)
        if success:
            await ctx.send(f"⚪ **{name}** 移除狀態 **{status}**")
        else:
            await ctx.send(f"❌ 找不到角色或狀態")
    
    elif subcommand == "end":
        # !init end
        summary = end_combat(ctx.channel.id)
        msg = f"🏁 **戰鬥結束！**\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"📊 總回合數: {summary['total_rounds']}\n"
        msg += f"👥 參戰角色: {summary['total_characters']}\n"
        if summary['survivors']:
            msg += f"✨ 存活者: {', '.join(summary['survivors'])}\n"
        await ctx.send(msg)
    
    elif subcommand == "reset":
        # !init reset
        reset_tracker(ctx.channel.id)
        await ctx.send("🔄 已重置回合數")
        await display_init_ui(ctx)
    
    else:
        # 嘗試解析為骰子公式 + 名字
        # 格式: !init 1d20+5 戰士
        if len(parts) >= 2:
            formula = parts[0]
            name = parts[1]
            
            success, result, roll_detail = add_entry_with_roll(ctx.channel.id, formula, name)
            if success:
                await ctx.send(f"🎲 擲骰: {formula} → {roll_detail}\n✅ 已新增 **{name}** (先攻: {result})")
                await display_init_ui(ctx)
            else:
                await ctx.send(f"❌ {result}")
        else:
            await ctx.send("❌ 未知的子命令！使用 `!init` 查看先攻表")


async def cmd_sheet(ctx, *, args: str = None):
    """
    歌單管理命令
    
    用法：
    - !sheet                    顯示所有歌單
    - !sheet <名稱>              切換到指定歌單
    - !sheet new <名稱> [顯示名] 建立新歌單
    - !sheet delete <名稱>       刪除歌單
    - !sheet rename <名稱> <新顯示名> 重命名歌單
    """
    if args is None:
        # 顯示所有歌單
        sheets = list_musicsheets()
        current = shared_state.current_musicsheet
        
        lines = ["📁 **歌單列表**", "━" * 25]
        for sheet in sheets:
            name = sheet["name"]
            display = sheet.get("display_name", name)
            marker = "▶ " if name == current else "   "
            
            # 讀取歌曲數量
            from music_utils import get_musicsheet_path
            path = get_musicsheet_path(name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    import json
                    data = json.load(f)
                    count = len(data.get("songs", []))
            except:
                count = 0
            
            lines.append(f"{marker}**{display}** (`{name}`) - {count} 首")
        
        lines.append("━" * 25)
        lines.append("`!sheet <名稱>` 切換歌單")
        lines.append("`!sheet new <名稱>` 建立新歌單")
        
        await ctx.send("\n".join(lines))
        return
    
    parts = args.strip().split(maxsplit=2)
    sub_cmd = parts[0].lower()
    
    if sub_cmd == "new":
        # 建立新歌單
        if len(parts) < 2:
            await ctx.send("❌ 用法: `!sheet new <歌單名稱> [顯示名稱]`")
            return
        
        name = parts[1]
        display_name = parts[2] if len(parts) > 2 else None
        
        success, msg = create_musicsheet(name, display_name)
        if success:
            await ctx.send(f"✅ 歌單 **{display_name or name}** 已建立")
        else:
            await ctx.send(f"❌ {msg}")
    
    elif sub_cmd == "delete":
        if len(parts) < 2:
            await ctx.send("❌ 用法: `!sheet delete <歌單名稱>`")
            return
        
        name = parts[1]
        success, msg = delete_musicsheet(name)
        if success:
            await ctx.send(f"🗑️ 歌單 **{name}** 已刪除")
        else:
            await ctx.send(f"❌ {msg}")
    
    elif sub_cmd == "rename":
        if len(parts) < 3:
            await ctx.send("❌ 用法: `!sheet rename <歌單名稱> <新顯示名稱>`")
            return
        
        name = parts[1]
        new_display = parts[2]
        success, msg = rename_musicsheet(name, new_display)
        if success:
            await ctx.send(f"✏️ 歌單 **{name}** 已重命名為 **{new_display}**")
        else:
            await ctx.send(f"❌ {msg}")
    
    else:
        # 切換歌單
        name = sub_cmd
        success, msg = switch_musicsheet(name)
        if success:
            display = get_sheet_display_name(name)
            await ctx.send(f"🔄 已切換到歌單: **{display}**")
        else:
            await ctx.send(f"❌ {msg}")


def register_commands(bot, check_authorization):
    """註冊所有命令到機器人實例"""
    
    @bot.command(name="list")
    async def list_command(ctx):
        if not check_authorization(ctx):
            return
        await cmd_list(ctx)
    
    @bot.command(name="play")
    async def play_command(ctx, *, title):
        if not check_authorization(ctx):
            return
        await cmd_play(ctx, title=title)  # 使用關鍵字參數傳遞 title
    
    @bot.command(name="now")
    async def now_command(ctx):
        if not check_authorization(ctx):
            return
        await cmd_now(ctx)
    
    @bot.command(name="join")
    async def join_command(ctx):
        if not check_authorization(ctx):
            return
        await cmd_join(ctx)
    
    @bot.command(name="leave")
    async def leave_command(ctx):
        if not check_authorization(ctx):
            return
        await cmd_leave(ctx)
    
    @bot.command(name="search")
    async def search_command(ctx, *, query):
        if not check_authorization(ctx):
            return
        await cmd_search(ctx, query=query)
    
    @bot.command(name="add")
    async def add_command(ctx, url):
        if not check_authorization(ctx):
            return
        await cmd_add(ctx, url)
    
    @bot.command(name="addplaylist", aliases=["add_playlist"])
    async def add_playlist_command(ctx, playlist_url):
        if not check_authorization(ctx):
            return
        await cmd_add_playlist(ctx, playlist_url)

    @bot.command(name="r")
    async def roll_command(ctx, *, formula: str):
        if not check_authorization(ctx):
            return
        await cmd_roll(ctx, formula=formula)

    @bot.command(name="init")
    async def init_command(ctx, *, args: str = None):
        if not check_authorization(ctx):
            return
        await cmd_init(ctx, args=args)

    @bot.command(name="sheet")
    async def sheet_command(ctx, *, args: str = None):
        if not check_authorization(ctx):
            return
        await cmd_sheet(ctx, args=args)

    @bot.command(name="help")
    async def help_command(ctx, *, topic: str = None):
        if not check_authorization(ctx):
            return
        await cmd_help(ctx, topic=topic)

    # 移除這些多餘的命令註冊行，因為使用裝飾器時已自動註冊
    # bot.add_command(list_command)
    # bot.add_command(play_command)
    # bot.add_command(now_command)
    # bot.add_command(join_command)
    # bot.add_command(leave_command)
    # bot.add_command(search_command)
    # bot.add_command(add_command)
    # bot.add_command(add_playlist_command)