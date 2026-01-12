# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

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

## Validation Limits

| Item | Min | Max |
|------|-----|-----|
| Dice count | 1 | 100 |
| Dice faces | 2 | 1000 |
| Repeat times | 1 | 20 |
| CoC bonus/penalty | 0 | 3 |
