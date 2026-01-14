"""
先攻表工具模組
提供先攻表的核心邏輯功能 (支援多頻道)
"""

import json
import os
import shared_state
from dice_utils import parse_and_roll, DiceParseError
from music_utils import log_message

# JSON 儲存路徑
INITIATIVE_FILE_PATH = "initiative_tracker.json"


# ============================================
# 存取函數
# ============================================

def save_tracker():
    """將所有頻道的先攻表儲存到 JSON 檔案"""
    try:
        data = {"channels": shared_state.initiative_trackers}
        with open(INITIATIVE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log_message("💾 先攻表已儲存")
    except Exception as e:
        log_message(f"❌ 儲存先攻表失敗: {e}")


def load_tracker():
    """從 JSON 檔案載入先攻表 (支援舊格式遷移)"""
    try:
        if os.path.exists(INITIATIVE_FILE_PATH):
            with open(INITIATIVE_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 新格式: {"channels": {...}}
                if "channels" in data:
                    shared_state.initiative_trackers = data["channels"]
                    total_channels = len(shared_state.initiative_trackers)
                    total_chars = sum(len(t.get("entries", [])) for t in shared_state.initiative_trackers.values())
                    log_message(f"📂 先攻表已載入 ({total_channels} 頻道, {total_chars} 位角色)")
                
                # 舊格式遷移: {"entries": [...], ...}
                elif "entries" in data:
                    # 將舊資料放入 "legacy" 頻道 (之後可以手動遷移)
                    shared_state.initiative_trackers["legacy"] = data
                    log_message(f"📂 先攻表已遷移舊格式 ({len(data.get('entries', []))} 位角色)")
                
                return True
    except Exception as e:
        log_message(f"❌ 載入先攻表失敗: {e}")
    return False


# ============================================
# 核心操作函數 (所有函數使用 channel_id 參數)
# ============================================

def add_entry(channel_id, name: str, initiative: int, roll_detail: str = None, formula: str = None):
    """
    新增角色到先攻表
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        initiative: 先攻值
        roll_detail: 擲骰詳情 (可選)
    
    Returns:
        bool: 是否成功新增
    """
    tracker = shared_state.get_tracker(channel_id)
    
    # 檢查是否已存在同名角色
    for entry in tracker["entries"]:
        if entry["name"] == name:
            return False
    
    # 預設 stats 為 0
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
        "last_formula": formula
    }
    
    tracker["entries"].append(new_entry)
    tracker["is_active"] = True
    
    # 按先攻值排序 (由高到低)
    sort_entries(channel_id)
    
    # 自動儲存
    save_tracker()
    
    log_message(f"⚔️ 先攻表: 新增 {name} (先攻: {initiative})")
    return True


def add_entry_with_roll(channel_id, formula: str, name: str):
    """
    擲骰並新增角色到先攻表
    
    Args:
        channel_id: 頻道 ID
        formula: 骰子公式 (例如 "1d20+5")
        name: 角色名稱
    
    Returns:
        tuple: (成功與否, 先攻值或錯誤訊息, 擲骰詳情)
    """
    try:
        result, dice_rolls = parse_and_roll(formula)
        
        # 生成擲骰詳情
        if dice_rolls:
            rolls_str = ", ".join(
                f"[{', '.join(map(str, d.kept_rolls if d.kept_rolls else d.rolls))}]"
                for d in dice_rolls
            )
            roll_detail = f"{rolls_str} = {result}"
        else:
            roll_detail = str(result)
        
        success = add_entry(channel_id, name, result, roll_detail, formula)
        if success:
            return True, result, roll_detail
        else:
            return False, "角色名稱已存在", None
            
    except DiceParseError as e:
        return False, str(e), None



def remove_entry(channel_id, name: str):
    """
    從先攻表移除角色
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
    
    Returns:
        bool: 是否成功移除
    """
    tracker = shared_state.get_tracker(channel_id)
    
    for i, entry in enumerate(tracker["entries"]):
        if entry["name"] == name:
            tracker["entries"].pop(i)
            
            # 調整當前索引
            if tracker["current_index"] >= len(tracker["entries"]):
                tracker["current_index"] = 0
            
            # 如果沒有角色了，結束戰鬥
            if not tracker["entries"]:
                tracker["is_active"] = False
            
            # 檢查是否為當前鎖定角色，若是則移除鎖定
            if tracker.get("selected_character") == name:
                tracker["selected_character"] = None
                log_message(f"⚔️ 先攻表: 移除鎖定角色 {name}")
            
            log_message(f"⚔️ 先攻表: 移除 {name}")
            save_tracker()
            return True
    
    return False


def select_character(channel_id, name: str):
    """
    設定當前選擇的角色
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱 (若為 None 或空字串則為取消選擇)
    
    Returns:
        bool: 是否成功 (若角色不存在且非取消則返回 False)
    """
    tracker = shared_state.get_tracker(channel_id)
    
    if not name or name == "None":
        tracker["selected_character"] = None
        log_message("⚔️ 先攻表: 取消選擇角色")
        save_tracker()
        return True
    
    # 確認角色存在
    if not get_entry(channel_id, name):
        return False
        
    tracker["selected_character"] = name
    log_message(f"⚔️ 先攻表: 選擇角色 [{name}]")
    save_tracker()
    return True


def get_selected_character(channel_id):
    """
    取得當前選擇的角色名稱
    
    Returns:
        str or None: 角色名稱
    """
    tracker = shared_state.get_tracker(channel_id)
    name = tracker.get("selected_character")
    
    # 再次確認該角色是否還在先攻表中 (防止被移除後仍選中)
    if name and get_entry(channel_id, name):
        return name
    
    # 若角色已不在，清除選擇
    if name:
        tracker["selected_character"] = None
        save_tracker()
        
    return None



def get_entry(channel_id, name: str):
    """
    取得角色資料
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
    
    Returns:
        dict or None: 角色資料
    """
    tracker = shared_state.get_tracker(channel_id)
    
    for entry in tracker["entries"]:
        if entry["name"] == name:
            return entry
    
    return None


def sort_entries(channel_id):
    """按先攻值排序 (由高到低)"""
    tracker = shared_state.get_tracker(channel_id)
    tracker["entries"].sort(key=lambda x: x["initiative"], reverse=True)


def next_turn(channel_id):
    """
    切換到下一位行動者
    
    Args:
        channel_id: 頻道 ID
    
    Returns:
        tuple: (角色名稱, 是否進入新回合)
    """
    tracker = shared_state.get_tracker(channel_id)
    
    if not tracker["entries"]:
        return None, False
    
    # 移動到下一位
    tracker["current_index"] += 1
    new_round = False
    
    # 如果超過列表長度，回到第一位並增加回合數
    if tracker["current_index"] >= len(tracker["entries"]):
        tracker["current_index"] = 0
        tracker["current_round"] += 1
        new_round = True
    
    current_entry = tracker["entries"][tracker["current_index"]]
    log_message(f"⚔️ 先攻表: 輪到 {current_entry['name']} (回合 {tracker['current_round']})")
    save_tracker()
    
    return current_entry["name"], new_round


def prev_turn(channel_id):
    """
    切換到上一位行動者 (反向操作)
    
    Args:
        channel_id: 頻道 ID
        
    Returns:
        tuple: (角色名稱, 當前回合數)
    """
    tracker = shared_state.get_tracker(channel_id)
    
    if not tracker["entries"]:
        return None, tracker["current_round"]
        
    tracker["current_index"] -= 1
    
    # 如果小於 0，回到上一回合的最後一位
    if tracker["current_index"] < 0:
        if tracker["current_round"] > 1:
            tracker["current_round"] -= 1
            tracker["current_index"] = len(tracker["entries"]) - 1
        else:
            # 第一回合第一位，無法再退
            tracker["current_index"] = 0
            
    current_entry = tracker["entries"][tracker["current_index"]]
    save_tracker()
    
    return current_entry["name"], tracker["current_round"]



def set_stats(channel_id, name: str, hp: int = None, elements: int = None, atk: int = None, def_: int = None):
    """
    設定角色數值
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        hp: 生命值
        elements: 剩餘元素
        atk: 攻擊等級
        def_: 防禦等級
    
    Returns:
        bool: 是否成功設定
    """
    entry = get_entry(channel_id, name)
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
    save_tracker()
    return True


def modify_hp(channel_id, name: str, delta: int):
    """
    調整角色 HP
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        delta: HP 變化量 (正數為增加，負數為減少)
    
    Returns:
        tuple: (成功與否, 新 HP 值或錯誤訊息)
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False, "找不到角色"
    
    entry["hp"] += delta
    log_message(f"⚔️ 先攻表: {name} HP {'+' if delta >= 0 else ''}{delta} → {entry['hp']}")
    save_tracker()
    
    return True, entry["hp"]


def modify_elements(channel_id, name: str, delta: int):
    """
    調整角色剩餘元素
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        delta: 元素變化量
    
    Returns:
        tuple: (成功與否, 新元素值或錯誤訊息)
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False, "找不到角色"
    
    entry["elements"] += delta
    log_message(f"⚔️ 先攻表: {name} 元素 {'+' if delta >= 0 else ''}{delta} → {entry['elements']}")
    save_tracker()
    
    return True, entry["elements"]


def add_status(channel_id, name: str, status_key: str, status_value: str):
    """
    新增狀態效果 (鍵值對)
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        status_key: 狀態名稱
        status_value: 狀態值
    
    Returns:
        bool: 是否成功新增
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False
    
    # 確保 status_effects 是 dict
    if isinstance(entry.get("status_effects"), list):
        entry["status_effects"] = {}
    
    entry["status_effects"][status_key] = status_value
    log_message(f"⚔️ 先攻表: {name} 獲得狀態 [{status_key}: {status_value}]")
    save_tracker()
    
    return True


def update_status(channel_id, name: str, status_key: str, new_value: str):
    """
    更新狀態效果的值
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        status_key: 狀態名稱
        new_value: 新狀態值
    
    Returns:
        bool: 是否成功更新
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False
    
    if status_key not in entry.get("status_effects", {}):
        return False
    
    entry["status_effects"][status_key] = new_value
    log_message(f"⚔️ 先攻表: {name} 狀態 [{status_key}] 更新為 [{new_value}]")
    save_tracker()
    
    return True


def remove_status(channel_id, name: str, status_key: str):
    """
    移除狀態效果
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        status_key: 狀態名稱
    
    Returns:
        bool: 是否成功移除
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False
    
    if status_key in entry.get("status_effects", {}):
        del entry["status_effects"][status_key]
        log_message(f"⚔️ 先攻表: {name} 移除狀態 [{status_key}]")
        save_tracker()
        return True
    
    return False


def get_status_names(channel_id, name: str):
    """
    取得角色的所有狀態名稱
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
    
    Returns:
        list: 狀態名稱列表
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return []
    
    status = entry.get("status_effects", {})
    if isinstance(status, dict):
        return list(status.keys())
    return []


def set_initiative(channel_id, name: str, new_initiative: int):
    """
    修改角色的先攻值
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        new_initiative: 新先攻值
    
    Returns:
        bool: 是否成功修改
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False
    
    old_initiative = entry["initiative"]
    entry["initiative"] = new_initiative
    
    # 重新排序
    sort_entries(channel_id)
    save_tracker()
    
    log_message(f"⚔️ 先攻表: {name} 先攻 {old_initiative} → {new_initiative}")
    return True


def add_favorite_dice(channel_id, name: str, dice_name: str, dice_formula: str):
    """
    新增常用骰
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        dice_name: 骰子名稱
        dice_formula: 骰子公式
    
    Returns:
        bool: 是否成功新增
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False
    
    # 確保 favorite_dice 存在
    if "favorite_dice" not in entry:
        entry["favorite_dice"] = {}
    
    entry["favorite_dice"][dice_name] = dice_formula
    log_message(f"⚔️ 先攻表: {name} 新增常用骰 [{dice_name}: {dice_formula}]")
    save_tracker()
    
    return True


def remove_favorite_dice(channel_id, name: str, dice_name: str):
    """
    移除常用骰
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        dice_name: 骰子名稱
    
    Returns:
        bool: 是否成功移除
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return False
    
    if dice_name in entry.get("favorite_dice", {}):
        del entry["favorite_dice"][dice_name]
        log_message(f"⚔️ 先攻表: {name} 移除常用骰 [{dice_name}]")
        save_tracker()
        return True
    
    return False


def roll_favorite_dice(channel_id, name: str, dice_name: str):
    """
    擲常用骰
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
        dice_name: 骰子名稱
    
    Returns:
        tuple: (成功與否, 結果或錯誤訊息, 公式, 擲骰詳情)
    """
    from dice_utils import format_multiple_results
    
    entry = get_entry(channel_id, name)
    if not entry:
        return False, "找不到角色", None, None
    
    formula = entry.get("favorite_dice", {}).get(dice_name)
    if not formula:
        return False, "找不到常用骰", None, None
    
    try:
        # 解析重複次數（.N 格式）
        times = 1
        actual_formula = formula.strip()
        
        if actual_formula.startswith('.'):
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
        
        # 執行擲骰
        if times == 1:
            result, dice_rolls = parse_and_roll(actual_formula)
            
            # 生成擲骰詳情
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
            # 多次擲骰
            results = []
            for _ in range(times):
                result, dice_rolls = parse_and_roll(actual_formula)
                results.append((result, dice_rolls))
            
            # 使用格式化函數生成詳情
            roll_detail = format_multiple_results(actual_formula, results, times)
            total_results = [r[0] for r in results]
            
            log_message(f"⚔️ 先攻表: {name} 擲 [{dice_name}] ({formula}) × {times}")
            return True, total_results, formula, roll_detail
        
    except DiceParseError as e:
        return False, str(e), formula, None


def get_favorite_dice_names(channel_id, name: str):
    """
    取得角色的所有常用骰名稱
    
    Args:
        channel_id: 頻道 ID
        name: 角色名稱
    
    Returns:
        list: 常用骰名稱列表
    """
    entry = get_entry(channel_id, name)
    if not entry:
        return []
    
    return list(entry.get("favorite_dice", {}).keys())


def reset_tracker(channel_id):
    """重置回合數但保留角色"""
    tracker = shared_state.get_tracker(channel_id)
    tracker["current_round"] = 1
    tracker["current_index"] = 0
    log_message("⚔️ 先攻表: 重置回合")
    save_tracker()


def end_combat(channel_id):
    """
    結束戰鬥，清空先攻表
    
    Args:
        channel_id: 頻道 ID
    
    Returns:
        dict: 戰鬥統計資料
    """
    tracker = shared_state.get_tracker(channel_id)
    
    summary = {
        "total_rounds": tracker["current_round"],
        "total_characters": len(tracker["entries"]),
        "survivors": [e["name"] for e in tracker["entries"] if e["hp"] is None or e["hp"] > 0]
    }
    
    # 清空先攻表
    tracker["entries"] = []
    tracker["current_round"] = 1
    tracker["current_index"] = 0
    tracker["is_active"] = False
    
    log_message(f"⚔️ 先攻表: 戰鬥結束 (共 {summary['total_rounds']} 回合)")
    save_tracker()
    
    return summary



def get_tracker_display(channel_id):
    """
    生成先攻表顯示文字
    
    Args:
        channel_id: 頻道 ID
    
    Returns:
        str: 格式化的先攻表文字
    """
    tracker = shared_state.get_tracker(channel_id)
    
    if not tracker["entries"]:
        return "⚔️ **先攻表** ─ 尚無角色\n\n使用 `!init 1d20+修正 名字` 加入角色"
    
    lines = [f"⚔️ **先攻表** ─ 第 {tracker['current_round']} 回合"]
    
    # 顯示當前鎖定角色
    target = get_selected_character(channel_id)
    if target:
        lines.append(f"🎯 **當前鎖定**: {target}")
        
    lines.append("━" * 30)
    
    for i, entry in enumerate(tracker["entries"]):
        # 當前行動者標記
        prefix = "▶ " if i == tracker["current_index"] else "   "
        
        # 基本資訊
        line = f"{prefix}{i + 1}. **{entry['name']}** [先攻: {entry['initiative']}]"
        
        # Stats 資訊
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
        
        # 狀態效果 (支援 dict 和 list)
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



def get_entry_names(channel_id):
    """
    取得所有角色名稱列表
    
    Args:
        channel_id: 頻道 ID
    
    Returns:
        list: 角色名稱列表
    """
    tracker = shared_state.get_tracker(channel_id)
    return [entry["name"] for entry in tracker["entries"]]


def reroll_all_initiative(channel_id):
    """
    全員重骰先攻
    使用角色上次的公式，若無則先攻設為 0
    
    Args:
        channel_id: 頻道 ID
    
    Returns:
        list: [(角色名, 舊先攻, 新先攻, 擲骰詳情), ...]
    """
    tracker = shared_state.get_tracker(channel_id)
    results = []
    
    for entry in tracker["entries"]:
        old_init = entry["initiative"]
        formula = entry.get("last_formula")
        
        if formula:
            try:
                total, dice_rolls = parse_and_roll(formula)
                
                # 生成擲骰詳情
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
                # 公式解析錯誤，設為 0
                entry["initiative"] = 0
                entry["roll_detail"] = "0 (公式錯誤)"
                results.append((entry["name"], old_init, 0, f"0 (公式錯誤: {e})"))
        else:
            # 無公式，設為 0
            entry["initiative"] = 0
            entry["roll_detail"] = "0"
            results.append((entry["name"], old_init, 0, "0 (無公式)"))
    
    # 重新排序
    sort_entries(channel_id)
    save_tracker()
    
    log_message(f"⚔️ 先攻表: 全員重骰完成 ({len(results)} 位角色)")
    return results



def get_favorite_dice_display(channel_id):
    """
    生成角色常用骰顯示文字
    
    Returns:
        str: 格式化的常用骰區文字，若無任何常用骰則返回 None
    """
    tracker = shared_state.get_tracker(channel_id)
    
    if not tracker["entries"]:
        return None
    
    lines = ["🎲 **常用骰快捷區**", "━" * 30]
    has_any_dice = False
    
    # 檢查是否有鎖定角色
    target = get_selected_character(channel_id)
    
    for entry in tracker["entries"]:
        # 若有鎖定角色，只顯示該角色與 GM
        if target and entry["name"] != target and entry["name"] != "GM":
            continue
            
        dice = entry.get("favorite_dice", {})
        if dice:
            has_any_dice = True
            # 只顯示前 5 個以避免過長
            dice_names = list(dice.keys())[:5]
            dice_list = " | ".join(f"`{name}`" for name in dice_names)
            if len(dice) > 5:
                dice_list += " ..."
            lines.append(f"**{entry['name']}**: {dice_list}")
        # 若無常用骰，不顯示該角色 (根據需求)
            
    lines.append("━" * 30)
    
    return "\n".join(lines) if has_any_dice else None


