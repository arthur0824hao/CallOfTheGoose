"""
先攻表工具模組 (PostgreSQL / Async)
提供先攻表的核心邏輯功能 (支援多頻道)
"""

import json
import utils.shared_state as shared_state
from utils.dice import parse_and_roll, DiceParseError
from utils.music import log_message
from utils.db import Database

# ============================================
# 存取函數 (Async DB)
# ============================================


async def save_tracker(channel_id):
    """將特定頻道的先攻表儲存到資料庫"""
    channel_id = str(channel_id)
    if channel_id not in shared_state.initiative_trackers:
        return

    data = shared_state.initiative_trackers[channel_id]

    query = """
        INSERT INTO initiative_trackers (channel_id, data) VALUES ($1, $2)
        ON CONFLICT (channel_id) DO UPDATE SET data = $2, updated_at = CURRENT_TIMESTAMP
    """
    try:
        await Database.execute(query, channel_id, json.dumps(data))
        # log_message(f"💾 先攻表已儲存 (頻道 {channel_id})") # 減少 log 噪音
    except Exception as e:
        log_message(f"❌ 儲存先攻表失敗: {e}")


async def load_tracker(channel_id):
    """從資料庫載入特定頻道的先攻表"""
    channel_id = str(channel_id)
    query = "SELECT data FROM initiative_trackers WHERE channel_id = $1"
    try:
        data_str = await Database.fetchval(query, channel_id)
        if data_str:
            data = json.loads(data_str)
            shared_state.initiative_trackers[channel_id] = data
            log_message(f"📂 先攻表已載入 (頻道 {channel_id})")
            return True
    except Exception as e:
        log_message(f"❌ 載入先攻表失敗: {e}")
    return False


async def get_tracker(channel_id):
    """
    取得指定頻道的先攻表，若記憶體無則查 DB，若 DB 無則創建
    """
    channel_id = str(channel_id)

    # 1. 檢查記憶體
    if channel_id in shared_state.initiative_trackers:
        return shared_state.initiative_trackers[channel_id]

    # 2. 檢查資料庫
    if await load_tracker(channel_id):
        return shared_state.initiative_trackers[channel_id]

    # 3. 創建新的
    shared_state.initiative_trackers[channel_id] = {
        "entries": [],
        "current_round": 1,
        "current_index": 0,
        "is_active": False,
    }
    return shared_state.initiative_trackers[channel_id]


# ============================================
# 核心操作函數 (Async)
# ============================================


async def add_entry(
    channel_id, name: str, initiative: int, roll_detail: str = None, formula: str = None
):
    tracker = await get_tracker(channel_id)

    for entry in tracker["entries"]:
        if entry["name"] == name:
            return False

    new_entry = {
        "name": name,
        "initiative": initiative,
        "roll_detail": roll_detail,
        "hp": 0,
        "elements": 0,
        "atk": 0,
        "def_": 0,
        "獎勵/懲罰": 0,
        "優勢/劣勢": 0,
        "status_effects": {},
        "favorite_dice": {},
        "last_formula": formula,
    }

    tracker["entries"].append(new_entry)
    tracker["is_active"] = True

    await sort_entries(channel_id)
    await save_tracker(channel_id)

    log_message(f"⚔️ 先攻表: 新增 {name} (先攻: {initiative})")
    return True


async def add_entry_with_roll(channel_id, formula: str, name: str):
    try:
        result, dice_rolls = parse_and_roll(formula)

        if dice_rolls:
            rolls_str = ", ".join(
                f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                for d in dice_rolls
            )
            roll_detail = f"{rolls_str} = {result}"
        else:
            roll_detail = str(result)

        success = await add_entry(channel_id, name, result, roll_detail, formula)
        if success:
            return True, result, roll_detail
        else:
            return False, "角色名稱已存在", None

    except DiceParseError as e:
        return False, str(e), None


async def remove_entry(channel_id, name: str):
    tracker = await get_tracker(channel_id)

    for i, entry in enumerate(tracker["entries"]):
        if entry["name"] == name:
            tracker["entries"].pop(i)

            if tracker["current_index"] >= len(tracker["entries"]):
                tracker["current_index"] = 0

            if not tracker["entries"]:
                tracker["is_active"] = False

            if tracker.get("selected_character") == name:
                tracker["selected_character"] = None
                log_message(f"⚔️ 先攻表: 移除鎖定角色 {name}")

            log_message(f"⚔️ 先攻表: 移除 {name}")
            await save_tracker(channel_id)
            return True

    return False


async def select_character(channel_id, name: str):
    tracker = await get_tracker(channel_id)

    if not name or name == "None":
        tracker["selected_character"] = None
        log_message("⚔️ 先攻表: 取消選擇角色")
        await save_tracker(channel_id)
        return True

    if not await get_entry(channel_id, name):
        return False

    tracker["selected_character"] = name
    log_message(f"⚔️ 先攻表: 選擇角色 [{name}]")
    await save_tracker(channel_id)
    return True


async def get_selected_character(channel_id):
    tracker = await get_tracker(channel_id)
    name = tracker.get("selected_character")

    if name and await get_entry(channel_id, name):
        return name

    if name:
        tracker["selected_character"] = None
        await save_tracker(channel_id)

    return None


async def get_entry(channel_id, name: str):
    tracker = await get_tracker(channel_id)
    for entry in tracker["entries"]:
        if entry["name"] == name:
            return entry
    return None


async def sort_entries(channel_id):
    tracker = await get_tracker(channel_id)
    tracker["entries"].sort(key=lambda x: x["initiative"], reverse=True)


async def next_turn(channel_id):
    tracker = await get_tracker(channel_id)

    if not tracker["entries"]:
        return None, False

    tracker["current_index"] += 1
    new_round = False

    if tracker["current_index"] >= len(tracker["entries"]):
        tracker["current_index"] = 0
        tracker["current_round"] += 1
        new_round = True

    current_entry = tracker["entries"][tracker["current_index"]]
    log_message(
        f"⚔️ 先攻表: 輪到 {current_entry['name']} (回合 {tracker['current_round']})"
    )
    await save_tracker(channel_id)

    return current_entry["name"], new_round


async def prev_turn(channel_id):
    tracker = await get_tracker(channel_id)

    if not tracker["entries"]:
        return None, tracker["current_round"]

    tracker["current_index"] -= 1

    if tracker["current_index"] < 0:
        if tracker["current_round"] > 1:
            tracker["current_round"] -= 1
            tracker["current_index"] = len(tracker["entries"]) - 1
        else:
            tracker["current_index"] = 0

    current_entry = tracker["entries"][tracker["current_index"]]
    await save_tracker(channel_id)

    return current_entry["name"], tracker["current_round"]


async def set_stats(
    channel_id,
    name: str,
    hp: int = None,
    elements: int = None,
    atk: int = None,
    def_: int = None,
):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    if hp is not None:
        entry["hp"] = hp
    if elements is not None:
        entry["elements"] = elements
    if atk is not None:
        entry["atk"] = atk
    if def_ is not None:
        entry["def_"] = def_

    log_message(f"⚔️ 先攻表: 設定 {name} 數值")
    await save_tracker(channel_id)
    return True


async def modify_hp(channel_id, name: str, delta: int):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False, "找不到角色"

    entry["hp"] += delta
    log_message(
        f"⚔️ 先攻表: {name} HP {'+' if delta >= 0 else ''}{delta} → {entry['hp']}"
    )
    await save_tracker(channel_id)
    return True, entry["hp"]


async def modify_elements(channel_id, name: str, delta: int):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False, "找不到角色"

    entry["elements"] += delta
    log_message(
        f"⚔️ 先攻表: {name} 元素 {'+' if delta >= 0 else ''}{delta} → {entry['elements']}"
    )
    await save_tracker(channel_id)
    return True, entry["elements"]


async def add_status(channel_id, name: str, status_key: str, status_value: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    if isinstance(entry.get("status_effects"), list):
        entry["status_effects"] = {}

    entry["status_effects"][status_key] = status_value
    log_message(f"⚔️ 先攻表: {name} 獲得狀態 [{status_key}: {status_value}]")
    await save_tracker(channel_id)
    return True


async def update_status(channel_id, name: str, status_key: str, new_value: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    if status_key not in entry.get("status_effects", {}):
        return False

    entry["status_effects"][status_key] = new_value
    log_message(f"⚔️ 先攻表: {name} 狀態 [{status_key}] 更新為 [{new_value}]")
    await save_tracker(channel_id)
    return True


async def remove_status(channel_id, name: str, status_key: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    if status_key in entry.get("status_effects", {}):
        del entry["status_effects"][status_key]
        log_message(f"⚔️ 先攻表: {name} 移除狀態 [{status_key}]")
        await save_tracker(channel_id)
        return True
    return False


async def set_all_status(channel_id, name: str, status_dict: dict):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    entry["status_effects"] = status_dict
    log_message(f"⚔️ 先攻表: {name} 狀態批次更新 ({len(status_dict)} 項)")
    await save_tracker(channel_id)
    return True


async def get_status_names(channel_id, name: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return []

    status = entry.get("status_effects", {})
    if isinstance(status, dict):
        return list(status.keys())
    return []


async def set_initiative(channel_id, name: str, new_initiative: int):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    old_initiative = entry["initiative"]
    entry["initiative"] = new_initiative

    await sort_entries(channel_id)
    await save_tracker(channel_id)

    log_message(f"⚔️ 先攻表: {name} 先攻 {old_initiative} → {new_initiative}")
    return True


async def add_favorite_dice(channel_id, name: str, dice_name: str, dice_formula: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    if "favorite_dice" not in entry:
        entry["favorite_dice"] = {}

    entry["favorite_dice"][dice_name] = dice_formula
    log_message(f"⚔️ 先攻表: {name} 新增常用骰 [{dice_name}: {dice_formula}]")
    await save_tracker(channel_id)
    return True


async def remove_favorite_dice(channel_id, name: str, dice_name: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return False

    if dice_name in entry.get("favorite_dice", {}):
        del entry["favorite_dice"][dice_name]
        log_message(f"⚔️ 先攻表: {name} 移除常用骰 [{dice_name}]")
        await save_tracker(channel_id)
        return True
    return False


async def roll_favorite_dice(channel_id, name: str, dice_name: str):
    from utils.dice import format_multiple_results, try_coc_roll

    entry = await get_entry(channel_id, name)
    if not entry:
        return False, "找不到角色", None, None

    formula = entry.get("favorite_dice", {}).get(dice_name)
    if not formula:
        return False, "找不到常用骰", None, None

    try:
        # 解析重複次數（.N 格式）
        times = 1
        actual_formula = formula.strip()

        if actual_formula.startswith("."):
            parts = actual_formula.split(None, 1)
            if len(parts) >= 2:
                try:
                    times_str = parts[0][1:]  # 移除開頭的 '.'
                    times = int(times_str)
                    actual_formula = parts[1]
                except ValueError:
                    pass  # 解析失敗，視為普通公式

            # 驗證重複次數範圍
            if times < 1:
                times = 1
            if times > 20:
                times = 20

        coc_result = try_coc_roll(actual_formula)
        if coc_result:
            if coc_result.startswith("❌"):
                return False, coc_result, formula, None

            if times == 1:
                log_message(f"⚔️ 先攻表: {name} 擲 [{dice_name}] (CoC)")
                return True, "CoC", formula, coc_result
            else:
                results = [f"第1次：\n{coc_result}"]
                for i in range(1, times):
                    res = try_coc_roll(actual_formula)
                    results.append(f"第{i + 1}次：\n{res}")

                log_message(f"⚔️ 先攻表: {name} 擲 [{dice_name}] (CoC) × {times}")
                return True, "CoC", formula, "\n".join(results)

        if times == 1:
            result, dice_rolls = parse_and_roll(actual_formula)
            if dice_rolls:
                rolls_str = ", ".join(
                    f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                    for d in dice_rolls
                )
                roll_detail = f"{rolls_str} = {result}"
            else:
                roll_detail = str(result)

            log_message(f"⚔️ 先攻表: {name} 擲 [{dice_name}] ({formula}) = {result}")
            return True, result, formula, roll_detail
        else:
            results = []
            for _ in range(times):
                result, dice_rolls = parse_and_roll(actual_formula)
                results.append((result, dice_rolls))

            roll_detail = format_multiple_results(actual_formula, results, times)
            total_results = [r[0] for r in results]

            log_message(f"⚔️ 先攻表: {name} 擲 [{dice_name}] ({formula}) × {times}")
            return True, total_results, formula, roll_detail

    except DiceParseError as e:
        return False, str(e), formula, None


async def get_favorite_dice_names(channel_id, name: str):
    entry = await get_entry(channel_id, name)
    if not entry:
        return []
    return list(entry.get("favorite_dice", {}).keys())


async def reset_tracker(channel_id):
    tracker = await get_tracker(channel_id)
    tracker["current_round"] = 1
    tracker["current_index"] = 0
    log_message("⚔️ 先攻表: 重置回合")
    await save_tracker(channel_id)


async def end_combat(channel_id):
    tracker = await get_tracker(channel_id)

    summary = {
        "total_rounds": tracker["current_round"],
        "total_characters": len(tracker["entries"]),
        "survivors": [
            e["name"] for e in tracker["entries"] if e["hp"] is None or e["hp"] > 0
        ],
    }

    tracker["entries"] = []
    tracker["current_round"] = 1
    tracker["current_index"] = 0
    tracker["is_active"] = False

    log_message(f"⚔️ 先攻表: 戰鬥結束 (共 {summary['total_rounds']} 回合)")
    await save_tracker(channel_id)

    return summary


async def get_tracker_display(channel_id):
    tracker = await get_tracker(channel_id)

    if not tracker["entries"]:
        return "⚔️ **先攻表** ─ 尚無角色\n\n使用 `!init 1d20+修正 名字` 加入角色"

    lines = [f"⚔️ **先攻表** ─ 第 {tracker['current_round']} 回合"]

    target = await get_selected_character(channel_id)
    if target:
        lines.append(f"🎯 **當前鎖定**: {target}")

    lines.append("━" * 30)

    for i, entry in enumerate(tracker["entries"]):
        prefix = "▶ " if i == tracker["current_index"] else "   "
        line = f"{prefix}{i + 1}. **{entry['name']}** [先攻: {entry['initiative']}]"

        stats_parts = []
        if entry["hp"] is not None:
            stats_parts.append(f"HP: {entry['hp']}")
        if entry["elements"] is not None:
            stats_parts.append(f"元素: {entry['elements']}")
        if entry["atk"] is not None:
            stats_parts.append(f"ATK: {entry['atk']}")
        if entry["def_"] is not None:
            stats_parts.append(f"DEF: {entry['def_']}")

        if stats_parts:
            line += " | " + " | ".join(stats_parts)

        status = entry.get("status_effects", {})
        if status:
            if isinstance(status, dict):
                status_str = " ".join(f"✦{k}:{v}" for k, v in status.items())
            else:
                status_str = " ".join(f"✦{s}" for s in status)
            line += f" | {status_str}"

        lines.append(line)

    lines.append("━" * 30)
    return "\n".join(lines)


async def get_entry_names(channel_id):
    tracker = await get_tracker(channel_id)
    return [entry["name"] for entry in tracker["entries"]]


async def reroll_all_initiative(channel_id):
    tracker = await get_tracker(channel_id)
    results = []

    for entry in tracker["entries"]:
        old_init = entry["initiative"]
        formula = entry.get("last_formula")

        if formula:
            try:
                total, dice_rolls = parse_and_roll(formula)
                if dice_rolls:
                    rolls_str = ", ".join(
                        f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                        for d in dice_rolls
                    )
                    roll_detail = f"{rolls_str} = {total}"
                else:
                    roll_detail = str(total)

                entry["initiative"] = total
                entry["roll_detail"] = roll_detail
                results.append((entry["name"], old_init, total, roll_detail))

            except DiceParseError as e:
                entry["initiative"] = 0
                entry["roll_detail"] = "0 (公式錯誤)"
                results.append((entry["name"], old_init, 0, f"0 (公式錯誤: {e})"))
        else:
            entry["initiative"] = 0
            entry["roll_detail"] = "0"
            results.append((entry["name"], old_init, 0, "0 (無公式)"))

    await sort_entries(channel_id)
    await save_tracker(channel_id)

    log_message(f"⚔️ 先攻表: 全員重骰完成 ({len(results)} 位角色)")
    return results


async def get_favorite_dice_display(channel_id):
    tracker = await get_tracker(channel_id)

    if not tracker["entries"]:
        return None

    lines = ["🎲 **常用骰快捷區**", "━" * 30]
    has_any_dice = False

    target = await get_selected_character(channel_id)

    for entry in tracker["entries"]:
        if target and entry["name"] != target and entry["name"] != "GM":
            continue

        dice = entry.get("favorite_dice", {})
        if dice:
            has_any_dice = True
            dice_names = list(dice.keys())[:5]
            dice_list = " | ".join(f"`{name}`" for name in dice_names)
            if len(dice) > 5:
                dice_list += " ..."
            lines.append(f"**{entry['name']}**: {dice_list}")

    lines.append("━" * 30)

    return "\n".join(lines) if has_any_dice else None
