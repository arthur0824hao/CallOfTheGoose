import discord
from discord.ui import Button
import utils.shared_state as shared_state
# ============================================
# 先攻表按鈕
# ============================================


class InitAddButton(Button):
    def __init__(self, ctx):
        super().__init__(label="➕ 新增角色", style=discord.ButtonStyle.success, row=3)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from ui.init_views import InitAddModal

        modal = InitAddModal(self.ctx)
        await interaction.response.send_modal(modal)


class InitPrevButton(Button):
    def __init__(self, ctx):
        super().__init__(label="⏮ 上一位", style=discord.ButtonStyle.primary, row=1)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from utils.initiative import prev_turn
        from ui.init_views import refresh_tracker_view

        channel_id = self.ctx.channel.id
        name, current_round = await prev_turn(channel_id)

        if name:
            await refresh_tracker_view(self.ctx)
        else:
            await interaction.followup.send("❌ 先攻表是空的！", ephemeral=True)


class InitNextButton(Button):
    def __init__(self, ctx):
        super().__init__(label="⏭ 下一位", style=discord.ButtonStyle.primary, row=1)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from utils.initiative import (
            next_turn,
            get_tracker_display,
            save_tracker,
            get_tracker,
        )
        from ui.init_views import InitiativeTrackerView

        channel_id = self.ctx.channel.id
        name, new_round = await next_turn(channel_id)

        if name:
            if new_round:
                tracker = await get_tracker(channel_id)
                await interaction.followup.send(
                    f"🔄 **第 {tracker['current_round']} 回合開始！** 輪到 **{name}** 行動"
                )

            # 刷新顯示
            display = await get_tracker_display(channel_id)
            view = InitiativeTrackerView(self.ctx)
            await interaction.message.edit(content=display, view=view)
        else:
            await interaction.followup.send("❌ 先攻表是空的！", ephemeral=True)


class InitRemoveButton(Button):
    def __init__(self, ctx):
        super().__init__(label="🗑️ 移除角色", style=discord.ButtonStyle.danger, row=3)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_entry_names
        from ui.init_views import InitRemoveView

        channel_id = self.ctx.channel.id
        names = await get_entry_names(channel_id)

        if not names:
            await interaction.response.send_message("❌ 先攻表是空的！", ephemeral=True)
            return

        view = InitRemoveView(self.ctx, names)
        await interaction.response.send_message(
            "🗑️ 選擇要移除的角色：", view=view, ephemeral=True
        )


class InitResetButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="🔄 重置回合", style=discord.ButtonStyle.secondary, row=1
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from utils.initiative import reset_tracker, get_tracker_display
        from ui.init_views import InitiativeTrackerView

        channel_id = self.ctx.channel.id
        await reset_tracker(channel_id)

        display = await get_tracker_display(channel_id)
        view = InitiativeTrackerView(self.ctx)
        await interaction.message.edit(content=display, view=view)
        await interaction.followup.send("🔄 已重置回合數", ephemeral=True)


class InitEndButton(Button):
    def __init__(self, ctx):
        super().__init__(label="🏁 結束戰鬥", style=discord.ButtonStyle.danger, row=1)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from ui.init_views import InitEndConfirmView

        view = InitEndConfirmView(self.ctx)
        await interaction.response.send_message(
            "⚠️ 確定要結束戰鬥並清空先攻表嗎？", view=view, ephemeral=True
        )


class InitStatsButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="📊 設定數值", style=discord.ButtonStyle.secondary, row=2
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_entry_names, get_selected_character
        from ui.init_views import InitCharacterSelectView, InitStatsModalWithName

        channel_id = self.ctx.channel.id
        selected = await get_selected_character(channel_id)

        if selected:
            modal = InitStatsModalWithName(self.ctx, selected)
            await interaction.response.send_modal(modal)
            return

        names = await get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "stats")
        await interaction.response.send_message(
            "📊 選擇要設定數值的角色：", view=view, ephemeral=True
        )


class InitHPButton(Button):
    def __init__(self, ctx):
        super().__init__(label="❤️ 調整 HP", style=discord.ButtonStyle.secondary, row=2)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_entry_names, get_selected_character
        from ui.init_views import InitCharacterSelectView, InitHPModalWithName

        channel_id = self.ctx.channel.id
        selected = await get_selected_character(channel_id)

        if selected:
            modal = InitHPModalWithName(self.ctx, selected)
            await interaction.response.send_modal(modal)
            return

        names = await get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "hp")
        await interaction.response.send_message(
            "❤️ 選擇要調整 HP 的角色：", view=view, ephemeral=True
        )


class InitStatusButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="✨ 狀態管理", style=discord.ButtonStyle.secondary, row=2
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_entry_names, get_selected_character, get_entry
        from ui.init_views import InitStatusBatchEditModal

        channel_id = str(self.ctx.channel.id)
        selected = await get_selected_character(channel_id)

        # 1. 已鎖定角色 -> 直接開啟 Batch Edit Modal
        if selected:
            entry = await get_entry(channel_id, selected)
            if entry:
                current_status = entry.get("status_effects", {})
                await interaction.response.send_modal(
                    InitStatusBatchEditModal(self.ctx, selected, current_status)
                )
            else:
                await interaction.response.send_message(
                    "❌ 找不到鎖定角色的資料", ephemeral=True
                )
            return

        # 2. 未鎖定 -> 先選角色
        class InitStatusSelectView(discord.ui.View):
            def __init__(self, ctx, names):
                super().__init__(timeout=60)
                self.ctx = ctx
                self.add_item(InitStatusSelect(ctx, names))

        class InitStatusSelect(discord.ui.Select):
            def __init__(self, ctx, names):
                options = [
                    discord.SelectOption(label=name, value=name) for name in names[:25]
                ]
                super().__init__(placeholder="選擇要編輯狀態的角色...", options=options)
                self.ctx = ctx

            async def callback(self, interaction: discord.Interaction):
                from utils.initiative import get_entry

                name = self.values[0]
                entry = await get_entry(str(self.ctx.channel.id), name)
                if entry:
                    current_status = entry.get("status_effects", {})
                    await interaction.response.send_modal(
                        InitStatusBatchEditModal(self.ctx, name, current_status)
                    )

        names = await get_entry_names(channel_id)
        if not names:
            await interaction.response.send_message("❌ 先攻表是空的！", ephemeral=True)
            return

        await interaction.response.send_message(
            "✨ 選擇要編輯狀態的角色：",
            view=InitStatusSelectView(self.ctx, names),
            ephemeral=True,
        )


class InitFavDiceEditButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="🎲 編輯常用骰", style=discord.ButtonStyle.secondary, row=2
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from ui.init_views import InitFavDiceActionSelectView

        view = InitFavDiceActionSelectView(self.ctx)
        await interaction.response.send_message(
            "🎲 選擇常用骰操作：", view=view, ephemeral=True
        )


class InitFavDiceRollButton(Button):
    """擲常用骰按鈕"""

    def __init__(self, ctx):
        super().__init__(label="🎲 擲常用骰", style=discord.ButtonStyle.primary, row=2)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import (
            get_entry_names,
            get_selected_character,
            get_favorite_dice_names,
        )
        from ui.init_views import InitCharacterSelectView, InitFavDiceRollSelectView

        channel_id = self.ctx.channel.id
        selected = await get_selected_character(channel_id)

        if selected:
            dice_names = await get_favorite_dice_names(channel_id, selected)
            if not dice_names:
                await interaction.response.send_message(
                    f"❌ **{selected}** 沒有常用骰！", ephemeral=True
                )
                return
            view = InitFavDiceRollSelectView(self.ctx, selected, dice_names)
            await interaction.response.send_message(
                f"🎲 選擇 **{selected}** 的常用骰：", view=view, ephemeral=True
            )
            return

        names = await get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "fav_dice_roll")
        await interaction.response.send_message(
            "🎲 選擇要擲骰的角色：", view=view, ephemeral=True
        )


class InitEditButton(Button):
    def __init__(self, ctx):
        super().__init__(label="✏️ 編輯先攻", style=discord.ButtonStyle.secondary, row=2)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_entry_names, get_selected_character
        from ui.init_views import InitCharacterSelectView, InitEditInitiativeModal

        channel_id = self.ctx.channel.id
        selected = await get_selected_character(channel_id)

        if selected:
            modal = InitEditInitiativeModal(self.ctx, selected)
            await interaction.response.send_modal(modal)
            return

        names = await get_entry_names(channel_id)
        view = InitCharacterSelectView(self.ctx, names, "initiative")
        await interaction.response.send_message(
            "✏️ 選擇要編輯先攻的角色：", view=view, ephemeral=True
        )


class RerollAllInitiativeButton(Button):
    """全員重骰先攻按鈕"""

    def __init__(self, ctx):
        super().__init__(
            label="🔄 全員重骰先攻", style=discord.ButtonStyle.danger, row=4
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from utils.initiative import reroll_all_initiative, get_tracker_display
        from ui.init_views import InitiativeTrackerView

        channel_id = self.ctx.channel.id
        results = await reroll_all_initiative(channel_id)

        # 顯示結果摘要
        summary = "🎲 **全員重骰結果**:\n"
        for name, old, new, detail in results:
            summary += f"**{name}**: {old} → **{new}** ({detail})\n"

        if len(summary) > 2000:
            summary = summary[:1997] + "..."

        await interaction.followup.send(summary)

        # 刷新先攻表
        display = await get_tracker_display(channel_id)
        view = InitiativeTrackerView(self.ctx)

        # 嘗試更新原訊息
        if hasattr(interaction.message, "edit"):
            # 如果是從先攻表按鈕觸發（通常不會，因為這是在常用骰區），但如果是
            # 我們需要找到先攻表的訊息。
            # 這裡簡單發送新訊息或不做動作，因為 reroll_all_initiative 已經儲存了
            # 但使用者需要看到更新後的表。

            # 從 shared_state 獲取先攻表訊息引用
            import utils.shared_state as shared_state

            msg_refs = shared_state.initiative_messages.get(str(channel_id), {})
            tracker_msg = msg_refs.get("tracker_msg")

            if tracker_msg:
                try:
                    await tracker_msg.edit(content=display, view=view)
                except:
                    # 如果編輯失敗，發送新的
                    tracker_msg = await self.ctx.send(display, view=view)
                    shared_state.initiative_messages[str(channel_id)]["tracker_msg"] = (
                        tracker_msg
                    )
            else:
                tracker_msg = await self.ctx.send(display, view=view)
                if str(channel_id) not in shared_state.initiative_messages:
                    shared_state.initiative_messages[str(channel_id)] = {}
                shared_state.initiative_messages[str(channel_id)]["tracker_msg"] = (
                    tracker_msg
                )


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
        from utils.initiative import roll_favorite_dice

        channel_id = self.ctx.channel.id
        success, result, formula, roll_detail = await roll_favorite_dice(
            channel_id, self.char_name, self.dice_name
        )

        if success:
            # 多次擲骰時 roll_detail 已經是完整格式化字串
            if isinstance(result, list):
                await interaction.response.send_message(
                    f"🎲 **{self.char_name}** 擲 **{self.dice_name}**\n{roll_detail}"
                )
            else:
                await interaction.response.send_message(
                    f"🎲 **{self.char_name}** 擲 **{self.dice_name}** ({formula})\n結果: {roll_detail}"
                )
        else:
            await interaction.response.send_message(
                f"❌ 公式錯誤: {result}", ephemeral=True
            )


class InitRemoveSelectButton(Button):
    """移除特定角色按鈕"""

    def __init__(self, name, ctx):
        super().__init__(label=name, style=discord.ButtonStyle.danger)
        self.name = name
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from utils.initiative import remove_entry
        from ui.init_views import refresh_tracker_view

        channel_id = self.ctx.channel.id
        success = await remove_entry(channel_id, self.name)

        if success:
            await interaction.followup.send(
                f"✅ 已移除 **{self.name}**", ephemeral=True
            )
            await refresh_tracker_view(self.ctx)

            # 刪除選擇訊息
            await interaction.message.delete()
        else:
            await interaction.followup.send(
                f"❌ 找不到 **{self.name}**", ephemeral=True
            )


class InitUnifiedEditButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="📝 整合編輯", style=discord.ButtonStyle.secondary, row=2
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_selected_character, get_entry
        from ui.init_views import InitCharacterSelectView, InitUnifiedEditModal

        channel_id = str(self.ctx.channel.id)
        selected = await get_selected_character(channel_id)

        # 如果已鎖定角色，直接開啟 Modal
        if selected:
            entry = await get_entry(channel_id, selected)
            if entry:
                await interaction.response.send_modal(
                    InitUnifiedEditModal(
                        self.ctx,
                        selected,
                        hp=entry.get("hp"),
                        elements=entry.get("elements"),
                        atk=entry.get("atk"),
                        def_=entry.get("def_"),
                        initiative=entry.get("initiative"),
                    )
                )
            else:
                await interaction.response.send_message(
                    "❌ 找不到鎖定角色的資料", ephemeral=True
                )
            return

        # 如果未鎖定，先選擇角色
        # 這裡需要一個特殊的 View 來處理選人後開啟 Unified Modal
        # 為了 Demo 簡單起見，我們暫時使用 InitCharacterSelectView，但這會導致回調需要修改
        # 更好的方法是：彈出一個下拉選單，選完後直接開 Modal。

        # 讓我們定義一個專用的 Select View for Unified Edit
        class InitUnifiedSelectView(discord.ui.View):
            def __init__(self, ctx, names):
                super().__init__(timeout=60)
                self.ctx = ctx
                self.add_item(InitUnifiedSelect(ctx, names))

        class InitUnifiedSelect(discord.ui.Select):
            def __init__(self, ctx, names):
                options = [
                    discord.SelectOption(label=name, value=name) for name in names[:25]
                ]
                super().__init__(placeholder="選擇要編輯的角色...", options=options)
                self.ctx = ctx

            async def callback(self, interaction: discord.Interaction):
                from utils.initiative import get_entry

                name = self.values[0]
                entry = await get_entry(str(self.ctx.channel.id), name)
                if entry:
                    await interaction.response.send_modal(
                        InitUnifiedEditModal(
                            self.ctx,
                            name,
                            hp=entry.get("hp"),
                            elements=entry.get("elements"),
                            atk=entry.get("atk"),
                            def_=entry.get("def_"),
                            initiative=entry.get("initiative"),
                        )
                    )

        from utils.initiative import get_entry_names

        names = await get_entry_names(channel_id)
        if not names:
            await interaction.response.send_message("❌ 先攻表是空的！", ephemeral=True)
            return

        await interaction.response.send_message(
            "📝 選擇要編輯的角色：",
            view=InitUnifiedSelectView(self.ctx, names),
            ephemeral=True,
        )


class InitSaveCharButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="💾 保存角色", style=discord.ButtonStyle.secondary, row=3
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.initiative import get_selected_character, get_entry_names
        from ui.init_views import InitSaveSelectionView

        channel_id = str(self.ctx.channel.id)
        selected = await get_selected_character(channel_id)

        if selected:
            # 已鎖定，直接顯示保存選項
            view = InitSaveSelectionView(self.ctx, selected)
            await interaction.response.send_message(
                f"💾 保存 **{selected}** 到全域庫：\n請選擇要保存的項目 (同名將覆蓋)",
                view=view,
                ephemeral=True,
            )
        else:
            # 未鎖定，先選人
            names = await get_entry_names(channel_id)
            if not names:
                await interaction.response.send_message(
                    "❌ 先攻表是空的！", ephemeral=True
                )
                return

            # Temporary View for selection
            class SaveSelectView(discord.ui.View):
                def __init__(self, ctx, names):
                    super().__init__(timeout=60)
                    self.ctx = ctx
                    self.add_item(SaveSelect(ctx, names))

            class SaveSelect(discord.ui.Select):
                def __init__(self, ctx, names):
                    options = [
                        discord.SelectOption(label=name, value=name)
                        for name in names[:25]
                    ]
                    super().__init__(placeholder="選擇要保存的角色...", options=options)
                    self.ctx = ctx

                async def callback(self, interaction: discord.Interaction):
                    name = self.values[0]
                    view = InitSaveSelectionView(self.ctx, name)
                    await interaction.response.send_message(
                        f"💾 保存 **{name}** 到全域庫：\n請選擇要保存的項目 (同名將覆蓋)",
                        view=view,
                        ephemeral=True,
                    )

            await interaction.response.send_message(
                "💾 選擇要保存的角色：",
                view=SaveSelectView(self.ctx, names),
                ephemeral=True,
            )


class InitLoadCharButton(Button):
    def __init__(self, ctx):
        super().__init__(
            label="📂 導入角色", style=discord.ButtonStyle.secondary, row=3
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        from utils.character_storage import get_all_names
        from ui.init_views import InitLoadSelectionView

        names = await get_all_names()
        if not names:
            await interaction.response.send_message(
                "📂 全域角色庫是空的！", ephemeral=True
            )
            return

        view = InitLoadSelectionView(self.ctx, names)
        await interaction.response.send_message(
            "📂 選擇要導入的角色：", view=view, ephemeral=True
        )
