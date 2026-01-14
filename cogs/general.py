
import discord
from discord.ext import commands
from permissions import check_authorization

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx, *, topic: str = None):
        if not check_authorization(ctx):
            return
            
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

async def setup(bot):
    await bot.add_cog(General(bot))
