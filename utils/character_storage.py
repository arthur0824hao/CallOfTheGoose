"""
全域角色儲存模組
負責讀寫 data/characters.json，提供跨頻道的角色保存與讀取功能
"""
import json
import os
import asyncio
from utils import shared_state
from utils.music import log_message

CHAR_FILE_PATH = "data/characters.json"

def _ensure_data_dir():
    """確保資料目錄存在"""
    os.makedirs(os.path.dirname(CHAR_FILE_PATH), exist_ok=True)

def _load_all_characters_sync():
    """讀取所有角色 (同步底層函數)"""
    if not os.path.exists(CHAR_FILE_PATH):
        return {}
    try:
        with open(CHAR_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log_message(f"❌ 讀取角色庫失敗: {e}")
        return {}

def _save_all_characters_sync(data):
    """儲存所有角色 (同步底層函數)"""
    _ensure_data_dir()
    try:
        with open(CHAR_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_message(f"❌ 儲存角色庫失敗: {e}")

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
    async with shared_state.character_lock:
        all_chars = _load_all_characters_sync()
        
        # 如果角色不存在，初始化基本結構
        if name not in all_chars:
            all_chars[name] = {
                "stats": {},
                "favorite_dice": {},
                "initiative_formula": None
            }
        
        target = all_chars[name]
        
        # 1. 基礎數值 (HP, Elements, ATK, DEF)
        if 'stats' in selected_fields:
            target["stats"] = {
                "hp": char_data.get("hp"),
                "elements": char_data.get("elements"),
                "atk": char_data.get("atk"),
                "def_": char_data.get("def_")
            }
            
        # 2. 常用骰
        if 'dice' in selected_fields:
            target["favorite_dice"] = char_data.get("favorite_dice", {}).copy()
            
        # 3. 先攻公式
        if 'formula' in selected_fields:
            target["initiative_formula"] = char_data.get("last_formula")
            
        _save_all_characters_sync(all_chars)
        log_message(f"💾 全域角色庫: 已儲存 {name} (欄位: {selected_fields})")
        return True

async def get_character(name: str):
    """取得指定角色的資料"""
    async with shared_state.character_lock:
        all_chars = _load_all_characters_sync()
        return all_chars.get(name)

async def get_all_names():
    """取得所有角色名稱列表"""
    async with shared_state.character_lock:
        all_chars = _load_all_characters_sync()
        return list(all_chars.keys())

async def delete_character(name: str):
    """刪除指定角色"""
    async with shared_state.character_lock:
        all_chars = _load_all_characters_sync()
        if name in all_chars:
            del all_chars[name]
            _save_all_characters_sync(all_chars)
            log_message(f"🗑️ 全域角色庫: 已刪除 {name}")
            return True
        return False
