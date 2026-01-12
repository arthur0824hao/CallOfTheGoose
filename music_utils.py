import os
import json
import re
import glob
import asyncio
import yt_dlp
import datetime
import traceback
import io
import threading
from yt_dlp.utils import sanitize_filename
from pydub import AudioSegment
from fuzzywuzzy import fuzz
import shared_state  # 添加缺少的import，修復下一首按鈕錯誤

# 全局常量
DEBUG_MODE = True
LOG_DIR = "logs"
LOG_FILE_PATH = os.path.join(LOG_DIR, "log.txt")
MUSICSHEET_BASE_DIR = "musicsheet"
SHEETS_CONFIG_PATH = os.path.join(MUSICSHEET_BASE_DIR, "sheets.json")
SONG_DIR = "song/"
QUEUE_PAGE_SIZE = 10

# ============================================
# 歌單路徑管理
# ============================================

def get_musicsheet_path(sheet_name=None):
    """取得指定歌單的 musicsheet.json 路徑"""
    if sheet_name is None:
        sheet_name = shared_state.current_musicsheet
    return os.path.join(MUSICSHEET_BASE_DIR, sheet_name, "musicsheet.json")

def get_current_musicsheet_path():
    """取得目前使用的 musicsheet.json 路徑"""
    return get_musicsheet_path(shared_state.current_musicsheet)

# 為了向後相容，保留 MUSIC_SHEET_PATH 但改為動態屬性
class _DynamicPath:
    @property
    def MUSIC_SHEET_PATH(self):
        return get_current_musicsheet_path()
    
_dynamic = _DynamicPath()

# ============================================
# 歌單清單管理
# ============================================

def load_sheets_config():
    """讀取歌單清單設定"""
    if not os.path.exists(SHEETS_CONFIG_PATH):
        # 建立預設設定
        default_config = {
            "current": "default",
            "sheets": [
                {"name": "default", "display_name": "預設"}
            ]
        }
        os.makedirs(MUSICSHEET_BASE_DIR, exist_ok=True)
        with open(SHEETS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config
    
    with open(SHEETS_CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"current": "default", "sheets": [{"name": "default", "display_name": "預設"}]}

def save_sheets_config(config):
    """儲存歌單清單設定"""
    os.makedirs(MUSICSHEET_BASE_DIR, exist_ok=True)
    with open(SHEETS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def list_musicsheets():
    """列出所有歌單"""
    config = load_sheets_config()
    return config.get("sheets", [])

def create_musicsheet(name, display_name=None):
    """建立新歌單"""
    config = load_sheets_config()
    
    # 檢查是否已存在
    if any(s["name"] == name for s in config["sheets"]):
        return False, "歌單已存在"
    
    # 建立資料夾和空的 musicsheet.json
    sheet_dir = os.path.join(MUSICSHEET_BASE_DIR, name)
    os.makedirs(sheet_dir, exist_ok=True)
    
    sheet_path = os.path.join(sheet_dir, "musicsheet.json")
    with open(sheet_path, "w", encoding="utf-8") as f:
        json.dump({"songs": []}, f, ensure_ascii=False, indent=2)
    
    # 更新設定
    config["sheets"].append({
        "name": name,
        "display_name": display_name or name
    })
    save_sheets_config(config)
    
    log_message(f"📁 新增歌單: {name}")
    return True, "歌單已建立"

def delete_musicsheet(name):
    """刪除歌單"""
    if name == "default":
        return False, "無法刪除預設歌單"
    
    config = load_sheets_config()
    
    # 檢查是否存在
    if not any(s["name"] == name for s in config["sheets"]):
        return False, "歌單不存在"
    
    # 如果正在使用這個歌單，切換到 default
    if shared_state.current_musicsheet == name:
        shared_state.current_musicsheet = "default"
        config["current"] = "default"
    
    # 移除設定
    config["sheets"] = [s for s in config["sheets"] if s["name"] != name]
    save_sheets_config(config)
    
    # 刪除資料夾 (可選，這裡只移除設定不刪檔案)
    log_message(f"🗑️ 刪除歌單: {name}")
    return True, "歌單已刪除"

def switch_musicsheet(name):
    """切換歌單"""
    config = load_sheets_config()
    
    # 檢查是否存在
    if not any(s["name"] == name for s in config["sheets"]):
        return False, "歌單不存在"
    
    shared_state.current_musicsheet = name
    config["current"] = name
    save_sheets_config(config)
    
    log_message(f"🔄 切換歌單: {name}")
    return True, f"已切換到歌單: {name}"

def get_sheet_display_name(name):
    """取得歌單顯示名稱"""
    config = load_sheets_config()
    for sheet in config["sheets"]:
        if sheet["name"] == name:
            return sheet.get("display_name", name)
    return name

def rename_musicsheet(old_name, new_display_name):
    """重命名歌單顯示名稱"""
    if old_name == "default" and new_display_name != "預設":
        pass  # 可以改 default 的顯示名稱
    
    config = load_sheets_config()
    
    for sheet in config["sheets"]:
        if sheet["name"] == old_name:
            sheet["display_name"] = new_display_name
            save_sheets_config(config)
            log_message(f"✏️ 重命名歌單: {old_name} → {new_display_name}")
            return True, "歌單已重命名"
    
    return False, "歌單不存在"

# ============================================
# 初始化歌單系統
# ============================================

def init_musicsheet_system():
    """初始化歌單系統，確保預設歌單存在"""
    config = load_sheets_config()
    shared_state.current_musicsheet = config.get("current", "default")
    
    # 確保預設歌單資料夾存在
    default_dir = os.path.join(MUSICSHEET_BASE_DIR, "default")
    os.makedirs(default_dir, exist_ok=True)
    
    default_sheet = os.path.join(default_dir, "musicsheet.json")
    if not os.path.exists(default_sheet):
        with open(default_sheet, "w", encoding="utf-8") as f:
            json.dump({"songs": []}, f, ensure_ascii=False, indent=2)
    
    log_message(f"🎵 歌單系統初始化完成，目前歌單: {shared_state.current_musicsheet}")


def log_message(message):
    """即時獲取最新時間並寫入 log.txt，確保記錄正確"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = os.path.join(LOG_DIR, "log.txt")

    # 重新獲取時間，確保每條記錄的時間都是最新的
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(log_filename, "a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} - {message}\n")

def log_error(error, ctx=None):
    """記錄錯誤資訊到 log.txt，包含控制台錯誤"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = os.path.join(LOG_DIR, "log.txt")

    error_info = traceback.format_exc()  # 抓取完整的錯誤堆疊資訊
    log_text = f"\n--- ERROR ---\nTime: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    if ctx:
        log_text += f"Command: {ctx.command}\nUser: {ctx.author}\nChannel: {ctx.channel}\n"

    log_text += f"Error: {error}\n{error_info}\n--- END ERROR ---\n"

    with open(log_filename, "a", encoding="utf-8") as log_file:
        log_file.write(log_text)

    print(log_text)  # 讓錯誤仍然顯示在控制台

def debug_log(message):
    """根據 `DEBUG_MODE` 決定是否 print"""
    if DEBUG_MODE:
        print(message)
    log_message(message)  # 一律記錄到 log

def load_musicsheet():
    """讀取 musicsheet，確保 `is_playing`、`is_previous`、`sanitized_title` 欄位存在"""
    path = get_current_musicsheet_path()
    if not os.path.exists(path):
        return {"songs": []}

    with open(path, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
            for song in data["songs"]:
                if "is_playing" not in song:
                    song["is_playing"] = False
                if "is_previous" not in song:
                    song["is_previous"] = False
                if "sanitized_title" not in song:
                    song["sanitized_title"] = sanitize_filename(song["title"])
            return data
        except json.JSONDecodeError:
            return {"songs": []}

def save_musicsheet(data):
    """儲存 musicsheet，確保 `sanitized_title` 存在"""
    for song in data["songs"]:
        if "sanitized_title" not in song:
            song["sanitized_title"] = sanitize_filename(song["title"])

    path = get_current_musicsheet_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def clean_string(text):
    """移除特殊字符與空白，只保留數字、字母、中文字"""
    return "".join(re.findall(r"[\w\u4e00-\u9fff]+", text)).lower()

def sanitize_filename(title):
    """清理檔名，確保與 `musicsheet.json` 一致"""
    title = title.replace("/", "_").replace("\\", "_")  # 避免路徑錯誤
    title = title.replace("?", "").replace(":", "").replace("|", "").replace("*", "").replace("\"", "").replace("<", "").replace(">", "")
    return title[:80]  # 限制長度，避免超過 Windows 限制

def find_downloaded_file(title):
    """在 `song/` 目錄內尋找匹配的音檔（全面忽略特殊字符與空白）"""
    cleaned_title = clean_string(title)
    song_files = os.listdir(SONG_DIR)

    best_match = None
    best_similarity = 0

    for file in song_files:
        cleaned_file = clean_string(file)
        
        # 完全匹配
        if cleaned_title == cleaned_file and file.lower().endswith((".mp3", ".m4a")):
            print(f"🔍 找到完全匹配音檔: {file}")
            return os.path.join(SONG_DIR, file)

        # 計算相似度
        similarity = fuzz.partial_ratio(cleaned_title, cleaned_file)
        if (similarity > best_similarity and file.lower().endswith((".mp3", ".m4a"))):
            best_similarity = similarity
            best_match = os.path.join(SONG_DIR, file)

    if best_match and best_similarity > 80:  # 相似度高於 80 才算匹配
        print(f"🔍 找到高相似度匹配: {best_match} (相似度: {best_similarity})")
        return best_match
    print("❌ 沒有找到匹配的音檔")
    return None

def convert_to_pcm(audio_file):
    """將音檔轉換為PCM格式，並返回一個可讀取的IO物件"""
    try:
        log_message(f"🔄 開始將 `{audio_file}` 轉換為PCM格式")
        
        # 使用pydub讀取音檔
        if (audio_file.lower().endswith('.mp3')):
            audio = AudioSegment.from_mp3(audio_file)
        elif (audio_file.lower().endswith('.m4a')):  # 修正拼寫錯誤 ends_with -> endswith
            audio = AudioSegment.from_file(audio_file, format="m4a")
        elif (audio_file.lower().endswith('.wav')):
            audio = AudioSegment.from_wav(audio_file)
        else:
            audio = AudioSegment.from_file(audio_file)
        
        # 優化轉換參數 - 統一採用更穩定的設定
        # - 固定採樣率為 48kHz (Discord 標準)
        # - 使用 16-bit 深度處理
        # - 設定標準立體聲
        # - 增加前置處理步驟包含正規化音量
        audio = audio.set_channels(2).set_frame_rate(48000).set_sample_width(2)
        
        # 正規化音量至適中水準 (-16dB LUFS)，避免爆音
        normalized_audio = audio.normalize(headroom=-16.0)

        # 建立一個較大的記憶體IO物件存放PCM資料，增加緩衝區大小
        pcm_io = io.BytesIO()
        normalized_audio.export(pcm_io, format="s16le", parameters=[
            "-ac", "2",
            "-ar", "48000",
            "-b:a", "320k",              # 提升位元率至 320 kbps
            "-bufsize", "8192k",         # 增大緩衝區至 8MB
            "-af", "aresample=resampler=soxr:precision=33"  # 使用 SoX 高品質重採樣
        ])
        pcm_io.seek(0)  # 讀寫指標歸零
        
        log_message(f"✅ `{audio_file}` PCM轉換成功，長度: {len(pcm_io.getbuffer())} 位元組")
        return pcm_io
    except Exception as e:
        log_message(f"❌ PCM轉換失敗: {e}")
        traceback_info = traceback.format_exc()
        log_message(f"轉換錯誤詳情: {traceback_info}")
        return None

class PCMStreamReader:
    """用於讀取PCM串流的類別，提供Discord.py需要的read()方法，增強緩衝處理"""
    def __init__(self, pcm_io):
        self.pcm_io = pcm_io
        self.buffer_size = 3840  # Discord.py 標準值
        self.closed = False
        self.read_count = 0      # 追蹤讀取次數
        
        # 讀取文件大小用於診斷
        try:
            self.total_bytes = len(pcm_io.getbuffer())
            log_message(f"📊 PCM數據大小: {self.total_bytes} 位元組")
        except:
            self.total_bytes = 0
            log_message(f"⚠ 無法獲取PCM數據大小")
    
    def read(self, frame_size=None):  # Discord.py 會提供 frame_size
        """讀取固定大小的PCM資料，兼容Discord.py調用方式"""
        if self.closed:
            return b''
        
        # 使用提供的 frame_size 或默認大小
        bytes_to_read = frame_size or self.buffer_size
        
        # 讀取數據
        chunk = self.pcm_io.read(bytes_to_read)
        self.read_count += 1
        
        # 檢查是否已讀完
        if not chunk:
            self.closed = True
            log_message(f"🔊 PCM音訊讀取完成: 共讀取 {self.read_count} 次")
            return b''
        
        # 每隔50次讀取記錄一次進度
        if self.read_count % 50 == 0:
            if self.total_bytes > 0:
                position = self.pcm_io.tell()
                progress = min(100, int(position * 100 / self.total_bytes))
                log_message(f"🔊 PCM播放進度: {progress}% (讀取 {self.read_count} 次)")
            else:
                log_message(f"🔊 PCM播放進行中: 已讀取 {self.read_count} 次")
        
        return chunk
    
    def cleanup(self):
        """清理資源"""
        self.closed = True
        self.pcm_io = None

async def download_song(url, title, ctx):
    """使用 yt-dlp 下載歌曲，確保 `musicsheet.json` 內 `sanitized_title` 正確"""
    sanitized_title = sanitize_filename(title)
    log_message(f"🔽 開始下載 `{title}`")
    
    # 確保下載目錄存在
    os.makedirs(SONG_DIR, exist_ok=True)
    
    # 引入 cookies 配置
    import shared_state
    
    # yt-dlp 下載選項 - 優先下載高品質音訊格式
    ydl_opts = {
        'format': 'bestaudio[ext=opus]/bestaudio[ext=m4a]/bestaudio/best',  # 優先選擇 Opus/M4A 高品質格式
        'outtmpl': os.path.join(SONG_DIR, f'{sanitized_title}.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'opus',  # Opus 編碼品質優於 MP3
            'preferredquality': '320',  # 提升至 320 kbps
        }],
        'quiet': True,
        'noplaylist': True,  # 避免下載整個播放清單
        'extractor_args': {
            'youtube': {
                'player_client': ['default']
            }
        },
    }
    
    # 如果存在 cookies 檔案，則加入設定
    if shared_state.youtube_cookies_path:
        log_message(f"🍪 使用 cookies 檔案進行下載: {shared_state.youtube_cookies_path}")
        ydl_opts['cookiefile'] = shared_state.youtube_cookies_path
    
    def run_download(url, opts):
        """在執行緒中執行下載"""
        if url is None:
            log_message(f"❌ 無法下載: URL為空")
            return False
            
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            log_message(f"❌ 下載失敗: {e}")
            return False

    # 使用執行緒執行下載
    download_thread = threading.Thread(target=run_download, args=(url, ydl_opts))
    download_thread.daemon = True
    download_thread.start()
    
    # 等待下載完成
    while download_thread.is_alive():
        await asyncio.sleep(1)
    
    # 檢查下載結果並更新 musicsheet.json
    downloaded_file = find_downloaded_file(title)
    musicsheet_data = load_musicsheet()
    
    for song in musicsheet_data["songs"]:
        if song["title"] == title:
            if downloaded_file:
                song["is_downloaded"] = True
                song["sanitized_title"] = sanitized_title
                log_message(f"✅ 下載完成: `{title}`")
            else:
                song["is_downloaded"] = False
                log_message(f"❌ `{title}` 下載後找不到對應檔案")
            break
    
    save_musicsheet(musicsheet_data)
    
    return downloaded_file

def check_audio_file(file_path):
    """檢查音樂檔案是否可播放"""
    if not file_path or not os.path.exists(file_path):
        log_message(f"❌ 檔案不存在: {file_path}")
        return False
        
    # 檢查檔案大小
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        log_message(f"❌ 檔案大小為0: {file_path}")
        return False
        
    # 檢查檔案是否可讀
    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)  # 讀取檔案頭
            
        # 簡單檢查檔案頭是否符合 MP3 或 M4A 格式
        if file_path.lower().endswith('.mp3') and not header.startswith(b'ID3') and not b'\xFF\xFB' in header:
            log_message(f"⚠️ 可能不是有效的 MP3 檔案: {file_path}")
            return False
            
        if file_path.lower().endswith('.m4a') and not b'ftyp' in header:
            log_message(f"⚠️ 可能不是有效的 M4A 檔案: {file_path}")
            return False
            
        log_message(f"✅ 檔案檢查通過: {file_path}")
        return True
    except Exception as e:
        log_message(f"❌ 檔案檢查時發生錯誤: {file_path}, {e}")
        return False

async def play_next(ctx):
    """根據播放模式選擇適當的下一首歌曲，確保機器人連回語音後自動播放"""
    # 生成新操作ID
    operation_id = shared_state.generate_operation_id()
    shared_state.current_operation_id = operation_id
    
    log_message(f"🎮 play_next 觸發 [操作ID: {operation_id[:8]}, 停止原因: {shared_state.stop_reason}]")
    voice_client = ctx.voice_client

    # 添加最大嘗試次數，防止無限迴圈
    if not hasattr(ctx, 'next_song_attempts'):
        ctx.next_song_attempts = 0
    
    # 如果已經嘗試太多次，則中止
    if ctx.next_song_attempts > 5:
        log_message("⚠️ 嘗試播放下一首歌曲次數過多，中止自動播放")
        ctx.next_song_attempts = 0  # 重置計數
        return
    
    ctx.next_song_attempts += 1

    # 確認播放模式
    current_mode = shared_state.playback_mode
    log_message(f"🎵 播放結束，根據模式「{current_mode}」選擇下一首 [ID: {operation_id[:8]}]")

    # 如果當前模式是「播完後待機」，則停止播放
    if current_mode == "播完後待機":
        log_message("⏸ 播放模式為「播完後待機」，停止播放")
        return

    # 如果仍在播放中，先停止
    if voice_client and voice_client.is_playing():
        log_message(f"⏹️ 停止當前播放，準備切換到下一首 [ID: {operation_id[:8]}]")
        # 設置為手動停止，避免觸發自動播放下一曲
        shared_state.stop_reason = "manual"
        voice_client.stop()
        await asyncio.sleep(1.5)  # 等待停止完成

    # 如果掉線，先重新連線
    if not voice_client or not voice_client.is_connected():
        log_message("⚠ 機器人未連接語音頻道，重新加入")
        try:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                voice_client = ctx.voice_client
            else:
                log_message("❌ 使用者未在語音頻道，無法重新加入")
                return
        except Exception as e:
            log_message(f"❌ 無法重新加入語音頻道: {e}")
            return

    musicsheet_data = load_musicsheet()
    song_list = musicsheet_data["songs"]

    if not song_list:
        log_message("⚠ 播放清單是空的，無法播放下一首")
        ctx.next_song_attempts = 0  # 重置計數
        return

    # 設置操作狀態
    shared_state.current_operation = 'switching'

    # 找出目前 is_playing=True 的歌曲索引
    current_index = next((i for i, song in enumerate(song_list) if song.get("is_playing")), None)

    if current_index is None:
        log_message("⚠ 無法取得當前播放歌曲，直接播放第一首")
        next_index = 0
    else:
        # 根據播放模式選擇下一首歌
        if current_mode == "單曲循環":
            next_index = current_index  # 單曲循環：重播同一首
        elif current_mode == "隨機播放":
            import random
            if len(song_list) > 1:
                next_index = random.randint(0, len(song_list) - 1)
                while next_index == current_index:
                    next_index = random.randint(0, len(song_list) - 1)
            else:
                next_index = 0
        else:  # 循環播放清單
            next_index = (current_index + 1) % len(song_list)

    next_song = song_list[next_index]
    log_message(f"🎵 下一首: `{next_song['title']}` [ID: {operation_id[:8]}]")
    
    # 檢查檔案是否存在，若不存在則嘗試其他歌曲
    song_file = find_downloaded_file(next_song["title"])
    
    if not song_file and not next_song.get("url"):
        log_message(f"⚠ 找不到檔案，跳過: `{next_song['title']}`")
        
        # 從播放清單中移除這首歌
        log_message(f"🗑️ 從播放清單移除找不到檔案的歌曲: `{next_song['title']}`")
        musicsheet_data["songs"] = [song for song in musicsheet_data["songs"] if song["title"] != next_song["title"]]
        save_musicsheet(musicsheet_data)
        
        # 清除操作狀態
        shared_state.current_operation = None
        shared_state.current_song_title = None
        
        # 短暫等待後遞迴調用自己，嘗試下一首
        await asyncio.sleep(0.5)
        return await play_next(ctx)
    
    # 呼叫 play 命令播放下一首
    try:
        await asyncio.sleep(0.5)  # 短暫等待
        
        # 檢查操作ID是否已變更
        if shared_state.current_operation_id != operation_id:
            log_message(f"⚠️ 操作ID已變更，跳過自動播放 [舊ID: {operation_id[:8]}, 新ID: {shared_state.current_operation_id[:8]}]")
            return
            
        play_cmd = ctx.bot.get_command("play")
        if play_cmd:
            ctx.next_song_attempts = 0  # 重置計數，成功找到了可播放的歌曲
            # 設置為手動模式，避免再次觸發自動播放
            shared_state.stop_reason = "manual"
            await ctx.invoke(play_cmd, title=next_song["title"])
        else:
            log_message("❌ 找不到播放命令")
            # 清除操作狀態
            shared_state.current_operation = None
            shared_state.current_song_title = None
    except Exception as e:
        log_message(f"❌ 呼叫play_cmd失敗: {e}")
        
        # 重置歌曲狀態
        for song in musicsheet_data["songs"]:
            song["is_playing"] = False
        save_musicsheet(musicsheet_data)
        
        # 清除操作狀態
        shared_state.current_operation = None
        shared_state.current_song_title = None
        
        await asyncio.sleep(0.5)
        await play_next(ctx)

def get_next_index(musicsheet_data):
    """計算下一個可用的 `a.b` 座標"""
    used_indexes = {song["index"] for song in musicsheet_data["songs"]}

    a = 1
    while True:
        for b in range(1, 11):
            new_index = f"{a}.{b}"
            if new_index not in used_indexes:
                return new_index
        a += 1

def reorganize_musicsheet(musicsheet_data):
    """重新整理 `musicsheet.json` 內的 `index`，確保索引連續"""
    new_songs = []
    current_a, current_b = 1, 1

    try:
        # 確保索引為 `a.b` 格式並排序
        musicsheet_data["songs"].sort(key=lambda x: tuple(map(int, x["index"].split("."))))
    except Exception as e:
        debug_log(f"⚠️ DEBUG: 索引整理失敗 -> {e}")

    for song in musicsheet_data["songs"]:
        song["index"] = f"{current_a}.{current_b}"
        new_songs.append(song)

        current_b += 1
        if current_b > 10:
            current_a += 1
            current_b = 1

    musicsheet_data["songs"] = new_songs

def remove_song(title):
    """刪除 `musicsheet.json` 內的歌曲，並同步刪除 `song/` 內的檔案（如果已下載）"""
    musicsheet_data = load_musicsheet()
    song_to_remove = next((song for song in musicsheet_data["songs"] if song["title"] == title), None)

    if not song_to_remove:
        log_message(f"❌ `{title}` 不在播放清單內")
        return False

    # 刪除 `musicsheet.json` 內的歌曲
    musicsheet_data["songs"] = [song for song in musicsheet_data["songs"] if song["title"] != title]
    reorganize_musicsheet(musicsheet_data)  # 重新整理索引
    save_musicsheet(musicsheet_data)

    log_message(f"✅ `{title}` 已從播放清單移除")

    # 刪除 `song/` 內對應檔案（如果 `is_downloaded`）
    if song_to_remove.get("is_downloaded", False):
        song_file = find_downloaded_file(title)
        if song_file:
            try:
                os.remove(song_file)
                log_message(f"🗑️ `{song_file}` 已刪除")
            except Exception as e:
                log_message(f"⚠ 無法刪除 `{song_file}`，錯誤: {e}")

    return True

def update_previous_song(current_song):
    """更新 `is_previous` 屬性，**僅 `隨機播放` 模式適用**"""
    musicsheet_data = load_musicsheet()

    # 導入共享狀態模組獲取播放模式
    import shared_state

    # 僅隨機播放模式才更新 `is_previous`
    if shared_state.playback_mode != "隨機播放":  # 使用共享狀態代替直接引用bot
        debug_log("⚠️ `update_previous_song` 只在 `隨機播放` 模式更新，其他模式無變更")
        return  

    for song in musicsheet_data["songs"]:
        song["is_previous"] = (song["title"] == current_song["title"])  # 只標記上一首

    debug_log(f"🔄 `is_previous` 已更新，上一首: `{current_song['title']}`")
    save_musicsheet(musicsheet_data)  # 儲存更新

def delete_unlisted_songs():
    """刪除 `song/` 內不在 `musicsheet.json` 的 .mp3 檔案"""
    musicsheet_data = load_musicsheet()

    # 取得 `musicsheet.json` 內的所有歌曲標題
    valid_titles = {sanitize_filename(song["title"]) for song in musicsheet_data["songs"]}

    # 取得 `song/` 目錄內的所有 `.mp3` 檔案
    song_files = glob.glob(os.path.join(SONG_DIR, "*.mp3"))

    deleted_count = 0
    for file_path in song_files:
        file_name = os.path.basename(file_path)
        file_title, _ = os.path.splitext(file_name)  # 移除 `.mp3`

        # 如果這個檔案不在 `musicsheet.json` 內，刪除
        if file_title not in valid_titles:
            try:
                os.remove(file_path)
                log_message(f"🗑️ 刪除未在 `musicsheet.json` 內的檔案: {file_name}")
                deleted_count += 1
            except Exception as e:
                log_message(f"⚠ 無法刪除 `{file_name}`，錯誤: {e}")

    log_message(f"✅ 已刪除 {deleted_count} 個不在播放清單內的音樂檔案")

def scan_and_update_musicsheet():
    """掃描 `song/` 目錄，並更新 `musicsheet.json` 內 `is_downloaded`，新增未登記歌曲，並自動排除重複項"""
    path = get_current_musicsheet_path()
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump({"songs": []}, file)
    
    # 讀取現有的 musicsheet 數據
    with open(path, "r", encoding="utf-8") as file:
        try:
            musicsheet_data = json.load(file)
        except json.JSONDecodeError:
            musicsheet_data = {"songs": []}

    # 取得 `song/` 內所有 `.mp3` & `.m4a` 檔案名稱
    downloaded_files = {os.path.splitext(os.path.basename(f))[0]: f for f in glob.glob(os.path.join(SONG_DIR, "*.mp3"))}
    downloaded_files.update({os.path.splitext(os.path.basename(f))[0]: f for f in glob.glob(os.path.join(SONG_DIR, "*.m4a"))})

    # 標記已下載的歌曲
    registered_titles = set()
    removed_count = 0
    
    # 檢查現有歌曲的下載狀態
    for song in musicsheet_data["songs"]:
        sanitized_title = sanitize_filename(song["title"])
        song["is_downloaded"] = any(fuzz.partial_ratio(sanitized_title, key) > 85 for key in downloaded_files)
        
        # 添加已下載的歌曲到已登記清單
        if song["is_downloaded"]:
            registered_titles.add(sanitized_title)
        
        # 檢查並移除無效歌曲 (沒有檔案且無URL的歌曲)
        if not song["is_downloaded"] and not song.get("url"):
            log_message(f"🗑️ 移除無效歌曲: `{song['title']}` (無檔案且無URL)")
            musicsheet_data["songs"].remove(song)
            removed_count += 1
    
    # 加入 `song/` 內但未登記的歌曲
    new_songs = []
    for file_name, file_path in downloaded_files.items():
        sanitized_title = sanitize_filename(file_name)
        
        # 模糊比對，避免加入重複歌曲
        if any(fuzz.partial_ratio(sanitized_title, title) > 85 for title in registered_titles):
            continue
        
        new_song = {
            "title": file_name,  # 保留原始檔名
            "sanitized_title": sanitized_title,
            "is_downloaded": True,
            "url": None,  # 無法回溯 URL
            "musicsheet": shared_state.current_musicsheet,
            "index": get_next_index(musicsheet_data),
            "is_playing": False,
            "is_previous": False
        }
        new_songs.append(new_song)
    
    # 添加新歌曲到清單
    musicsheet_data["songs"].extend(new_songs)

    # 重新整理索引
    reorganize_musicsheet(musicsheet_data)

    # 儲存 `musicsheet.json`
    with open(path, "w", encoding="utf-8") as file:
        json.dump(musicsheet_data, file, ensure_ascii=False, indent=2)

    log_message(f"✅ `musicsheet.json` 已更新，新增 {len(new_songs)} 首歌曲，移除 {removed_count} 首無效歌曲")


