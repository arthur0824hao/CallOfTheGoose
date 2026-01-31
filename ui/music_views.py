import discord
from discord.ui import View
import math
from utils.music import (load_musicsheet, save_musicsheet, find_downloaded_file, 
                         download_song, play_next, remove_song, log_message, debug_log)
from ui.music_buttons import (NextSongButton, PrevSongButton, PauseResumeButton, PlaybackModeButton,
                     QueueControlButton, QueuePageButton, QueueClearButton, PlaySelectionButton,
                     QueueRemoveButton, SearchButton)
import utils.shared_state as shared_state

QUEUE_PAGE_SIZE = 10

class QueuePaginationView(View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.setup_ui()
    def setup_ui(self):
        musicsheet_data = load_musicsheet()
        songs = musicsheet_data["songs"]
        total_pages = max(1, math.ceil(len(songs) / QUEUE_PAGE_SIZE))
        if total_pages <= 5:
            for page in range(1, total_pages + 1):
                self.add_item(QueuePageButton(str(page), self.ctx, page))
        else:
            pass
        self.add_item(QueueControlButton("🎵 播放", "play", self.ctx))
        self.add_item(QueueControlButton("🗑️ 移除", "remove", self.ctx))
        self.add_item(QueueControlButton("⏭️ 下一首", "next", self.ctx))
        self.add_item(QueueClearButton(self.ctx))
        playback_btn = PlaybackModeButton(self.ctx)
        modes = ["循環播放清單", "單曲循環", "隨機播放", "播完後待機"]
        current_mode = shared_state.playback_mode
        if current_mode in modes:
            playback_btn.current_mode = modes.index(current_mode)
            playback_btn.label = f"🔄 播放模式：{current_mode}"
        self.add_item(playback_btn)
    def get_queue_text(self):
        musicsheet_data = load_musicsheet()
        songs = musicsheet_data["songs"]
        total_pages = max(1, math.ceil(len(songs) / QUEUE_PAGE_SIZE))
        if shared_state.current_page > total_pages:
            shared_state.current_page = 1
        start = (shared_state.current_page - 1) * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, len(songs))
        queue_slice = songs[start:end]
        queue_text = f"📜 **播放清單 (第 {shared_state.current_page} 頁 / {total_pages} 頁)**\n"
        for song in queue_slice:
            prefix = "🎵 " if song.get("is_playing") else ""
            queue_text += f"{prefix}{song['index']}. {song['title']}\n"
        queue_text += f"\n🔄 播放模式：**{shared_state.playback_mode}**"
        return queue_text

class SearchView(View):
    def __init__(self, ctx, results):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.results = results
        for i, entry in enumerate(results[:10]):
            self.add_item(SearchButton(entry, ctx))

class PlaySelectionView(View):
    def __init__(self, ctx, songs):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.songs = songs
        for i, song in enumerate(songs[:10]):
            button_number = int(song["index"].split(".")[1])
            self.add_item(PlaySelectionButton(button_number, song, ctx))

class NowPlayingView(View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.add_item(PrevSongButton(ctx))
        self.add_item(PauseResumeButton(ctx))
        self.add_item(NextSongButton(ctx))
        self.add_item(PlaybackModeButton(ctx))

class QueueRemoveView(View):
    def __init__(self, ctx, page=1):
        super().__init__(timeout=60)
        self.ctx = ctx
        musicsheet_data = load_musicsheet()
        total_songs = len(musicsheet_data["songs"])
        start = (page - 1) * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, total_songs)
        for i in range(start, end):
            button_number = i - start + 1
            self.add_item(QueueRemoveButton(button_number, ctx, page))

class ConfirmClearQueueView(View):
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.add_item(ConfirmClearButton(ctx))
        self.add_item(CancelClearButton())

class ConfirmClearButton(discord.ui.Button):
    def __init__(self, ctx):
        super().__init__(label="確認清空", style=discord.ButtonStyle.danger)
        self.ctx = ctx
    async def callback(self, interaction):
        import utils.shared_state as shared_state
        async with shared_state.music_lock:
            musicsheet_data = load_musicsheet()
            current_song = next((song for song in musicsheet_data["songs"] if song.get("is_playing")), None)
            if current_song:
                musicsheet_data["songs"] = [current_song]
            else:
                musicsheet_data["songs"] = []
            for i, song in enumerate(musicsheet_data["songs"]):
                song["index"] = f"1.{i+1}"
            save_musicsheet(musicsheet_data)
        await interaction.response.send_message("✅ 播放清單已清空！", ephemeral=True)
        
        view = QueuePaginationView(self.ctx)
        content = view.get_queue_text()
        await interaction.message.edit(content=content, view=view)

class CancelClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="取消", style=discord.ButtonStyle.secondary)
    async def callback(self, interaction):
        await interaction.response.send_message("✅ 已取消清空播放清單", ephemeral=True)

