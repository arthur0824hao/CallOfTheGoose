"""
共享狀態模組，用於儲存Bot共享的全局狀態變數，避免不同模組間的循環導入問題
"""

import uuid

# 播放狀態
current_page = 1
selected_song_index = ""
last_page = 1
last_selected_number = 1
is_fading_out = False

# 播放控制標記
current_operation = None  # 當前操作類型: 'playing', 'switching', 'stopping', None
current_song_title = None  # 當前正在處理的歌曲標題
stop_reason = None  # 停止原因: 'manual'(手動切換), 'finished'(自然結束), None
current_operation_id = None  # 當前操作的唯一ID

# 播放模式，預設「循環播放清單」
playback_mode = "循環播放清單"

# YouTube cookies 路徑，供下載時使用
youtube_cookies_path = None  # 預設為 None，可在 config/cookies_config.py 中設定

# 多歌單系統
current_musicsheet = "default"  # 目前使用的歌單名稱

# 操作ID生成器
def generate_operation_id():
    """生成唯一操作ID"""
    return str(uuid.uuid4())

# 先攻表狀態 (多頻道支援)
# 以頻道 ID 為 key 的 dict 結構
initiative_trackers = {}  # {channel_id_str: tracker_data}

# 先攻表 UI 訊息追蹤 (用於編輯訊息而非發送新訊息)
# {channel_id_str: {"tracker_msg": Message, "dice_msg": Message}}
initiative_messages = {}

# 向後相容：舊的單一先攻表結構 (僅供資料遷移用)
initiative_tracker = {
    "entries": [],
    "current_round": 1,
    "current_index": 0,
    "is_active": False
}


def get_tracker(channel_id):
    """
    取得指定頻道的先攻表，若不存在則創建
    
    Args:
        channel_id: 頻道 ID (int 或 str)
    
    Returns:
        dict: 該頻道的先攻表資料
    """
    channel_id = str(channel_id)  # 統一轉為字串
    if channel_id not in initiative_trackers:
        initiative_trackers[channel_id] = {
            "entries": [],
            "current_round": 1,
            "current_index": 0,
            "is_active": False
        }
    return initiative_trackers[channel_id]


def create_empty_tracker():
    """建立空的先攻表結構 (供擴展用)"""
    return {
        "entries": [],
        "current_round": 1,
        "current_index": 0,
        "is_active": False
    }


# 角色資料結構範例:
# {
#     "name": str,           # 角色名稱
#     "initiative": int,     # 先攻值
#     "roll_detail": str,    # 擲骰詳情 (例如 "[15] + 5 = 20")
#     "hp": int,             # 生命值
#     "elements": int,       # 剩餘元素
#     "atk": int,            # 攻擊等級
#     "def_": int,           # 防禦等級 (避免與 Python 關鍵字衝突)
#     "status_effects": {},  # 狀態效果 (鍵值對)
#     "favorite_dice": {}    # 常用骰 (名稱:公式)
# }
