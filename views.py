import discord
from discord.ui import View
import math
from music_utils import (load_musicsheet, save_musicsheet, find_downloaded_file, 
                         download_song, play_next, remove_song, log_message, debug_log)
from buttons import (NextSongButton, PrevSongButton, PauseResumeButton, PlaybackModeButton,
                     QueueControlButton, QueuePageButton, QueueClearButton, PlaySelectionButton,
                     QueueRemoveButton, SearchButton)
import shared_state

# 全局常量
QUEUE_PAGE_SIZE = 10

class QueuePaginationView(View):
    """播放清單分頁視圖"""
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.setup_ui()

    def setup_ui(self):
        """設置 UI 元素"""
        # 讀取 `musicsheet.json`
        musicsheet_data = load_musicsheet()
        songs = musicsheet_data["songs"]
        total_pages = max(1, math.ceil(len(songs) / QUEUE_PAGE_SIZE))

        # 頁碼按鈕
        # 如果總頁數超過 5 頁，則顯示前 2 頁、當前頁、後 2 頁
        if total_pages <= 5:
            for page in range(1, total_pages + 1):
                self.add_item(QueuePageButton(str(page), self.ctx, page))
        else:
            # ...existing page button logic...
            pass

        # 功能控制按鈕區塊
        self.add_item(QueueControlButton("🎵 播放", "play", self.ctx))
        self.add_item(QueueControlButton("🗑️ 移除", "remove", self.ctx))
        self.add_item(QueueControlButton("⏭️ 下一首", "next", self.ctx))
        self.add_item(QueueClearButton(self.ctx))
        
        # 播放模式按鈕 - 讀取當前模式並更新標籤
        playback_btn = PlaybackModeButton(self.ctx)
        modes = ["循環播放清單", "單曲循環", "隨機播放", "播完後待機"]
        current_mode = shared_state.playback_mode
        if current_mode in modes:
            playback_btn.current_mode = modes.index(current_mode)
            playback_btn.label = f"🔄 播放模式：{current_mode}"
        self.add_item(playback_btn)

    def get_queue_text(self):
        """產生播放清單文字"""
        musicsheet_data = load_musicsheet()
        songs = musicsheet_data["songs"]
        total_pages = max(1, math.ceil(len(songs) / QUEUE_PAGE_SIZE))

        # 確保頁數不超出範圍
        if shared_state.current_page > total_pages:
            shared_state.current_page = 1

        start = (shared_state.current_page - 1) * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, len(songs))
        queue_slice = songs[start:end]

        # 產生顯示文字
        queue_text = f"📜 **播放清單 (第 {shared_state.current_page} 頁 / {total_pages} 頁)**\n"
        for song in queue_slice:
            # 標記當前播放的歌曲
            prefix = "🎵 " if song.get("is_playing") else ""
            queue_text += f"{prefix}{song['index']}. {song['title']}\n"

        # 添加播放模式提示
        queue_text += f"\n🔄 播放模式：**{shared_state.playback_mode}**"

        return queue_text

class SearchView(View):
    """YouTube 搜尋結果視圖"""
    def __init__(self, ctx, results):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.results = results

        # 添加結果按鈕
        for i, entry in enumerate(results[:10]):  # 最多顯示 10 個結果
            self.add_item(SearchButton(entry, ctx))

class PlaySelectionView(View):
    """選擇播放哪首歌曲的視圖"""
    def __init__(self, ctx, songs):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.songs = songs

        # 添加歌曲按鈕
        for i, song in enumerate(songs[:10]):  # 最多顯示 10 個結果
            button_number = int(song["index"].split(".")[1])  # 使用 b 作為按鈕編號
            self.add_item(PlaySelectionButton(button_number, song, ctx))

class NowPlayingView(View):
    """目前播放的歌曲控制視圖"""
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx

        # 添加控制按鈕
        self.add_item(PrevSongButton(ctx))
        self.add_item(PauseResumeButton(ctx))
        self.add_item(NextSongButton(ctx))
        self.add_item(PlaybackModeButton(ctx))

class QueueRemoveView(View):
    """移除播放清單中歌曲的視圖"""
    def __init__(self, ctx, page=1):
        super().__init__(timeout=60)
        self.ctx = ctx

        # 讀取 `musicsheet.json`
        musicsheet_data = load_musicsheet()
        total_songs = len(musicsheet_data["songs"])
        start = (page - 1) * QUEUE_PAGE_SIZE
        end = min(start + QUEUE_PAGE_SIZE, total_songs)

        # 添加移除按鈕
        for i in range(start, end):
            button_number = i - start + 1  # 計算按鈕號碼 (1-10)
            self.add_item(QueueRemoveButton(button_number, ctx, page))

class ConfirmClearQueueView(View):
    """確認清空播放清單的視圖"""
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        
        # 添加確認和取消按鈕
        self.add_item(ConfirmClearButton(ctx))
        self.add_item(CancelClearButton())

class ConfirmClearButton(discord.ui.Button):
    """確認清空播放清單按鈕"""
    def __init__(self, ctx):
        super().__init__(label="確認清空", style=discord.ButtonStyle.danger)
        self.ctx = ctx
        
    async def callback(self, interaction):
        # 讀取現有歌曲，保留正在播放的歌曲
        musicsheet_data = load_musicsheet()
        current_song = next((song for song in musicsheet_data["songs"] if song.get("is_playing")), None)
        
        # 清空播放清單，只保留當前播放歌曲
        if current_song:
            musicsheet_data["songs"] = [current_song]
        else:
            musicsheet_data["songs"] = []
            
        # 重組索引
        for i, song in enumerate(musicsheet_data["songs"]):
            song["index"] = f"1.{i+1}"
            
        save_musicsheet(musicsheet_data)
        
        await interaction.response.send_message("✅ 播放清單已清空！", ephemeral=True)
        
        # 重新顯示播放清單
        list_cmd = self.ctx.bot.get_command("list")
        if list_cmd:
            await self.ctx.invoke(list_cmd)

class CancelClearButton(discord.ui.Button):
    """取消清空播放清單按鈕"""
    def __init__(self):
        super().__init__(label="取消", style=discord.ButtonStyle.secondary)
        
    async def callback(self, interaction):
        await interaction.response.send_message("✅ 已取消清空播放清單", ephemeral=True)


# ============================================
# 先攻表視圖與 Modal
# ============================================

class InitiativeTrackerView(View):
    """先攻表主視圖"""
    def __init__(self, ctx):
        super().__init__(timeout=None)  # 不會超時
        self.ctx = ctx
        self.setup_ui()

    def setup_ui(self):
        from buttons import (InitAddButton, InitNextButton, InitRemoveButton, 
                            InitEndButton, InitStatsButton, InitHPButton,
                            InitStatusButton, InitResetButton,
                            InitFavDiceAddButton, InitFavDiceRollButton, InitEditButton)
        
        # 第一排：主要操作
        self.add_item(InitAddButton(self.ctx))
        self.add_item(InitNextButton(self.ctx))
        self.add_item(InitRemoveButton(self.ctx))
        self.add_item(InitResetButton(self.ctx))
        self.add_item(InitEndButton(self.ctx))
        
        # 第二排：數值管理
        self.add_item(InitStatsButton(self.ctx))
        self.add_item(InitHPButton(self.ctx))
        self.add_item(InitStatusButton(self.ctx))
        self.add_item(InitFavDiceAddButton(self.ctx))
        self.add_item(InitFavDiceRollButton(self.ctx))
        
        # 第三排：編輯
        self.add_item(InitEditButton(self.ctx))


class InitAddModal(discord.ui.Modal, title="新增角色"):
    """新增角色 Modal"""
    
    formula = discord.ui.TextInput(
        label="骰子公式",
        placeholder="例如: 1d20+5 或直接輸入數字",
        required=True,
        max_length=50
    )
    
    name = discord.ui.TextInput(
        label="角色名稱",
        placeholder="例如: 戰士、哥布林A",
        required=True,
        max_length=30
    )
    
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import add_entry, add_entry_with_roll, get_tracker_display
        
        channel_id = self.ctx.channel.id
        formula_str = self.formula.value.strip()
        name_str = self.name.value.strip()
        
        # 嘗試直接解析為數字
        try:
            initiative_value = int(formula_str)
            success = add_entry(channel_id, name_str, initiative_value)
            if success:
                await interaction.response.send_message(
                    f"✅ 已新增 **{name_str}** (先攻: {initiative_value})",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 角色 **{name_str}** 已存在！",
                    ephemeral=True
                )
        except ValueError:
            # 當作骰子公式處理
            success, result, roll_detail = add_entry_with_roll(channel_id, formula_str, name_str)
            if success:
                await interaction.response.send_message(
                    f"🎲 擲骰: {formula_str} → {roll_detail}\n✅ 已新增 **{name_str}** (先攻: {result})",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ {result}", ephemeral=True)
        
        # 更新先攻表顯示
        view = InitiativeTrackerView(self.ctx)
        display = get_tracker_display(channel_id)
        await self.ctx.send(display, view=view)


class InitStatsModal(discord.ui.Modal, title="設定角色數值"):
    """設定角色數值 Modal"""
    
    name = discord.ui.TextInput(
        label="角色名稱",
        placeholder="輸入先攻表中的角色名稱",
        required=True,
        max_length=30
    )
    
    hp = discord.ui.TextInput(
        label="HP (生命值)",
        placeholder="例如: 45",
        required=False,
        max_length=10
    )
    
    elements = discord.ui.TextInput(
        label="剩餘元素",
        placeholder="例如: 3",
        required=False,
        max_length=10
    )
    
    atk = discord.ui.TextInput(
        label="攻擊等級",
        placeholder="例如: 5",
        required=False,
        max_length=10
    )
    
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        # 動態添加防禦等級欄位
        self.def_input = discord.ui.TextInput(
            label="防禦等級",
            placeholder="例如: 3",
            required=False,
            max_length=10
        )
        self.add_item(self.def_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import set_stats, get_entry, get_tracker_display
        
        channel_id = self.ctx.channel.id
        name_str = self.name.value.strip()
        
        # 檢查角色是否存在
        entry = get_entry(channel_id, name_str)
        if not entry:
            await interaction.response.send_message(f"❌ 找不到角色 **{name_str}**", ephemeral=True)
            return
        
        # 解析數值 (若未輸入：若已有值則不變(None)，若無值則設為0)
        hp_val = int(self.hp.value) if self.hp.value.strip() else (0 if "hp" not in entry else None)
        elements_val = int(self.elements.value) if self.elements.value.strip() else (0 if "elements" not in entry else None)
        atk_val = int(self.atk.value) if self.atk.value.strip() else (0 if "atk" not in entry else None)
        def_val = int(self.def_input.value) if self.def_input.value.strip() else (0 if "def_" not in entry else None)
        
        set_stats(channel_id, name_str, hp=hp_val, elements=elements_val, atk=atk_val, def_=def_val)
        
        # 簡潔回應，不重複發送整個先攻表
        await interaction.response.send_message("✅ 數值已更新", ephemeral=True)


class InitRemoveView(View):
    """移除角色選擇視圖"""
    def __init__(self, ctx, names: list):
        super().__init__(timeout=60)
        self.ctx = ctx
        
        from buttons import InitRemoveSelectButton, InitAddButton
        
        if not names:
            self.add_item(InitAddButton(ctx))
            return

        # 為每個角色添加一個按鈕 (最多 25 個)
        for name in names[:25]:
            self.add_item(InitRemoveSelectButton(name, ctx))


class InitEndConfirmView(View):
    """結束戰鬥確認視圖"""
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        
        self.add_item(InitEndConfirmButton(ctx))
        self.add_item(InitEndCancelButton())


class InitEndConfirmButton(discord.ui.Button):
    """確認結束戰鬥按鈕"""
    def __init__(self, ctx):
        super().__init__(label="確認結束", style=discord.ButtonStyle.danger)
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import end_combat
        
        channel_id = self.ctx.channel.id
        summary = end_combat(channel_id)
        
        # 生成戰鬥統計
        msg = f"🏁 **戰鬥結束！**\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"📊 總回合數: {summary['total_rounds']}\n"
        msg += f"👥 參戰角色: {summary['total_characters']}\n"
        
        if summary['survivors']:
            msg += f"✨ 存活者: {', '.join(summary['survivors'])}\n"
        
        await interaction.response.send_message(msg)


class InitEndCancelButton(discord.ui.Button):
    """取消結束戰鬥按鈕"""
    def __init__(self):
        super().__init__(label="取消", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ 已取消", ephemeral=True)


# ============================================
# 角色選擇下拉式選單
# ============================================

class InitCharacterSelectView(View):
    """角色選擇視圖 (含下拉式選單)"""
    def __init__(self, ctx, names: list, action_type: str):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.action_type = action_type
        self.add_item(InitCharacterSelect(ctx, names, action_type))


class InitCharacterSelect(discord.ui.Select):
    """角色選擇下拉式選單"""
    def __init__(self, ctx, names: list, action_type: str):
        self.ctx = ctx
        self.action_type = action_type
        
        # 建立選項 - 首先加入新增角色選項
        options = [
            discord.SelectOption(label="➕ 新增角色", value="__NEW__", description="新增一個角色")
        ]
        
        # 加入現有角色
        for name in names[:24]:  # 保留一個給新增選項
            options.append(discord.SelectOption(label=name, value=name))
        
        super().__init__(
            placeholder="選擇角色...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_name = self.values[0]
        
        # 如果選擇新增角色
        if selected_name == "__NEW__":
            modal = InitQuickAddCharacterModal(self.ctx, self.action_type)
            await interaction.response.send_modal(modal)
            return
        
        if self.action_type == "hp":
            modal = InitHPModalWithName(self.ctx, selected_name)
            await interaction.response.send_modal(modal)
        elif self.action_type == "elements":
            modal = InitElementsModalWithName(self.ctx, selected_name)
            await interaction.response.send_modal(modal)
        elif self.action_type == "status":
            modal = InitStatusModalWithName(self.ctx, selected_name)
            await interaction.response.send_modal(modal)
        elif self.action_type == "stats":
            modal = InitStatsModalWithName(self.ctx, selected_name)
            await interaction.response.send_modal(modal)
        elif self.action_type == "initiative":
            modal = InitEditInitiativeModal(self.ctx, selected_name)
            await interaction.response.send_modal(modal)
        elif self.action_type == "fav_dice_add":
            modal = InitAddFavDiceModal(self.ctx, selected_name)
            await interaction.response.send_modal(modal)
        elif self.action_type == "fav_dice_roll":
            # 顯示該角色的常用骰選擇
            from initiative_utils import get_favorite_dice_names
            channel_id = self.ctx.channel.id
            dice_names = get_favorite_dice_names(channel_id, selected_name)
            if not dice_names:
                await interaction.response.send_message(f"❌ **{selected_name}** 沒有常用骰！", ephemeral=True)
                return
            view = InitFavDiceRollSelectView(self.ctx, selected_name, dice_names)
            await interaction.response.send_message(f"🎲 選擇 **{selected_name}** 的常用骰：", view=view, ephemeral=True)
        elif self.action_type == "status_add":
            modal = InitStatusAddModal(self.ctx, selected_name)
            await interaction.response.send_modal(modal)


class InitHPModalWithName(discord.ui.Modal):
    """調整 HP Modal (已選擇角色)"""
    
    delta = discord.ui.TextInput(
        label="HP 變化量",
        placeholder="正數增加，負數減少 (例如: -10)",
        required=True,
        max_length=10
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__(title=f"調整 {character_name} 的 HP")
        self.ctx = ctx
        self.character_name = character_name
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import modify_hp, get_tracker_display
        
        channel_id = self.ctx.channel.id
        try:
            delta_val = int(self.delta.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ HP 變化量必須是數字！", ephemeral=True)
            return
        
        success, result = modify_hp(channel_id, self.character_name, delta_val)
        
        if success:
            emoji = "💚" if delta_val > 0 else "💔"
            await interaction.response.send_message(
                f"{emoji} **{self.character_name}** HP {'+' if delta_val >= 0 else ''}{delta_val} → **{result}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ {result}", ephemeral=True)


class InitElementsModalWithName(discord.ui.Modal):
    """調整元素 Modal (已選擇角色)"""
    
    delta = discord.ui.TextInput(
        label="元素變化量",
        placeholder="正數增加，負數減少 (例如: -1)",
        required=True,
        max_length=10
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__(title=f"調整 {character_name} 的元素")
        self.ctx = ctx
        self.character_name = character_name
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import modify_elements, get_tracker_display
        
        channel_id = self.ctx.channel.id
        try:
            delta_val = int(self.delta.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 元素變化量必須是數字！", ephemeral=True)
            return
        
        success, result = modify_elements(channel_id, self.character_name, delta_val)
        
        if success:
            await interaction.response.send_message(
                f"✨ **{self.character_name}** 元素 {'+' if delta_val >= 0 else ''}{delta_val} → **{result}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ {result}", ephemeral=True)


class InitStatusModalWithName(discord.ui.Modal):
    """狀態效果 Modal (已選擇角色)"""
    
    status = discord.ui.TextInput(
        label="狀態名稱",
        placeholder="例如: 專注、中毒、倒地",
        required=True,
        max_length=20
    )
    
    action = discord.ui.TextInput(
        label="操作",
        placeholder="輸入 '新增' 或 '移除'",
        required=True,
        max_length=10,
        default="新增"
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__(title=f"管理 {character_name} 的狀態")
        self.ctx = ctx
        self.character_name = character_name
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import add_status, remove_status, get_tracker_display
        
        channel_id = self.ctx.channel.id
        status_str = self.status.value.strip()
        action_str = self.action.value.strip()
        
        if action_str in ["新增", "add", "+"]:
            success = add_status(channel_id, self.character_name, status_str, "")
            if success:
                await interaction.response.send_message(
                    f"✨ **{self.character_name}** 獲得狀態 **{status_str}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ 找不到角色", ephemeral=True)
        
        elif action_str in ["移除", "remove", "-"]:
            success = remove_status(channel_id, self.character_name, status_str)
            if success:
                await interaction.response.send_message(
                    f"⚪ **{self.character_name}** 移除狀態 **{status_str}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ 找不到角色或狀態", ephemeral=True)
        
        else:
            await interaction.response.send_message("❌ 操作必須是 '新增' 或 '移除'", ephemeral=True)


class InitStatsModalWithName(discord.ui.Modal):
    """設定數值 Modal (已選擇角色)"""
    
    hp = discord.ui.TextInput(
        label="HP (生命值)",
        placeholder="例如: 45",
        required=False,
        max_length=10
    )
    
    elements = discord.ui.TextInput(
        label="剩餘元素",
        placeholder="例如: 3",
        required=False,
        max_length=10
    )
    
    atk = discord.ui.TextInput(
        label="攻擊等級",
        placeholder="例如: 5",
        required=False,
        max_length=10
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__(title=f"設定 {character_name} 的數值")
        self.ctx = ctx
        self.character_name = character_name
        # 動態添加防禦等級欄位
        self.def_input = discord.ui.TextInput(
            label="防禦等級",
            placeholder="例如: 3",
            required=False,
            max_length=10
        )
        self.add_item(self.def_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import set_stats, get_tracker_display
        
        channel_id = self.ctx.channel.id
        # 解析數值
        hp_val = int(self.hp.value) if self.hp.value.strip() else None
        elements_val = int(self.elements.value) if self.elements.value.strip() else None
        atk_val = int(self.atk.value) if self.atk.value.strip() else None
        def_val = int(self.def_input.value) if self.def_input.value.strip() else None
        
        success = set_stats(channel_id, self.character_name, hp=hp_val, elements=elements_val, atk=atk_val, def_=def_val)
        
        if success:
            # 簡潔回應
            await interaction.response.send_message("✅ 數值已更新", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 找不到角色", ephemeral=True)


# 保留舊的 Modal 類別以供向後相容 (文字指令用)
class InitHPModal(discord.ui.Modal, title="調整 HP"):
    """調整 HP Modal (文字輸入版)"""
    
    name = discord.ui.TextInput(
        label="角色名稱",
        placeholder="輸入先攻表中的角色名稱",
        required=True,
        max_length=30
    )
    
    delta = discord.ui.TextInput(
        label="HP 變化量",
        placeholder="正數增加，負數減少 (例如: -10)",
        required=True,
        max_length=10
    )
    
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import modify_hp, get_tracker_display
        
        channel_id = self.ctx.channel.id
        name_str = self.name.value.strip()
        
        try:
            delta_val = int(self.delta.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ HP 變化量必須是數字！", ephemeral=True)
            return
        
        success, result = modify_hp(channel_id, name_str, delta_val)
        
        if success:
            emoji = "💚" if delta_val > 0 else "💔"
            await interaction.response.send_message(
                f"{emoji} **{name_str}** HP {'+' if delta_val >= 0 else ''}{delta_val} → **{result}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ {result}", ephemeral=True)


class InitElementsModal(discord.ui.Modal, title="調整剩餘元素"):
    """調整元素 Modal (文字輸入版)"""
    
    name = discord.ui.TextInput(
        label="角色名稱",
        placeholder="輸入先攻表中的角色名稱",
        required=True,
        max_length=30
    )
    
    delta = discord.ui.TextInput(
        label="元素變化量",
        placeholder="正數增加，負數減少 (例如: -1)",
        required=True,
        max_length=10
    )
    
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import modify_elements, get_tracker_display
        
        channel_id = self.ctx.channel.id
        name_str = self.name.value.strip()
        
        try:
            delta_val = int(self.delta.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 元素變化量必須是數字！", ephemeral=True)
            return
        
        success, result = modify_elements(channel_id, name_str, delta_val)
        
        if success:
            await interaction.response.send_message(
                f"✨ **{name_str}** 元素 {'+' if delta_val >= 0 else ''}{delta_val} → **{result}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ {result}", ephemeral=True)


class InitStatusModal(discord.ui.Modal, title="管理狀態效果"):
    """狀態效果 Modal (文字輸入版)"""
    
    name = discord.ui.TextInput(
        label="角色名稱",
        placeholder="輸入先攻表中的角色名稱",
        required=True,
        max_length=30
    )
    
    status = discord.ui.TextInput(
        label="狀態名稱",
        placeholder="例如: 專注、中毒、倒地",
        required=True,
        max_length=20
    )
    
    action = discord.ui.TextInput(
        label="操作",
        placeholder="輸入 '新增' 或 '移除'",
        required=True,
        max_length=10,
        default="新增"
    )
    
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import add_status, remove_status, get_tracker_display
        
        channel_id = self.ctx.channel.id
        name_str = self.name.value.strip()
        status_str = self.status.value.strip()
        action_str = self.action.value.strip()
        
        if action_str in ["新增", "add", "+"]:
            success = add_status(channel_id, name_str, status_str, "")
            if success:
                await interaction.response.send_message(
                    f"✨ **{name_str}** 獲得狀態 **{status_str}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ 找不到 **{name_str}**", ephemeral=True)
        
        elif action_str in ["移除", "remove", "-"]:
            success = remove_status(channel_id, name_str, status_str)
            if success:
                await interaction.response.send_message(
                    f"⚪ **{name_str}** 移除狀態 **{status_str}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ 找不到角色或狀態", ephemeral=True)
        
        else:
            await interaction.response.send_message("❌ 操作必須是 '新增' 或 '移除'", ephemeral=True)


# ============================================
# 狀態操作選擇 (新增/移除/改變)
# ============================================

class InitStatusActionSelectView(View):
    """狀態操作選擇視圖"""
    def __init__(self, ctx, names: list):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.names = names
        self.add_item(InitStatusActionSelect(ctx, names))


class InitStatusActionSelect(discord.ui.Select):
    """狀態操作選擇下拉選單"""
    def __init__(self, ctx, names: list):
        self.ctx = ctx
        self.names = names
        
        options = [
            discord.SelectOption(label="➕ 新增狀態", value="add", description="新增新的狀態效果"),
            discord.SelectOption(label="✏️ 改變狀態", value="change", description="修改已有狀態的值"),
            discord.SelectOption(label="🗑️ 移除狀態", value="remove", description="移除已有的狀態效果"),
        ]
        
        super().__init__(
            placeholder="選擇操作...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        
        if action == "add":
            # 新增：先選角色，再輸入狀態鍵值對
            view = InitCharacterSelectView(self.ctx, self.names, "status_add")
            await interaction.response.send_message("➕ 選擇要新增狀態的角色：", view=view, ephemeral=True)
        elif action == "change":
            # 改變：先選角色，再選狀態，再輸入新值
            view = InitStatusCharacterSelectView(self.ctx, self.names, "change")
            await interaction.response.send_message("✏️ 選擇要改變狀態的角色：", view=view, ephemeral=True)
        elif action == "remove":
            # 移除：先選角色，再選狀態
            view = InitStatusCharacterSelectView(self.ctx, self.names, "remove")
            await interaction.response.send_message("🗑️ 選擇要移除狀態的角色：", view=view, ephemeral=True)


class InitStatusCharacterSelectView(View):
    """狀態操作角色選擇視圖 (用於改變/移除)"""
    def __init__(self, ctx, names: list, mode: str):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.mode = mode
        self.add_item(InitStatusCharacterSelect(ctx, names, mode))


class InitStatusCharacterSelect(discord.ui.Select):
    """狀態操作角色選擇"""
    def __init__(self, ctx, names: list, mode: str):
        self.ctx = ctx
        self.mode = mode
        
        # 加入新增角色選項
        options = [
            discord.SelectOption(label="➕ 新增角色", value="__NEW__", description="新增一個角色")
        ]
        
        for name in names[:24]:
            options.append(discord.SelectOption(label=name, value=name))
        
        super().__init__(
            placeholder="選擇角色...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_name = self.values[0]
        
        # 如果選擇新增角色
        if selected_name == "__NEW__":
            modal = InitQuickAddCharacterModal(self.ctx, f"status_{self.mode}")
            await interaction.response.send_modal(modal)
            return
        
        from initiative_utils import get_status_names
        
        channel_id = self.ctx.channel.id
        status_names = get_status_names(channel_id, selected_name)
        
        if not status_names:
            await interaction.response.send_message(f"❌ **{selected_name}** 沒有狀態效果！", ephemeral=True)
            return
        
        if self.mode == "change":
            view = InitStatusSelectView(self.ctx, selected_name, status_names, "change")
            await interaction.response.send_message(f"✏️ 選擇要改變的狀態：", view=view, ephemeral=True)
        elif self.mode == "remove":
            view = InitStatusSelectView(self.ctx, selected_name, status_names, "remove")
            await interaction.response.send_message(f"🗑️ 選擇要移除的狀態：", view=view, ephemeral=True)


class InitStatusSelectView(View):
    """狀態選擇視圖"""
    def __init__(self, ctx, character_name: str, status_names: list, mode: str):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.add_item(InitStatusSelect(ctx, character_name, status_names, mode))


class InitStatusSelect(discord.ui.Select):
    """狀態選擇下拉選單"""
    def __init__(self, ctx, character_name: str, status_names: list, mode: str):
        self.ctx = ctx
        self.character_name = character_name
        self.mode = mode
        
        options = [
            discord.SelectOption(label=name, value=name)
            for name in status_names[:25]
        ]
        
        super().__init__(
            placeholder="選擇狀態...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_status = self.values[0]
        
        if self.mode == "change":
            modal = InitStatusChangeModal(self.ctx, self.character_name, selected_status)
            await interaction.response.send_modal(modal)
        elif self.mode == "remove":
            from initiative_utils import remove_status, get_tracker_display
            
            channel_id = self.ctx.channel.id
            success = remove_status(channel_id, self.character_name, selected_status)
            if success:
                await interaction.response.send_message(
                    f"⚪ **{self.character_name}** 移除狀態 **{selected_status}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ 移除失敗", ephemeral=True)


class InitStatusChangeModal(discord.ui.Modal):
    """改變狀態值 Modal"""
    
    new_value = discord.ui.TextInput(
        label="新狀態值 (可輸入骰子公式)",
        placeholder="輸入新的狀態值或公式 (例如: 2d6、1d4+2)",
        required=True,
        max_length=50
    )
    
    def __init__(self, ctx, character_name: str, status_key: str):
        super().__init__(title=f"改變 {status_key} 的值")
        self.ctx = ctx
        self.character_name = character_name
        self.status_key = status_key
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import update_status, get_tracker_display
        from dice_utils import parse_and_roll, DiceParseError
        
        channel_id = self.ctx.channel.id
        input_val = self.new_value.value.strip()
        
        # 嘗試解析為骰子公式
        try:
            result, dice_rolls = parse_and_roll(input_val)
            if dice_rolls:
                rolls_str = ", ".join(
                    f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                    for d in dice_rolls
                )
                new_val = str(result)
                roll_msg = f"\n🎲 擲骰: {input_val} → {rolls_str} = {result}"
            else:
                new_val = input_val
                roll_msg = ""
        except DiceParseError:
            new_val = input_val
            roll_msg = ""
        
        success = update_status(channel_id, self.character_name, self.status_key, new_val)
        
        if success:
            await interaction.response.send_message(
                f"✅ **{self.character_name}** 狀態 **{self.status_key}** 更新為 **{new_val}**{roll_msg}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ 更新失敗", ephemeral=True)


class InitStatusAddModal(discord.ui.Modal, title="新增狀態"):
    """新增狀態 Modal (鍵值對)"""
    
    status_key = discord.ui.TextInput(
        label="狀態名稱",
        placeholder="例如: 專注、中毒、倒地",
        required=True,
        max_length=20
    )
    
    status_value = discord.ui.TextInput(
        label="狀態值 (可輸入骰子公式)",
        placeholder="例如: 2回合、1d4+2、進行中",
        required=True,
        max_length=50
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__()
        self.ctx = ctx
        self.character_name = character_name
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import add_status, get_tracker_display
        from dice_utils import parse_and_roll, DiceParseError
        
        channel_id = self.ctx.channel.id
        key = self.status_key.value.strip()
        input_val = self.status_value.value.strip()
        
        # 嘗試解析為骰子公式
        try:
            result, dice_rolls = parse_and_roll(input_val)
            if dice_rolls:
                rolls_str = ", ".join(
                    f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                    for d in dice_rolls
                )
                value = str(result)
                roll_msg = f"\n🎲 擲骰: {input_val} → {rolls_str} = {result}"
            else:
                value = input_val
                roll_msg = ""
        except DiceParseError:
            value = input_val
            roll_msg = ""
        
        success = add_status(channel_id, self.character_name, key, value)
        
        if success:
            await interaction.response.send_message(
                f"✨ **{self.character_name}** 獲得狀態 **{key}: {value}**{roll_msg}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ 新增失敗", ephemeral=True)





class InitFavDiceRollSelectView(View):
    """常用骰擲骰選擇視圖"""
    def __init__(self, ctx, character_name: str, dice_names: list):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.add_item(InitFavDiceRollSelect(ctx, character_name, dice_names))


class InitFavDiceRollSelect(discord.ui.Select):
    """常用骰擲骰選擇"""
    def __init__(self, ctx, character_name: str, dice_names: list):
        self.ctx = ctx
        self.character_name = character_name
        
        options = [
            discord.SelectOption(label=name, value=name)
            for name in dice_names[:25]
        ]
        
        super().__init__(
            placeholder="選擇常用骰...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        from initiative_utils import roll_favorite_dice
        
        channel_id = self.ctx.channel.id
        selected_dice = self.values[0]
        success, result, formula, roll_detail = roll_favorite_dice(channel_id, self.character_name, selected_dice)
        
        if success:
            await interaction.response.send_message(
                f"🎲 **{self.character_name}** 擲 **{selected_dice}** ({formula})\n"
                f"結果: {roll_detail}"
            )
        else:
            await interaction.response.send_message(f"❌ {result}", ephemeral=True)


class InitAddFavDiceModal(discord.ui.Modal, title="新增常用骰"):
    """新增常用骰 Modal"""
    
    dice_name = discord.ui.TextInput(
        label="常用骰名稱",
        placeholder="例如: 攻擊、傷害、技能",
        required=True,
        max_length=20
    )
    
    dice_formula = discord.ui.TextInput(
        label="骰子公式",
        placeholder="例如: 1d20+5、2d6+3",
        required=True,
        max_length=50
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__()
        self.ctx = ctx
        self.character_name = character_name
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import add_favorite_dice
        
        channel_id = self.ctx.channel.id
        name = self.dice_name.value.strip()
        formula = self.dice_formula.value.strip()
        
        success = add_favorite_dice(channel_id, self.character_name, name, formula)
        
        if success:
            await interaction.response.send_message(
                f"✅ **{self.character_name}** 新增常用骰 **{name}**: `{formula}`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ 新增失敗", ephemeral=True)


class InitEditInitiativeModal(discord.ui.Modal):
    """編輯先攻值 Modal"""
    
    new_initiative = discord.ui.TextInput(
        label="新先攻值",
        placeholder="輸入新的先攻數值",
        required=True,
        max_length=10
    )
    
    def __init__(self, ctx, character_name: str):
        super().__init__(title=f"編輯 {character_name} 的先攻")
        self.ctx = ctx
        self.character_name = character_name
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import set_initiative, get_tracker_display
        
        channel_id = self.ctx.channel.id
        try:
            new_val = int(self.new_initiative.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 先攻值必須是數字！", ephemeral=True)
            return
        
        success = set_initiative(channel_id, self.character_name, new_val)
        
        if success:
            await interaction.response.send_message(
                f"✅ **{self.character_name}** 先攻更新為 **{new_val}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ 更新失敗", ephemeral=True)


class InitQuickAddCharacterModal(discord.ui.Modal, title="快速新增角色"):
    """快速新增角色 Modal (僅輸入名字，所有數值預設為 0)"""
    
    name = discord.ui.TextInput(
        label="角色名稱",
        placeholder="輸入新角色的名稱",
        required=True,
        max_length=30
    )
    
    def __init__(self, ctx, next_action: str):
        super().__init__()
        self.ctx = ctx
        self.next_action = next_action  # 接下來要做的動作
    
    async def on_submit(self, interaction: discord.Interaction):
        from initiative_utils import add_entry, get_tracker_display
        
        channel_id = self.ctx.channel.id
        name_str = self.name.value.strip()
        
        # 新增角色，先攻值預設為 0
        success = add_entry(channel_id, name_str, 0)
        
        if success:
            await interaction.response.send_message(
                f"✅ 已新增角色 **{name_str}** (所有數值預設為 0)\n請重新點擊按鈕進行後續操作",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ 角色 **{name_str}** 已存在！",
                ephemeral=True
            )
