import discord
from discord.ui import Button
import asyncio
import math
from music_utils import (load_musicsheet, save_musicsheet, find_downloaded_file, 
                         download_song, play_next, remove_song, log_message, debug_log)
import shared_state  # 引入共享狀態模組

# 全局常量
QUEUE_PAGE_SIZE = 10

class SearchButton(Button):
    def __init__(self, entry, ctx):
        super().__init__(label=entry['title'][:20] + "...", style=discord.ButtonStyle.primary)
        self.entry = entry
        self.ctx = ctx

    async def callback(self, interaction):
        await interaction.response.defer()
        
        from music_utils import load_musicsheet, get_next_index, save_musicsheet

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
        
        from music_utils import play_next
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
        import shared_state
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

        # 重新顯示 `!list`，避免 `404 Unknown Message`
        await interaction.message.delete()
        
        # 獲取list命令
        list_cmd = self.ctx.bot.get_command("list")
        if list_cmd:
            await self.ctx.invoke(list_cmd)

class QueueClearButton(Button):
    def __init__(self, ctx):
        super().__init__(label="🗑️ 清空播放清單", style=discord.ButtonStyle.danger, row=2)
        self.ctx = ctx

    async def callback(self, interaction):
        """確認是否清空播放清單"""
        await interaction.response.defer()

        debug_log("🛠 DEBUG: QueueClearButton clicked - Asking for confirmation")

        # 問使用者是否清空播放清單
        from views import ConfirmClearQueueView
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
        from views import QueuePaginationView
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

            from views import PlaySelectionView
            view = PlaySelectionView(self.ctx, current_page_songs)  # 修正: this.ctx -> self.ctx
            await interaction.followup.send("🎵 選擇要播放的歌曲：", view=view, ephemeral=True)

        elif self.action == "remove":
            if not musicsheet_data["songs"]:
                await interaction.followup.send("❌ 播放清單是空的！", ephemeral=True)
                return

            debug_log("🛠 DEBUG: `QueueControlButton` 觸發移除 UI")

            from views import QueueRemoveView
            view = QueueRemoveView(self.ctx, shared_state.current_page)  # 修正: this.ctx -> self.ctx
            await interaction.followup.send("🗑️ 請選擇要移除的歌曲：", view=view, ephemeral=True)

        elif self.action == "next":
            # 獲取並調用play_next函數
            from music_utils import play_next
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


# ============================================
# 先攻表按鈕
# ============================================

class InitAddButton(Button):
    """新增角色按鈕"""
    def __init__(self, ctx):
        super().__init__(label="➕ 新增角色", style=discord.ButtonStyle.success, row=0)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from views import InitAddModal
        modal = InitAddModal(self.ctx)
        await interaction.response.send_modal(modal)

class InitPrevButton(Button):
    """上一位行動者按鈕"""
    def __init__(self, ctx):
        super().__init__(label="⏮ 上一位", style=discord.ButtonStyle.primary, row=0)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from initiative_utils import prev_turn
        from views import refresh_tracker_view
        
        channel_id = self.ctx.channel.id
        name, current_round = prev_turn(channel_id)
        
        if name:
            await refresh_tracker_view(self.ctx)
        else:
            await interaction.followup.send("❌ 先攻表是空的！", ephemeral=True)

class InitNextButton(Button):
    """下一位行動者按鈕"""
    def __init__(self, ctx):
        super().__init__(label="⏭ 下一位", style=discord.ButtonStyle.primary, row=0)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from initiative_utils import next_turn, get_tracker_display, save_tracker
        from views import InitiativeTrackerView
        
        channel_id = self.ctx.channel.id
        name, new_round = next_turn(channel_id)
        
        if name:
            if new_round:
                tracker = shared_state.get_tracker(channel_id)
                await interaction.followup.send(f"🔄 **第 {tracker['current_round']} 回合開始！** 輪到 **{name}** 行動")
            
            # 刷新顯示
            display = get_tracker_display(channel_id)
            view = InitiativeTrackerView(self.ctx)
            await interaction.message.edit(content=display, view=view)
        else:
            await interaction.followup.send("❌ 先攻表是空的！", ephemeral=True)

class InitRemoveButton(Button):
    """移除角色按鈕"""
    def __init__(self, ctx):
        super().__init__(label="🗑️ 移除角色", style=discord.ButtonStyle.danger, row=0)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import get_entry_names
        from views import InitRemoveView
        
        channel_id = self.ctx.channel.id
        names = get_entry_names(channel_id)
        
        if not names:
            await interaction.response.send_message("❌ 先攻表是空的！", ephemeral=True)
            return
            
        view = InitRemoveView(self.ctx, names)
        await interaction.response.send_message("🗑️ 選擇要移除的角色：", view=view, ephemeral=True)

class InitResetButton(Button):
    """重置回合按鈕"""
    def __init__(self, ctx):
        super().__init__(label="🔄 重置回合", style=discord.ButtonStyle.secondary, row=0)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from initiative_utils import reset_tracker, get_tracker_display
        from views import InitiativeTrackerView
        
        channel_id = self.ctx.channel.id
        reset_tracker(channel_id)
        
        display = get_tracker_display(channel_id)
        view = InitiativeTrackerView(self.ctx)
        await interaction.message.edit(content=display, view=view)
        await interaction.followup.send("🔄 已重置回合數", ephemeral=True)

class InitEndButton(Button):
    """結束戰鬥按鈕"""
    def __init__(self, ctx):
        super().__init__(label="🏁 結束戰鬥", style=discord.ButtonStyle.danger, row=1)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from views import InitEndConfirmView
        view = InitEndConfirmView(self.ctx)
        await interaction.response.send_message("⚠️ 確定要結束戰鬥並清空先攻表嗎？", view=view, ephemeral=True)

class InitStatsButton(Button):
    """設定數值按鈕"""
    def __init__(self, ctx):
        super().__init__(label="📊 設定數值", style=discord.ButtonStyle.secondary, row=1)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import get_entry_names, get_selected_character
        from views import InitCharacterSelectView, InitStatsModalWithName
        
        channel_id = self.ctx.channel.id
        selected = get_selected_character(channel_id)
        
        if selected:
            modal = InitStatsModalWithName(self.ctx, selected)
            await interaction.response.send_modal(modal)
            return
            
        names = get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "stats")
        await interaction.response.send_message("📊 選擇要設定數值的角色：", view=view, ephemeral=True)

class InitHPButton(Button):
    """調整 HP 按鈕"""
    def __init__(self, ctx):
        super().__init__(label="❤️ 調整 HP", style=discord.ButtonStyle.secondary, row=1)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import get_entry_names, get_selected_character
        from views import InitCharacterSelectView, InitHPModalWithName
        
        channel_id = self.ctx.channel.id
        selected = get_selected_character(channel_id)
        
        if selected:
            modal = InitHPModalWithName(self.ctx, selected)
            await interaction.response.send_modal(modal)
            return
            
        names = get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "hp")
        await interaction.response.send_message("❤️ 選擇要調整 HP 的角色：", view=view, ephemeral=True)

class InitStatusButton(Button):
    """狀態管理按鈕"""
    def __init__(self, ctx):
        super().__init__(label="✨ 狀態管理", style=discord.ButtonStyle.secondary, row=1)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import get_entry_names
        from views import InitStatusActionSelectView
        
        channel_id = self.ctx.channel.id
        names = get_entry_names(channel_id)
        
        view = InitStatusActionSelectView(self.ctx, names)
        await interaction.response.send_message("✨ 選擇狀態操作：", view=view, ephemeral=True)

class InitFavDiceEditButton(Button):
    """編輯常用骰按鈕 (新增/修改/刪除)"""
    def __init__(self, ctx):
        super().__init__(label="🎲 編輯常用骰", style=discord.ButtonStyle.secondary, row=1)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from views import InitFavDiceActionSelectView
        
        view = InitFavDiceActionSelectView(self.ctx)
        await interaction.response.send_message("🎲 選擇常用骰操作：", view=view, ephemeral=True)

class InitFavDiceRollButton(Button):
    """擲常用骰按鈕"""
    def __init__(self, ctx):
        super().__init__(label="🎲 擲常用骰", style=discord.ButtonStyle.primary, row=2)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import get_entry_names, get_selected_character, get_favorite_dice_names
        from views import InitCharacterSelectView, InitFavDiceRollSelectView
        
        channel_id = self.ctx.channel.id
        selected = get_selected_character(channel_id)
        
        if selected:
            dice_names = get_favorite_dice_names(channel_id, selected)
            if not dice_names:
                await interaction.response.send_message(f"❌ **{selected}** 沒有常用骰！", ephemeral=True)
                return
            view = InitFavDiceRollSelectView(self.ctx, selected, dice_names)
            await interaction.response.send_message(f"🎲 選擇 **{selected}** 的常用骰：", view=view, ephemeral=True)
            return
            
        names = get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "fav_dice_roll")
        await interaction.response.send_message("🎲 選擇要擲骰的角色：", view=view, ephemeral=True)

class InitEditButton(Button):
    """編輯先攻按鈕"""
    def __init__(self, ctx):
        super().__init__(label="✏️ 編輯先攻", style=discord.ButtonStyle.secondary, row=2)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import get_entry_names, get_selected_character
        from views import InitCharacterSelectView, InitEditInitiativeModal
        
        channel_id = self.ctx.channel.id
        selected = get_selected_character(channel_id)
        
        if selected:
            modal = InitEditInitiativeModal(self.ctx, selected)
            await interaction.response.send_modal(modal)
            return
            
        names = get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "initiative")
        await interaction.response.send_message("✏️ 選擇要編輯先攻的角色：", view=view, ephemeral=True)

class RerollAllInitiativeButton(Button):
    """全員重骰先攻按鈕"""
    def __init__(self, ctx):
        super().__init__(label="🔄 全員重骰先攻", style=discord.ButtonStyle.danger, row=4)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from initiative_utils import reroll_all_initiative, get_tracker_display
        from views import InitiativeTrackerView
        
        channel_id = self.ctx.channel.id
        results = reroll_all_initiative(channel_id)
        
        # 顯示結果摘要
        summary = "🎲 **全員重骰結果**:\n"
        for name, old, new, detail in results:
            summary += f"**{name}**: {old} → **{new}** ({detail})\n"
        
        if len(summary) > 2000:
            summary = summary[:1997] + "..."
            
        await interaction.followup.send(summary)
        
        # 刷新先攻表
        display = get_tracker_display(channel_id)
        view = InitiativeTrackerView(self.ctx)
        
        # 嘗試更新原訊息
        if hasattr(interaction.message, "edit"):
            # 如果是從先攻表按鈕觸發（通常不會，因為這是在常用骰區），但如果是
            # 我們需要找到先攻表的訊息。
            # 這裡簡單發送新訊息或不做動作，因為 reroll_all_initiative 已經儲存了
            # 但使用者需要看到更新後的表。
            
            # 從 shared_state 獲取先攻表訊息引用
            import shared_state
            msg_refs = shared_state.initiative_messages.get(str(channel_id), {})
            tracker_msg = msg_refs.get("tracker_msg")
            
            if tracker_msg:
                try:
                    await tracker_msg.edit(content=display, view=view)
                except:
                    # 如果編輯失敗，發送新的
                    tracker_msg = await self.ctx.send(display, view=view)
                    shared_state.initiative_messages[str(channel_id)]["tracker_msg"] = tracker_msg
            else:
                tracker_msg = await self.ctx.send(display, view=view)
                if str(channel_id) not in shared_state.initiative_messages:
                    shared_state.initiative_messages[str(channel_id)] = {}
                shared_state.initiative_messages[str(channel_id)]["tracker_msg"] = tracker_msg

class QuickDiceButton(Button):
    """快速擲骰按鈕 (常用骰快捷鍵)"""
    def __init__(self, ctx, char_name, dice_name, formula):
        label = f"{char_name}: {dice_name}"
        if len(label) > 80:
            label = label[:77] + "..."
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.ctx = ctx
        self.char_name = char_name
        self.dice_name = dice_name
        self.formula = formula
    
    async def callback(self, interaction: discord.Interaction):
        from dice_utils import parse_and_roll, DiceParseError, try_coc_roll
        
        # 嘗試 CoC 擲骰
        coc_result = try_coc_roll(self.formula)
        if coc_result:
            if coc_result.startswith("❌"):
                await interaction.response.send_message(coc_result, ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"🎲 **{self.char_name}** 擲 **{self.dice_name}**\n{coc_result}"
                )
            return
        
        try:
            result, dice_rolls = parse_and_roll(self.formula)
            
            # 生成擲骰詳情
            if dice_rolls:
                rolls_str = ", ".join(
                    f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                    for d in dice_rolls
                )
                roll_detail = f"{rolls_str} = {result}"
            else:
                roll_detail = str(result)
            
            await interaction.response.send_message(
                f"🎲 **{self.char_name}** 擲 **{self.dice_name}** ({self.formula})\n"
                f"結果: {roll_detail}"
            )
            
        except DiceParseError as e:
            await interaction.response.send_message(f"❌ 公式錯誤: {e}", ephemeral=True)

class InitRemoveSelectButton(Button):
    """移除特定角色按鈕"""
    def __init__(self, name, ctx):
        super().__init__(label=name, style=discord.ButtonStyle.danger)
        self.name = name
        self.ctx = ctx
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from initiative_utils import remove_entry
        from views import refresh_tracker_view
        
        channel_id = self.ctx.channel.id
        success = remove_entry(channel_id, self.name)
        
        if success:
            await interaction.followup.send(f"✅ 已移除 **{self.name}**", ephemeral=True)
            await refresh_tracker_view(self.ctx)
            
            # 刪除選擇訊息
            await interaction.message.delete()
        else:
            await interaction.followup.send(f"❌ 找不到 **{self.name}**", ephemeral=True)
