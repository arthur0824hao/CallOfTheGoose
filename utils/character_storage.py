"""
全域角色儲存模組 (PostgreSQL)
負責讀寫資料庫中的 characters 表
"""
import json
from utils.music import log_message
from utils.db import Database

async def save_character(name: str, char_data: dict, selected_fields: list):
    """
    儲存單一角色到全域資料庫
    
    Args:
        name: 角色名稱
        char_data: 來源資料 (從 initiative entry 來的 dict)
        selected_fields: 要儲存的欄位列表 ['stats', 'dice', 'formula']
        
    Returns:
        bool: 是否成功
    """
    # 1. 獲取現有數據
    existing_data = await get_character(name) or {
        "stats": {},
        "favorite_dice": {},
        "initiative_formula": None
    }
    
    target = existing_data
    
    # Update fields
    if 'stats' in selected_fields:
        target["stats"] = {
            "hp": char_data.get("hp"),
            "elements": char_data.get("elements"),
            "atk": char_data.get("atk"),
            "def_": char_data.get("def_")
        }
        
    if 'dice' in selected_fields:
        target["favorite_dice"] = char_data.get("favorite_dice", {}).copy()
        
    if 'formula' in selected_fields:
        target["initiative_formula"] = char_data.get("last_formula")
    
    # Upsert
    query = """
        INSERT INTO characters (name, data) VALUES ($1, $2)
        ON CONFLICT (name) DO UPDATE SET data = $2, updated_at = CURRENT_TIMESTAMP
    """
    try:
        await Database.execute(query, name, json.dumps(target))
        log_message(f"💾 全域角色庫: 已儲存 {name} (欄位: {selected_fields})")
        return True
    except Exception as e:
        log_message(f"❌ 儲存角色失敗: {e}")
        return False

async def get_character(name: str):
    """取得指定角色的資料"""
    query = "SELECT data FROM characters WHERE name = $1"
    try:
        data_str = await Database.fetchval(query, name)
        if data_str:
            return json.loads(data_str)
        return None
    except Exception as e:
        log_message(f"❌ 讀取角色失敗: {e}")
        return None

async def get_all_names():
    """取得所有角色名稱列表"""
    query = "SELECT name FROM characters ORDER BY name"
    try:
        rows = await Database.fetch(query)
        return [row['name'] for row in rows]
    except Exception as e:
        log_message(f"❌ 讀取角色列表失敗: {e}")
        return []

async def delete_character(name: str):
    """刪除指定角色"""
    query = "DELETE FROM characters WHERE name = $1"
    try:
        result = await Database.execute(query, name)
        # result format is typically "DELETE <count>"
        if result == "DELETE 0":
            return False
        log_message(f"🗑️ 全域角色庫: 已刪除 {name}")
        return True
    except Exception as e:
        log_message(f"❌ 刪除角色失敗: {e}")
        return False
