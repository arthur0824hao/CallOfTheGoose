# AGENT.md

## users word for you (do not touch or remove)


### General

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

所有功能都要用TDD
新功能開發用git branch  沒問題才並回主分支



### Setup
```bash
pip install -r requirements.txt
```

### Run the Bot
```bash
python bot.py
```

### Requirements
- FFmpeg must be installed and available in PATH for music playback
- Discord bot token must be configured via environment or in code

## Environment Maintenance

### Update Tools
- **OpenCode**: Run `opencode upgrade`
- **Oh My OpenCode**: Run `ohmyopencode update` (or check installation docs)

## Architecture Overview

The bot follows a modular architecture:

```
bot.py (Entry point & core setup)
    ↓
commands.py (Command implementations & registration)
    ↓
Utility modules:
- music_utils.py (Music playback, logging)
- dice_utils.py (Dice rolling parser & formatter)
- buttons.py (Discord UI buttons)
- views.py (Discord UI views)
- shared_state.py (Global state management)
```

## Command System Pattern

All commands follow a three-step pattern:

1. **Define command function** (in `commands.py`):
```python
async def cmd_commandname(ctx, param1, param2):
    await ctx.send("response")
```

2. **Register command** (in `register_commands()` function):
```python
@bot.command(name="commandname")
async def commandname_command(ctx, param1, param2):
    if not check_authorization(ctx):
        return
    await cmd_commandname(ctx, param1, param2)
```

3. **Authorization**: All commands require `check_authorization(ctx)` check (defined in `bot.py:92`)

### Command Prefix
All commands use the `!` prefix (e.g., `!play`, `!r`, `!skip`).

## Key Files

- **bot.py**: Entry point, bot initialization, `check_authorization()` at line 92
- **commands.py**: All command implementations (`cmd_*` functions) and `register_commands(bot)`
- **dice_utils.py**: Dice rolling system with recursive descent parser
- **music_utils.py**: Music playback, queue management, `log_message()` function
- **shared_state.py**: Global state (queues, current songs, per-channel initiative trackers)
- **initiative_utils.py**: 先攻表核心邏輯，所有函數第一個參數為 `channel_id`

## Initiative Tracker (Per-Channel)

先攻表支援多頻道獨立運作：
- 使用 `shared_state.get_tracker(channel_id)` 取得頻道專屬先攻表
- 所有 `initiative_utils` 函數第一個參數皆為 `channel_id`
- JSON 格式: `{"channels": {"channel_id": {...tracker data...}}}`
- **UI 行為**: 下拉選單在先攻表為空時，會顯示「新增角色」選項，防止卡死。

## Dice Rolling System

### Command Format
```
!r <formula>          # Single roll
!r .N <formula>       # Repeat N times (1-20)
!r cc[n][N] <skill>   # Call of Cthulhu roll
```

### Parser Architecture
**Recursive Descent Parser** with three precedence levels:
- `expression`: handles + and -
- `term`: handles * and /
- `factor`: handles numbers, dice (NdM), parentheses

### Supported Syntax
- Basic Dice: `1d20`, `2d6`
- Math: `+`, `-`, `*`, `/`, parentheses
- Keep Highest/Lowest: `3d20kh2`, `5d6kl3`
- CoC Rolls: `cc 65`, `cc1 65` (bonus), `ccn2 50` (penalty)

### Call of Cthulhu Mechanics
- `cc`: Normal roll, `cc1-3`: Bonus dice (min tens), `ccn1-3`: Penalty dice (max tens)
- Critical Success: Result == 1 only
- Fumble: Result >= 96
- Success: Result <= skill_value

## Critical Implementation Details

1. **CoC Prefix Parsing Order**: In `cmd_roll()`, ALWAYS parse `.N` prefix BEFORE checking for CoC pattern. Otherwise `!r .3 cc1 65` fails.

2. **Critical Success Rule**: In CoC, only rolling exactly 1 is a critical success. NOT <= 5.

3. **Keep Count Validation**: Use `keep_count is not None` not `keep_count` to properly validate `kh0` as invalid.

4. **Logging**: Use `log_message(msg)` from `music_utils.py` for all logging.

## Recent Updates (2026-01-12)

- **Initiative UI Enhancement**:
  - `!init` now displays two messages:
    1. Initiative Tracker (with standard controls)
    2. Character Favorite Dice Shortcuts (with "Reroll All Initiative" button)
  - Favorite dice shortcuts only appear if characters have them.
  - "Reroll All Initiative" allows rerolling for everyone at once.

## Validation Limits

| Item | Min | Max |
|------|-----|-----|
| Dice count | 1 | 100 |
| Dice faces | 2 | 1000 |
| Repeat times | 1 | 20 |
| CoC bonus/penalty | 0 | 3 |


# GooseOnCall 音樂機器人開發記錄

## 2025-03-01 開發中遇到的問題與解決

### 播放問題：過度複雜導致失敗
- **問題**：多層檢查、複雜的PCM轉換和進度監控導致播放無法正常進行
- **解決**：回歸最簡單的播放方式，採用「如無必要，勿增實體」原則
- **原理**：使用最基本的 discord.FFmpegPCMAudio 直接播放，不加任何參數
- **教訓**：優化的前提是基本功能可用，過度優化反而導致不穩定

### 爆音問題
- **問題**：某些歌曲音量過大或不穩定，造成爆音
- **解決**：
  1. 使用 FFmpeg 的 volume 過濾器降低音量 (volume=0.65)
  2. 應用 Discord.py 的 PCMVolumeTransformer 再次調整音量 (volume=0.7)
  3. 保持簡單的參數配置，避免過度複雜化

### 其他已解決問題
- **PCM音訊播放問題**: Discord.py 的音頻系統在調用 PCMStreamReader.read() 方法時傳入額外參數
- **播放模式功能**: 實現了單曲循環、隨機播放、循環播放清單、播完後待機四種播放模式
- **命令參數傳遞**: 統一使用關鍵字參數 `title=song_title`，確保參數正確傳遞

## 新增功能 - YouTube Cookies 支援
- **問題**: 某些私人或受限制的 YouTube 影片無法下載
- **解決**：
  1. 從瀏覽器導出 YouTube cookies
  2. 創建 config/cookies_config.py 存儲 cookies 設定
  3. 修改 download_song 函數使用 cookies 進行認證
  4. 通過共享狀態模塊在全局範圍使用 cookies 路徑
- **優點**：
  1. 可以下載私人或受限影片 (如果用戶有權限)
  2. 設置一次後所有下載都會自動使用認證
  3. 不會將認證信息硬編碼到主程序中

## 音頻優化的平衡之道
我們發現，音頻處理需要在功能豐富性和穩定性之間取得平衡：
1. 過度複雜的參數和前處理會導致播放不穩定
2. 但基本的音量控制仍然是必要的，以解決爆音問題
3. 最佳實踐是使用最少的參數達到足夠的效果
4. Discord.py 內建的 PCMVolumeTransformer 已經提供足夠的音量控制功能

## 未來改進方向 (從簡單做起)
1. 確保基本播放穩定後再嘗試音質優化
2. 考慮使用更穩定的播放庫
3. 將複雜功能設為選項，而非默認
4. 重視可靠性勝於功能豐富度- 已安裝 Bun

## Recent Updates (2026-01-15)

### Major Refactoring
- **Modular Structure**: Codebase reorganized into `utils/`, `ui/`, and `cogs/`.
  - `utils/`: `dice.py`, `music.py`, `initiative.py`, `character_storage.py`, `shared_state.py`
  - `ui/`: `views.py`, `buttons.py`
- **Global Character Storage**: New `!char` command and persistent storage in `data/characters.json`.
  - `!char list`: List saved characters.
  - `!char show`: View details.
  - `!char delete`: Delete character.

### Initiative Tracker Enhancements
- **Unified Edit Modal**: One modal to edit HP, Elements, ATK, DEF, and Initiative at once.
- **Batch Status Edit**: Textarea-based status editing (add/remove/update multiple statuses in one go).
- **Save/Load Character**:
  - **Save**: Export current character stats/dice to global storage.
  - **Load**: Import character from global storage (auto-rolls initiative).
- **Target Locking**: Improved integration with new UI buttons.

### Core Improvements
- **Dice Parser**: Added support for unary operators (e.g., `-1d4`, `+5`).
- **Stability**: Implemented `asyncio.Lock` for music and character storage operations.
- **Error Handling**: Enhanced JSON loading safety (backups corrupted files).
- **Music UI**: Refactored queue removal to use in-place message editing (no flickering).
