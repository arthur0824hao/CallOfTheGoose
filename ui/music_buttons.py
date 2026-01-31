import discord
from discord.ui import Button
import asyncio
import math
from utils.music import (load_musicsheet, save_musicsheet, find_downloaded_file, 
                         download_song, play_next, remove_song, log_message, debug_log)
import utils.shared_state as shared_state  # 引入共享狀態模組

# 全局常量
QUEUE_PAGE_SIZE = 10

class SearchButton(Button):
    def __init__(self, entry, ctx):
        super().__init__(label=entry['title'][:20] + "...", style=discord.ButtonStyle.primary)
        self.entry = entry
        self.ctx = ctx

    async def callback(self, interaction):
        await interaction.response.defer()
        
        from utils.music import load_musicsheet, get_next_index, save_musicsheet

        musicsheet_data = load_musicsheet()

        if len(musicsheet_data["songs"]) >= 50:  # MAX_SONGS
            await interaction.followup.send("❌ 播放清單已滿 (最多 50 首)！", ephemeral=True)
            return

        new_song = {
            "title": self.entry["title"],
            "is_downloaded": False,
            "url": self.entry["url"],
            "musicsheet": "default",
            "index": get_next_index(musicsheet_data)
        }

        musicsheet_data["songs"].append(new_song)
        save_musicsheet(musicsheet_data)

        debug_log(f"🎵 DEBUG: 已加入 `{new_song['title']}` 至 `musicsheet.json`")

        await interaction.followup.send(f"✅ 已加入播放清單：{new_song['title']} 🎵", ephemeral=True)

class SongButton(Button):
    def __init__(self, label, action, index, ctx):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.action = action
        self.index = index
        self.ctx = ctx

    async def callback(self, interaction):
        # 在全局範圍下獲取queue
        from bot import queue
        
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
        
        # 獲取並調用show_queue命令 
        show_queue = self.ctx.bot.get_command("queue")
        if show_queue:
            await self.ctx.invoke(show_queue)

class NextSongButton(Button):
    def __init__(self, ctx):
        super().__init__(label="⏭ 下一首", style=discord.ButtonStyle.primary)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        """下一首按鈕，觸發 `play_next`"""
        await interaction.response.defer()
        
        # 明確標記這是手動切換
        shared_state.stop_reason = "manual"
        
        # 生成新的操作ID
        operation_id = shared_state.generate_operation_id()
        shared_state.current_operation_id = operation_id
        
        log_message(f"⏭ 手動切換下一首 [ID: {operation_id[:8]}]")
        
        from utils.music import play_next
        await play_next(self.ctx)
        
        await interaction.followup.send("🔄 切換至下一首...", ephemeral=True)

class PlaySelectionButton(Button):
    def __init__(self, number, song, ctx):
        super().__init__(label=str(number), style=discord.ButtonStyle.primary)
        self.number = number
        self.song = song  # 儲存歌曲資訊
        self.ctx = ctx

    async def callback(self, interaction):
        """選擇播放歌曲，並處理 `Unknown interaction` 問題"""
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()  # 避免過期
                
            # 生成新的操作ID
            operation_id = shared_state.generate_operation_id()
            shared_state.current_operation_id = operation_id
            
            # 明確標記這是手動選擇
            shared_state.stop_reason = "manual"
                
            # 提供使用者反饋，但不阻止操作
            if shared_state.current_operation == 'playing':
                log_message(f"👉 有操作正在進行，但仍會處理新請求：{self.song['title']} [ID: {operation_id[:8]}]")

            # 更新當前操作狀態
            song_title = self.song['title']
            shared_state.current_operation = 'playing'
            shared_state.current_song_title = song_title
        
            debug_log(f"🎵 播放選擇：{song_title} [ID: {operation_id[:8]}]")
            
            # 檢查歌曲是否可用
            song_file = find_downloaded_file(song_title)
            
            if not song_file and not self.song.get("url"):
                await interaction.followup.send(f"⚠️ 無法找到歌曲檔案或下載URL: {song_title}", ephemeral=True)
                
                # 自動從播放清單移除此歌曲
                musicsheet_data = load_musicsheet()
                musicsheet_data["songs"] = [s for s in musicsheet_data["songs"] if s["title"] != song_title]
                save_musicsheet(musicsheet_data)
                
                await interaction.followup.send(f"已自動從播放清單移除無效歌曲: {song_title}", ephemeral=True)
                # 重置操作狀態
                shared_state.current_operation = None
                shared_state.current_song_title = None
                return
                
            # 更新播放標記以確保切換順暢
            musicsheet_data = load_musicsheet()
            for song in musicsheet_data["songs"]:
                song["is_playing"] = (song["title"] == song_title)
            save_musicsheet(musicsheet_data)
            
            # 獲取play命令
            play_cmd = self.ctx.bot.get_command("play")
            if play_cmd:
                try:
                    # 重置嘗試計數器
                    if hasattr(self.ctx, 'next_song_attempts'):
                        self.ctx.next_song_attempts = 0
                    
                    # 使用關鍵字參數來傳遞 title
                    await self.ctx.invoke(play_cmd, title=song_title)
                    log_message(f"🎮 按鈕指令: 播放 {song_title} [ID: {operation_id[:8]}]")
                    await interaction.followup.send(f"🎶 正在播放：{song_title} 🎵", ephemeral=True)
                except Exception as e:
                    log_message(f"❌ 播放命令執行錯誤: {e}")
                    await interaction.followup.send(f"❌ 播放失敗: {e}", ephemeral=True)
                    # 重置操作狀態
                    shared_state.current_operation = None
                    shared_state.current_song_title = None
            else:
                await interaction.followup.send("❌ 找不到播放命令", ephemeral=True)
                # 重置操作狀態
                shared_state.current_operation = None
                shared_state.current_song_title = None

        except discord.errors.NotFound:
            log_message("⚠ 按鈕點擊超時，重新發送 UI")
            # 重置操作狀態
            shared_state.current_operation = None
            shared_state.current_song_title = None

            # UI 超時，重新發送 `!list` 讓使用者重新選擇
            list_cmd = self.ctx.bot.get_command("list")
            if list_cmd:
                await self.ctx.invoke(list_cmd)
        except Exception as e:
            log_message(f"❌ 播放選擇按鈕錯誤: {e}")
            # 重置操作狀態
            shared_state.current_operation = None
            shared_state.current_song_title = None
            
            # 捕獲所有其他例外並回報
            try:
                await interaction.followup.send(f"❌ 處理播放選擇時出錯: {e}", ephemeral=True)
            except:
                await self.ctx.send(f"❌ 處理播放選擇時出錯: {e}")

class PlayButton(Button):
    def __init__(self, index, ctx):
        super().__init__(label="▶️ 播放", style=discord.ButtonStyle.success)
        self.index = index
        self.ctx = ctx

    async def callback(self, interaction):
        """播放這首歌，並將當前播放的歌曲放回 queue"""
        from bot import queue
        
        voice_client = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)

        if voice_client and voice_client.is_playing():
            now_playing_source = voice_client.source  # 取得當前音樂
            now_playing_title = "當前歌曲"  # 這裡可改成讀取 `queue` 存的標題
            queue.append((now_playing_source, now_playing_title))  # 送回 queue 尾部

        song_to_play = queue.pop(self.index)  # 取出選擇的歌曲
        
        # 獲取play命令
        play_cmd = self.ctx.bot.get_command("play")
        if play_cmd:
            await self.ctx.invoke(play_cmd, song_to_play[0])  # 播放
        
        await interaction.response.send_message(f"🎶 正在播放：{song_to_play[1]}")

class PlaybackModeButton(Button):
    def __init__(self, ctx):
        super().__init__(label="🔄 播放模式：循環整個資料夾", style=discord.ButtonStyle.success)
        self.ctx = ctx
        self.modes = ["循環播放清單", "單曲循環", "隨機播放", "播完後待機"]
        self.current_mode = 0  # 預設「循環播放清單」

    async def callback(self, interaction):
        """切換播放模式，並同步 shared_state 狀態與 UI 標籤"""
        self.current_mode = (self.current_mode + 1) % len(self.modes)
        new_mode = self.modes[self.current_mode]

        # 直接同步到 shared_state
        import utils.shared_state as shared_state
        shared_state.playback_mode = new_mode

        self.label = f"🔄 播放模式：{new_mode}"
        await interaction.response.defer()
        await interaction.message.edit(view=self.view)

        await interaction.followup.send(f"🔄 播放模式已切換為：**{new_mode}**", ephemeral=True)

class PrevSongButton(Button):
    def __init__(self, ctx):
        super().__init__(label="⏮ 上一首", style=discord.ButtonStyle.primary)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        """切換到上一首歌曲"""
        await interaction.response.defer()

        log_message("🔄 `上一首` 按鈕觸發，呼叫 `play_previous(ctx)`")

        # 獲取並調用play_previous函數
        from commands import cmd_play_previous
        await cmd_play_previous(self.ctx)

        await interaction.followup.send("🔄 切換至上一首...", ephemeral=True)

class PauseResumeButton(Button):
    def __init__(self, ctx):
        super().__init__(label="⏸ 暫停", style=discord.ButtonStyle.secondary)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        """暫停或繼續播放，確保 `is_playing` 保持正確"""
        voice_client = self.ctx.voice_client
        musicsheet_data = load_musicsheet()
        current_song = next((s for s in musicsheet_data["songs"] if s.get("is_playing", False)), None)

        if not voice_client or not current_song:
            await interaction.response.send_message("❌ 目前沒有播放中的歌曲！", ephemeral=True)
            return

        if voice_client.is_playing():
            voice_client.pause()
            current_song["is_playing"] = True  # 確保暫停時 `is_playing` 仍維持 True
            self.label = "▶️ 播放"
        else:
            voice_client.resume()
            current_song["is_playing"] = True  # 確保恢復時 `is_playing` 仍維持 True
            self.label = "⏸ 暫停"

        save_musicsheet(musicsheet_data)  # 確保 `musicsheet.json` 也同步
        await interaction.response.edit_message(view=self.view)  # 修正 UI 交互失效

class QueueRemoveButton(Button):
    def __init__(self, number, ctx, page):
        super().__init__(label=str(number), style=discord.ButtonStyle.danger)
        self.number = number
        self.ctx = ctx
        self.page = page

    async def callback(self, interaction):
        """移除選擇的歌曲，並更新 `!list`"""
        await interaction.response.defer()

        import utils.shared_state as shared_state
        async with shared_state.music_lock:
            musicsheet_data = load_musicsheet()
            total_songs = len(musicsheet_data["songs"])
            start = (self.page - 1) * QUEUE_PAGE_SIZE
            index = start + (self.number - 1)  # 計算正確索引

            if index >= total_songs:  
                await interaction.followup.send("❌ 此曲目不存在！", ephemeral=True)
                return

            removed_song = musicsheet_data["songs"][index]
            song_title = removed_song["title"]

            # 刪除歌曲
            remove_song(song_title)

        debug_log(f"🗑️ DEBUG: `{song_title}` 已移除，更新後清單: {len(musicsheet_data['songs'])} 首")

        # 原地刷新介面
        from ui.music_views import QueuePaginationView
        view = QueuePaginationView(self.ctx)
        content = view.get_queue_text()
        await interaction.message.edit(content=content, view=view)

class QueueClearButton(Button):
    def __init__(self, ctx):
        super().__init__(label="🗑️ 清空播放清單", style=discord.ButtonStyle.danger, row=2)
        self.ctx = ctx

    async def callback(self, interaction):
        """確認是否清空播放清單"""
        await interaction.response.defer()

        debug_log("🛠 DEBUG: QueueClearButton clicked - Asking for confirmation")

        # 問使用者是否清空播放清單
        from ui.music_views import ConfirmClearQueueView
        view = ConfirmClearQueueView(self.ctx)
        await interaction.followup.send("⚠️ 確定要刪除整個播放清單嗎？", view=view, ephemeral=True)

class QueuePageButton(Button):
    def __init__(self, label, ctx, target_page):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.ctx = ctx
        self.target_page = target_page  

    async def callback(self, interaction):
        """點擊頁碼按鈕時，確保 `current_page` 更新"""
        # 使用共享狀態模組
        shared_state.current_page = self.target_page

        # 重新產生 UI
        from ui.music_views import QueuePaginationView
        view = QueuePaginationView(self.ctx)
        queue_text = view.get_queue_text()

        try:
            await interaction.response.edit_message(content=queue_text, view=view)
        except discord.errors.NotFound:
            await interaction.followup.send("⚠️ 交互已失效，請重新輸入 `!list`", ephemeral=True)

class QueueControlButton(Button):
    def __init__(self, label, action, ctx):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.action = action
        self.ctx = ctx

    async def callback(self, interaction):
        await interaction.response.defer()

        musicsheet_data = load_musicsheet()  # 確保重新讀取最新 `musicsheet.json`

        if self.action == "play":
            if not musicsheet_data["songs"]:
                await interaction.followup.send("❌ 播放清單是空的！", ephemeral=True)
                return

            debug_log("🛠 DEBUG: `QueueControlButton` 觸發播放 UI")

            # 重新整理當前頁面歌曲
            current_page_songs = [
                song for song in musicsheet_data["songs"]
                if int(song["index"].split(".")[0]) == shared_state.current_page  # 使用共享狀態
            ]

            if not current_page_songs:
                await interaction.followup.send("❌ 此頁沒有可播放的歌曲！", ephemeral=True)
                return

            from ui.music_views import PlaySelectionView
            view = PlaySelectionView(self.ctx, current_page_songs)  # 修正: this.ctx -> self.ctx
            await interaction.followup.send("🎵 選擇要播放的歌曲：", view=view, ephemeral=True)

        elif self.action == "remove":
            if not musicsheet_data["songs"]:
                await interaction.followup.send("❌ 播放清單是空的！", ephemeral=True)
                return

            debug_log("🛠 DEBUG: `QueueControlButton` 觸發移除 UI")

            from ui.music_views import QueueRemoveView
            view = QueueRemoveView(self.ctx, shared_state.current_page)  # 修正: this.ctx -> self.ctx
            await interaction.followup.send("🗑️ 請選擇要移除的歌曲：", view=view, ephemeral=True)

        elif self.action == "next":
            # 獲取並調用play_next函數
            from utils.music import play_next
            await play_next(self.ctx)  # 修正: this.ctx -> self.ctx
            await interaction.followup.send("🔄 切換至下一首...", ephemeral=True)

class QueueActionButton(Button):
    def __init__(self, number, ctx, page, action):
        super().__init__(label=str(number), style=discord.ButtonStyle.secondary)
        self.number = number
        self.ctx = ctx
        self.page = page
        self.action = action  # 確保區分播放/移除

    async def callback(self, interaction):
        """處理移除動作後將所有索引向前移動"""
        await interaction.response.defer()

        from bot import playlist
        
        total_songs = len(playlist["songs"])
        total_pages = max(1, math.ceil(total_songs / QUEUE_PAGE_SIZE))
        valid_page = self.page % total_pages  # 修正: this.page -> self.page
        index = (valid_page * QUEUE_PAGE_SIZE) + (self.number - 1)  # 修正: this.number -> self.number

        if index >= total_songs:  # 確保 index 不超出範圍
            await interaction.followup.send("❌ 此曲目不存在！", ephemeral=True)
            return

        if self.action == "remove":  # 修正: this.action -> self.action
            removed_song = playlist["songs"].pop(index)  # 直接移除該歌曲
            await interaction.followup.send(f"🗑️ 已移除 `{removed_song['title']}`！", ephemeral=True)

            # 更新索引，使後面歌曲往前移動
            for i in range(index, len(playlist["songs"])):
                page, track = map(int, playlist["songs"][i]["index"].split("."))

                # `a+1` 不能動，確保索引與顯示一致
                new_page = page + 1  # `a+1` 不能動
                new_track = track - 1 if track > 1 else QUEUE_PAGE_SIZE  # 調整索引

                playlist["songs"][i]["index"] = f"{new_page}.{new_track}"  # `a+1` 不能動

            # 獲取list命令
            list_cmd = self.ctx.bot.get_command("list")  # 修正: this.ctx -> self.ctx
            if list_cmd:
                return await self.ctx.invoke(list_cmd)  # 修正: this.ctx -> self.ctx

