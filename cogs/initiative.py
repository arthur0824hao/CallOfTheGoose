
import discord
from discord.ext import commands
from utils.permissions import check_authorization
from ui.views import InitiativeTrackerView, FavoriteDiceOverviewView
from utils.initiative import (add_entry, add_entry_with_roll, remove_entry, get_entry,
                              next_turn, set_stats, modify_hp, modify_elements,
                              add_status, remove_status, reset_tracker, end_combat,
                              get_tracker_display, get_entry_names, get_favorite_dice_display)
import utils.shared_state as shared_state

class Initiative(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def display_init_ui(self, ctx, force_new=False):
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

    @commands.command(name="init")
    async def init_command(self, ctx, *, args: str = None):
        if not check_authorization(ctx):
            return
        
        # 沒有參數時，顯示先攻表 (強制刷新)
        if not args:
            await self.display_init_ui(ctx, force_new=True)
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
                await self.display_init_ui(ctx)
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
                await self.display_init_ui(ctx)
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
                await self.display_init_ui(ctx)
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
                await self.display_init_ui(ctx)
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
            await self.display_init_ui(ctx)
        
        else:
            # 嘗試解析為骰子公式 + 名字
            # 格式: !init 1d20+5 戰士
            if len(parts) >= 2:
                formula = parts[0]
                name = parts[1]
                
                success, result, roll_detail = add_entry_with_roll(ctx.channel.id, formula, name)
                if success:
                    await ctx.send(f"🎲 擲骰: {formula} → {roll_detail}\n✅ 已新增 **{name}** (先攻: {result})")
                    await self.display_init_ui(ctx)
                else:
                    await ctx.send(f"❌ {result}")
            else:
                await ctx.send("❌ 未知的子命令！使用 `!init` 查看先攻表")

    @commands.group(name="char", invoke_without_command=True)
    async def char_command(self, ctx):
        if not check_authorization(ctx): return
        await ctx.send("使用 `!char list` 列出角色，`!char show <名字>` 查看詳情，或使用先攻表按鈕進行保存/導入。")

    @char_command.command(name="list")
    async def char_list(self, ctx):
        from utils.character_storage import get_all_names
        names = await get_all_names()
        if not names:
            await ctx.send("📂 全域角色庫是空的。")
            return
        
        msg = "📂 **全域角色列表**:\n" + ", ".join(f"`{n}`" for n in names)
        await ctx.send(msg)

    @char_command.command(name="delete")
    async def char_delete(self, ctx, name: str):
        from utils.character_storage import delete_character
        success = await delete_character(name)
        if success:
            await ctx.send(f"🗑️ 已刪除全域角色 **{name}**")
        else:
            await ctx.send(f"❌ 找不到全域角色 **{name}**")

    @char_command.command(name="show")
    async def char_show(self, ctx, name: str):
        from utils.character_storage import get_character
        data = await get_character(name)
        if not data:
            await ctx.send(f"❌ 找不到全域角色 **{name}**")
            return
            
        stats = data.get("stats", {})
        dice = data.get("favorite_dice", {})
        formula = data.get("initiative_formula")
        
        embed = discord.Embed(title=f"角色詳情: {name}", color=discord.Color.blue())
        if formula:
            embed.add_field(name="⚔️ 先攻公式", value=f"`{formula}`", inline=False)
            
        stats_desc = []
        if stats.get("hp") is not None: stats_desc.append(f"HP: {stats['hp']}")
        if stats.get("elements") is not None: stats_desc.append(f"元素: {stats['elements']}")
        if stats.get("atk") is not None: stats_desc.append(f"ATK: {stats['atk']}")
        if stats.get("def_") is not None: stats_desc.append(f"DEF: {stats['def_']}")
        if stats_desc:
            embed.add_field(name="📊 基礎數值", value=" | ".join(stats_desc), inline=False)
            
        if dice:
            dice_desc = "\n".join(f"• **{k}**: `{v}`" for k, v in dice.items())
            embed.add_field(name="🎲 常用骰", value=dice_desc, inline=False)
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Initiative(bot))
