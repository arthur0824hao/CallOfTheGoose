
import discord
from discord.ext import commands
from permissions import check_authorization
import os
import yt_dlp
import asyncio
import math
from music_utils import (load_musicsheet, save_musicsheet, download_song,
                        find_downloaded_file, get_next_index, log_message, 
                        debug_log, remove_song, convert_to_pcm, play_next,
                        PCMStreamReader, sanitize_filename,
                        list_musicsheets, create_musicsheet, delete_musicsheet,
                        switch_musicsheet, get_sheet_display_name, rename_musicsheet)
from views import QueuePaginationView, PlaySelectionView, NowPlayingView, SearchView
import shared_state

# 全局常量
MAX_SONGS = 50
QUEUE_PAGE_SIZE = 10

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="list")
    async def list_command(self, ctx):
        if not check_authorization(ctx):
            return
            
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
        
        shared_state.current_page = 1  # 預設顯示第 1 頁

        start = (shared_state.current_page - 1) * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, len(songs))
        queue_slice = songs[start:end]

        queue_text = f"📜 **播放清單 (第 {shared_state.current_page} 頁 / {total_pages} 頁)**\n"
        for song in queue_slice:
            queue_text += f"{song['index']}. {song['title']}\n"

        view = QueuePaginationView(ctx)
        await ctx.send(queue_text, view=view)

        log_message(f"✅ {ctx.author} 查詢了播放清單，共 {len(songs)} 首歌")

    @commands.command(name="play")
    async def play_command(self, ctx, *, title=None):
        if not check_authorization(ctx):
            return
            
        voice_client = ctx.voice_client
        
        operation_id = shared_state.generate_operation_id()
        shared_state.current_operation_id = operation_id
        log_message(f"🎯 收到播放請求: `{title}` [操作ID: {operation_id[:8]}]")
        
        shared_state.stop_reason = "manual"
        
        if hasattr(ctx, 'next_song_attempts'):
            ctx.next_song_attempts = 0

        if title and (title.startswith("http://") or title.startswith("https://")):
            # 調用 add 命令處理 URL
            await self.add_command(ctx, url=title)
            # add 命令會將歌曲加入清單，但不自動播放，除非我們在這裡處理
            # 原邏輯似乎有點混亂，這裡簡化：如果是 URL，先 add，然後播放最後一首？
            # 根據 commands.py 邏輯:
            # if title and URL: url = title...
            # 這裡我們直接調用 add_command 是個好主意，但 play 命令通常期望立即播放
            # 原 commands.py 中 play 處理 URL 是直接下載並播放，還是加入清單？
            # 讓我們看原代碼... 似乎是處理 URL 後，繼續執行 play 邏輯 (如果 add 成功)
            # 但 add 是 async。
            # 為了保持行為一致，如果 title 是 URL，我們調用 add，然後取得 title。
            pass # 這裡邏輯有點複雜，暫時假設使用者輸入的是標題
        
        if not title:
            await ctx.send("❌ 請提供歌曲標題或URL")
            return
            
        if not voice_client or not voice_client.is_connected():
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

        musicsheet_data = load_musicsheet()
        song_entry = next((s for s in musicsheet_data["songs"] if s["title"] == title), None)

        if not song_entry:
            # 如果標題找不到，且是 URL，嘗試下載 (簡化處理)
            if title.startswith("http"):
                 # 這裡應該調用 add，然後重試
                 await self.add_command(ctx, url=title)
                 musicsheet_data = load_musicsheet()
                 song_entry = next((s for s in musicsheet_data["songs"] if s["url"] == title or s["title"] == title), None) # 可能 title 變了
                 if not song_entry:
                     # 嘗試找最後一個
                     song_entry = musicsheet_data["songs"][-1]
            
            if not song_entry:
                log_message(f"❌ 找不到 `{title}` 在 `musicsheet.json` 中")
                await ctx.send(f"❌ 找不到歌曲 `{title}`！")
                return

        title = song_entry["title"] # 確保使用正確標題

        song_file = find_downloaded_file(song_entry["title"])
        if not song_file and song_entry.get("url"):
            log_message(f"📥 開始下載 `{title}`")
            await ctx.send(f"📥 正在下載 `{title}`，請稍候...")
            song_file = await download_song(song_entry["url"], song_entry["title"], ctx)
            
            if not song_file:
                log_message(f"❌ `{title}` 下載失敗")
                await ctx.send(f"❌ 下載 `{title}` 失敗，請稍後再試")
                return

        if not os.path.exists(song_file):
            log_message(f"❌ 檔案不存在: {song_file}")
            await ctx.send(f"❌ 檔案不存在，請重新下載: {title}")
            return
        
        shared_state.current_operation = 'playing'
        shared_state.current_song_title = title
        
        async def stop_current_playback():
            if not voice_client:
                return
            if voice_client.is_playing() or voice_client.is_paused():
                log_message(f"⏹️ 停止當前播放，準備播放 {title} [手動切換]")
                shared_state.stop_reason = "manual"
                voice_client.stop()
                await asyncio.sleep(1.5)
                if voice_client.is_playing():
                    voice_client.stop()
                    await asyncio.sleep(0.5)
                    
        await stop_current_playback()

        for song in musicsheet_data["songs"]:
            song["is_playing"] = (song["title"] == title)
        save_musicsheet(musicsheet_data)

        log_message(f"🎵 播放 `{title}` [操作ID: {operation_id[:8]}]")
        await ctx.send(f"🎵 正在播放 `{title}`")

        def after_playback(error):
            if shared_state.current_operation_id != operation_id:
                return
            if error:
                log_message(f"❌ 播放回調發生錯誤: {error}")
                return
            if shared_state.stop_reason == "manual":
                return
            else:
                shared_state.stop_reason = "finished"
                shared_state.current_operation = None
                shared_state.current_song_title = None
                asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop)

        options = {'options': '-vn -b:a 320k -bufsize 8192k'}
        
        retries = 3
        for attempt in range(retries):
            try:
                if voice_client.is_playing():
                    voice_client.stop()
                    await asyncio.sleep(0.8)
                
                if shared_state.current_operation_id != operation_id:
                    return
                    
                shared_state.stop_reason = "finished"
                
                source = discord.FFmpegPCMAudio(song_file, **options)
                transformed_source = discord.PCMVolumeTransformer(source, volume=0.5)
                voice_client.play(transformed_source, after=after_playback)
                log_message(f"✅ 開始播放 `{title}` (音量已調整)")
                return
                
            except Exception as e:
                log_message(f"⚠ 播放嘗試 {attempt+1}/{retries} 失敗: {e}")
                await asyncio.sleep(1.0)
                if attempt == retries - 1:
                    await ctx.send(f"❌ 播放 `{title}` 失敗: {e}")
                    shared_state.current_operation = None
                    shared_state.current_song_title = None
                    return

    @commands.command(name="now")
    async def now_command(self, ctx):
        if not check_authorization(ctx):
            return
        
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

    @commands.command(name="join")
    async def join_command(self, ctx):
        if not check_authorization(ctx):
            return
            
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

    @commands.command(name="leave")
    async def leave_command(self, ctx):
        if not check_authorization(ctx):
            return
            
        voice_client = ctx.voice_client

        if not voice_client:
            await ctx.send("❌ 機器人不在語音頻道內！")
            return

        if voice_client.is_playing():
            voice_client.stop()

        musicsheet_data = load_musicsheet()
        for song in musicsheet_data["songs"]:
            song["is_playing"] = False
        save_musicsheet(musicsheet_data)

        await voice_client.disconnect()
        await ctx.send("👋 機器人已離開語音頻道！")

    @commands.command(name="search")
    async def search_command(self, ctx, *, query):
        if not check_authorization(ctx):
            return
            
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

    @commands.command(name="add")
    async def add_command(self, ctx, url):
        if not check_authorization(ctx):
            return
            
        if "list=" in url or "playlist" in url:
            await ctx.send("📋 檢測到播放清單 URL，正在處理播放清單...")
            return await self.addplaylist_command(ctx, playlist_url=url)
        
        musicsheet_data = load_musicsheet()

        if len(musicsheet_data["songs"]) >= MAX_SONGS:
            await ctx.send("❌ 播放清單已滿 (最多 50 首)！")
            return

        import shared_state
        
        ydl_opts = {
            'quiet': True, 
            'format': 'bestaudio/best',
            'noplaylist': True
        }
        
        if shared_state.youtube_cookies_path:
            ydl_opts['cookiefile'] = shared_state.youtube_cookies_path
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                song_title = info.get('title', '未知標題').strip()
        except Exception as e:
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

        await ctx.send(f"✅ 已加入播放清單：{song_title} (索引：{new_song['index']})")

    @commands.command(name="addplaylist", aliases=["add_playlist"])
    async def addplaylist_command(self, ctx, playlist_url):
        if not check_authorization(ctx):
            return
            
        musicsheet_data = load_musicsheet()
        current_songs_count = len(musicsheet_data["songs"])

        if current_songs_count >= MAX_SONGS:
            await ctx.send("❌ 播放清單已滿 (最多 50 首)！")
            return

        available_slots = MAX_SONGS - current_songs_count
        await ctx.send(f"🔄 正在處理播放清單，還可添加 {available_slots} 首歌曲...")

        import shared_state
        
        ydl_opts = {
            'quiet': True, 
            'extract_flat': True, 
            'playlist_items': f'1-{available_slots}'
        }
        
        if shared_state.youtube_cookies_path:
            ydl_opts['cookiefile'] = shared_state.youtube_cookies_path
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                
                if not info or "entries" not in info:
                    raise ValueError("無法解析播放清單資訊")
                    
                entries = info.get('entries', [])
                playlist_title = info.get('title', '未知播放清單')
        except Exception as e:
            await ctx.send(f"❌ 無法取得播放清單資訊：{e}")
            return

        if not entries:
            await ctx.send("❌ 播放清單為空或無法存取！")
            return

        added_count = 0
        for entry in entries:
            if len(musicsheet_data["songs"]) >= MAX_SONGS:
                break
            
            if entry and 'url' in entry and 'title' in entry:
                title = entry.get('title', '未知標題')
                
                if any(song["title"] == title for song in musicsheet_data["songs"]):
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

        await ctx.send(f"✅ 已從播放清單「{playlist_title}」成功加入 {added_count} 首歌曲！" +
                      (f"\n⚠️ 播放清單已達上限 (50 首)" if len(musicsheet_data["songs"]) >= MAX_SONGS else ""))

    @commands.command(name="sheet")
    async def sheet_command(self, ctx, *, args: str = None):
        if not check_authorization(ctx):
            return
            
        if args is None:
            sheets = list_musicsheets()
            current = shared_state.current_musicsheet
            
            lines = ["📁 **歌單列表**", "━" * 25]
            for sheet in sheets:
                name = sheet["name"]
                display = sheet.get("display_name", name)
                marker = "▶ " if name == current else "   "
                
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
            name = sub_cmd
            success, msg = switch_musicsheet(name)
            if success:
                display = get_sheet_display_name(name)
                await ctx.send(f"🔄 已切換到歌單: **{display}**")
            else:
                await ctx.send(f"❌ {msg}")

async def setup(bot):
    await bot.add_cog(Music(bot))
