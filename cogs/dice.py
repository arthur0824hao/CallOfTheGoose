
import discord
from discord.ext import commands
from permissions import check_authorization
from dice_utils import (parse_and_roll, format_dice_result, format_multiple_results,
                        DiceParseError, roll_coc_dice, format_coc_result)
from music_utils import log_message

class Dice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="r")
    async def roll_command(self, ctx, *, formula: str):
        if not check_authorization(ctx):
            return
            
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

async def setup(bot):
    await bot.add_cog(Dice(bot))
