"""
Comprehensive test suite for utils/music.py

Tests cover:
- Logging functions: log_message, log_error, debug_log
- Musicsheet operations: load, save, clean_string, sanitize_filename
- File operations: find_downloaded_file, check_audio_file
- PCM conversion: convert_to_pcm, PCMStreamReader
- Download: download_song (with mocked yt_dlp)
- Playback: play_next (with mocked discord context)
- Musicsheet management: create, delete, switch, rename
- Helper functions: get_next_index, reorganize_musicsheet, remove_song, etc.

CRITICAL MOCKING:
- yt_dlp: No real network calls
- discord.FFmpegPCMAudio: Mocked
- discord.PCMVolumeTransformer: Mocked
- asyncio.sleep: Mocked to speed up tests
- pydub.AudioSegment: Mocked
- fuzzywuzzy.fuzz: Mocked
"""

import pytest
import asyncio
import json
import os
import tempfile
import io
from unittest.mock import (
    patch, MagicMock, AsyncMock, mock_open, call, ANY
)
from pathlib import Path

# Import the module under test
import utils.music as music
import utils.shared_state as shared_state


# ==================== Fixtures ====================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_log_dir(temp_dir, monkeypatch):
    """Mock LOG_DIR to use temp directory."""
    log_dir = os.path.join(temp_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    monkeypatch.setattr(music, "LOG_DIR", log_dir)
    monkeypatch.setattr(music, "LOG_FILE_PATH", os.path.join(log_dir, "log.txt"))
    return log_dir


@pytest.fixture
def mock_song_dir(temp_dir, monkeypatch):
    """Mock SONG_DIR to use temp directory."""
    song_dir = os.path.join(temp_dir, "song")
    os.makedirs(song_dir, exist_ok=True)
    monkeypatch.setattr(music, "SONG_DIR", song_dir)
    return song_dir


@pytest.fixture
def mock_musicsheet_path(temp_dir, monkeypatch):
    """Mock MUSIC_SHEET_PATH to use temp directory."""
    musicsheet_dir = os.path.join(temp_dir, "musicsheet", "default")
    os.makedirs(musicsheet_dir, exist_ok=True)
    musicsheet_path = os.path.join(musicsheet_dir, "musicsheet.json")
    monkeypatch.setattr(music, "MUSIC_SHEET_PATH", musicsheet_path)
    monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", os.path.join(temp_dir, "musicsheet"))
    monkeypatch.setattr(
        music, "MUSICSHEET_INDEX_PATH",
        os.path.join(temp_dir, "musicsheet", "sheets_index.json")
    )
    return musicsheet_path


@pytest.fixture
def mock_discord_context():
    """Mock Discord context object."""
    ctx = AsyncMock()
    ctx.send = AsyncMock()
    ctx.author = MagicMock()
    ctx.author.id = 123456789
    ctx.author.voice = MagicMock()
    ctx.author.voice.channel = AsyncMock()
    ctx.author.voice.channel.connect = AsyncMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 987654321
    ctx.channel = MagicMock()
    ctx.channel.id = 555555555
    ctx.voice_client = AsyncMock()
    ctx.voice_client.is_playing = MagicMock(return_value=False)
    ctx.voice_client.is_connected = MagicMock(return_value=True)
    ctx.voice_client.play = MagicMock()
    ctx.voice_client.stop = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.get_command = MagicMock(return_value=AsyncMock())
    ctx.invoke = AsyncMock()
    ctx.next_song_attempts = 0
    return ctx


@pytest.fixture
def sample_musicsheet():
    """Sample musicsheet data."""
    return {
        "songs": [
            {
                "title": "Song 1",
                "url": "https://example.com/song1",
                "is_downloaded": True,
                "sanitized_title": "Song 1",
                "musicsheet": "default",
                "index": "1.1",
                "is_playing": False,
                "is_previous": False
            },
            {
                "title": "Song 2",
                "url": "https://example.com/song2",
                "is_downloaded": False,
                "sanitized_title": "Song 2",
                "musicsheet": "default",
                "index": "1.2",
                "is_playing": False,
                "is_previous": False
            }
        ]
    }


@pytest.fixture
def reset_shared_state():
    """Reset shared_state to defaults."""
    original_state = {
        "current_page": shared_state.current_page,
        "selected_song_index": shared_state.selected_song_index,
        "playback_mode": shared_state.playback_mode,
        "current_operation": shared_state.current_operation,
        "current_song_title": shared_state.current_song_title,
        "stop_reason": shared_state.stop_reason,
        "current_operation_id": shared_state.current_operation_id,
    }
    yield
    # Restore
    shared_state.current_page = original_state["current_page"]
    shared_state.selected_song_index = original_state["selected_song_index"]
    shared_state.playback_mode = original_state["playback_mode"]
    shared_state.current_operation = original_state["current_operation"]
    shared_state.current_song_title = original_state["current_song_title"]
    shared_state.stop_reason = original_state["stop_reason"]
    shared_state.current_operation_id = original_state["current_operation_id"]


# ==================== Logging Tests ====================

class TestLogging:
    """Test logging functions."""

    def test_log_message(self, mock_log_dir):
        """Test log_message writes to file."""
        music.log_message("Test message")
        log_file = os.path.join(mock_log_dir, "log.txt")
        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Test message" in content

    def test_log_message_creates_dir(self, temp_dir, monkeypatch):
        """Test log_message creates LOG_DIR if it doesn't exist."""
        log_dir = os.path.join(temp_dir, "new_logs")
        monkeypatch.setattr(music, "LOG_DIR", log_dir)
        monkeypatch.setattr(music, "LOG_FILE_PATH", os.path.join(log_dir, "log.txt"))
        
        music.log_message("Test")
        assert os.path.exists(log_dir)

    def test_log_error(self, mock_log_dir):
        """Test log_error writes error info."""
        try:
            raise ValueError("Test error")
        except ValueError:
            music.log_error("Test error occurred")
        
        log_file = os.path.join(mock_log_dir, "log.txt")
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "ERROR" in content
            assert "Test error occurred" in content

    def test_log_error_with_context(self, mock_log_dir, mock_discord_context):
        """Test log_error includes context info."""
        try:
            raise ValueError("Test error")
        except ValueError:
            music.log_error("Error with context", mock_discord_context)
        
        log_file = os.path.join(mock_log_dir, "log.txt")
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "ERROR" in content

    @patch("builtins.print")
    def test_debug_log_prints_when_debug_mode(self, mock_print, mock_log_dir):
        """Test debug_log prints when DEBUG_MODE is True."""
        original_debug = music.DEBUG_MODE
        music.DEBUG_MODE = True
        try:
            music.debug_log("Debug message")
            mock_print.assert_called_with("Debug message")
        finally:
            music.DEBUG_MODE = original_debug

    @patch("builtins.print")
    def test_debug_log_no_print_when_debug_disabled(self, mock_print, mock_log_dir):
        """Test debug_log doesn't print when DEBUG_MODE is False."""
        original_debug = music.DEBUG_MODE
        music.DEBUG_MODE = False
        try:
            music.debug_log("Debug message")
            mock_print.assert_not_called()
        finally:
            music.DEBUG_MODE = original_debug


# ==================== Musicsheet Tests ====================

class TestMusicsheetOperations:
    """Test musicsheet loading, saving, and manipulation."""

    def test_load_musicsheet_creates_default(self, mock_musicsheet_path):
        """Test load_musicsheet creates default structure if file doesn't exist."""
        result = music.load_musicsheet()
        assert result == {"songs": []}

    def test_load_musicsheet_existing(self, mock_musicsheet_path, sample_musicsheet):
        """Test load_musicsheet reads existing file."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        result = music.load_musicsheet()
        assert len(result["songs"]) == 2
        assert result["songs"][0]["title"] == "Song 1"

    def test_load_musicsheet_adds_missing_fields(self, mock_musicsheet_path):
        """Test load_musicsheet adds missing fields."""
        incomplete_data = {
            "songs": [
                {"title": "Song 1", "url": "http://example.com"}
            ]
        }
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(incomplete_data, f)
        
        result = music.load_musicsheet()
        song = result["songs"][0]
        assert "is_playing" in song
        assert "is_previous" in song
        assert "sanitized_title" in song

    def test_load_musicsheet_corrupted_file(self, mock_musicsheet_path, mock_log_dir):
        """Test load_musicsheet handles corrupted JSON."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")
        
        result = music.load_musicsheet()
        assert result == {"songs": []}
        
        # Check backup was created
        backup_path = mock_musicsheet_path + ".corrupted"
        assert os.path.exists(backup_path)

    def test_save_musicsheet(self, mock_musicsheet_path, sample_musicsheet):
        """Test save_musicsheet writes to file."""
        music.save_musicsheet(sample_musicsheet)
        
        with open(mock_musicsheet_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        
        assert len(saved["songs"]) == 2
        assert saved["songs"][0]["title"] == "Song 1"

    def test_save_musicsheet_adds_sanitized_title(self, mock_musicsheet_path):
        """Test save_musicsheet adds sanitized_title if missing."""
        data = {
            "songs": [
                {"title": "Song/With\\Special?Chars"}
            ]
        }
        music.save_musicsheet(data)
        
        with open(mock_musicsheet_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        
        assert "sanitized_title" in saved["songs"][0]

    def test_clean_string(self):
        """Test clean_string removes special characters."""
        assert music.clean_string("Hello World!") == "helloworld"
        assert music.clean_string("Test-123_ABC") == "test123_abc"  # Underscore is kept
        assert music.clean_string("中文測試") == "中文測試"

    def test_sanitize_filename(self):
        """Test sanitize_filename removes invalid characters."""
        result = music.sanitize_filename("Song/With\\Invalid?Chars:*|\"<>")
        assert "/" not in result
        assert "\\" not in result
        assert "?" not in result
        assert ":" not in result

    def test_sanitize_filename_length_limit(self):
        """Test sanitize_filename limits length to 80 chars."""
        long_name = "a" * 100
        result = music.sanitize_filename(long_name)
        assert len(result) <= 80


# ==================== File Operations Tests ====================

class TestFileOperations:
    """Test file finding and validation."""

    @patch("utils.music.fuzz.partial_ratio")
    def test_find_downloaded_file_exact_match(self, mock_fuzz, mock_song_dir):
        """Test find_downloaded_file with exact match."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        result = music.find_downloaded_file("Song 1")
        assert result == test_file

    @patch("utils.music.fuzz.partial_ratio")
    def test_find_downloaded_file_fuzzy_match(self, mock_fuzz, mock_song_dir):
        """Test find_downloaded_file with fuzzy matching."""
        mock_fuzz.return_value = 85
        test_file = os.path.join(mock_song_dir, "Song One.mp3")
        Path(test_file).touch()
        
        result = music.find_downloaded_file("Song 1")
        assert result == test_file

    def test_find_downloaded_file_not_found(self, mock_song_dir):
        """Test find_downloaded_file returns None when not found."""
        result = music.find_downloaded_file("Nonexistent Song")
        assert result is None

    @patch("utils.music.fuzz.partial_ratio")
    def test_find_downloaded_file_ignores_non_audio(self, mock_fuzz, mock_song_dir):
        """Test find_downloaded_file ignores non-audio files."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.txt")
        Path(test_file).touch()
        
        result = music.find_downloaded_file("Song 1")
        assert result is None

    def test_check_audio_file_valid_mp3(self, mock_song_dir):
        """Test check_audio_file validates MP3 files."""
        test_file = os.path.join(mock_song_dir, "test.mp3")
        # Create a file with MP3 header
        with open(test_file, "wb") as f:
            f.write(b"ID3" + b"\x00" * 13)  # MP3 header
        
        result = music.check_audio_file(test_file)
        assert result is True

    def test_check_audio_file_nonexistent(self):
        """Test check_audio_file returns False for nonexistent file."""
        result = music.check_audio_file("/nonexistent/file.mp3")
        assert result is False

    def test_check_audio_file_empty(self, mock_song_dir):
        """Test check_audio_file returns False for empty file."""
        test_file = os.path.join(mock_song_dir, "empty.mp3")
        Path(test_file).touch()
        
        result = music.check_audio_file(test_file)
        assert result is False

    def test_check_audio_file_invalid_header(self, mock_song_dir):
        """Test check_audio_file detects invalid MP3 header."""
        test_file = os.path.join(mock_song_dir, "invalid.mp3")
        with open(test_file, "wb") as f:
            f.write(b"INVALID" + b"\x00" * 10)
        
        result = music.check_audio_file(test_file)
        assert result is False


# ==================== PCM Conversion Tests ====================

class TestPCMConversion:
    """Test PCM conversion and streaming."""

    @patch("utils.music.AudioSegment")
    def test_convert_to_pcm_mp3(self, mock_audio_segment, mock_song_dir, mock_log_dir):
        """Test convert_to_pcm with MP3 file."""
        # Mock AudioSegment
        mock_audio = MagicMock()
        mock_audio.set_channels = MagicMock(return_value=mock_audio)
        mock_audio.set_frame_rate = MagicMock(return_value=mock_audio)
        mock_audio.set_sample_width = MagicMock(return_value=mock_audio)
        mock_audio.normalize = MagicMock(return_value=mock_audio)
        mock_audio.export = MagicMock()
        
        mock_audio_segment.from_mp3 = MagicMock(return_value=mock_audio)
        
        test_file = os.path.join(mock_song_dir, "test.mp3")
        Path(test_file).touch()
        
        result = music.convert_to_pcm(test_file)
        assert result is not None

    @patch("utils.music.AudioSegment")
    def test_convert_to_pcm_m4a(self, mock_audio_segment, mock_song_dir, mock_log_dir):
        """Test convert_to_pcm with M4A file."""
        mock_audio = MagicMock()
        mock_audio.set_channels = MagicMock(return_value=mock_audio)
        mock_audio.set_frame_rate = MagicMock(return_value=mock_audio)
        mock_audio.set_sample_width = MagicMock(return_value=mock_audio)
        mock_audio.normalize = MagicMock(return_value=mock_audio)
        mock_audio.export = MagicMock()
        
        mock_audio_segment.from_file = MagicMock(return_value=mock_audio)
        
        test_file = os.path.join(mock_song_dir, "test.m4a")
        Path(test_file).touch()
        
        result = music.convert_to_pcm(test_file)
        assert result is not None

    @patch("utils.music.AudioSegment")
    def test_convert_to_pcm_error(self, mock_audio_segment, mock_song_dir, mock_log_dir):
        """Test convert_to_pcm handles errors."""
        mock_audio_segment.from_mp3 = MagicMock(side_effect=Exception("Test error"))
        
        test_file = os.path.join(mock_song_dir, "test.mp3")
        Path(test_file).touch()
        
        result = music.convert_to_pcm(test_file)
        assert result is None

    def test_pcm_stream_reader_read(self):
        """Test PCMStreamReader.read() method."""
        pcm_data = b"test pcm data" * 100
        pcm_io = io.BytesIO(pcm_data)
        
        reader = music.PCMStreamReader(pcm_io)
        chunk = reader.read(100)
        
        assert len(chunk) == 100
        assert chunk == pcm_data[:100]

    def test_pcm_stream_reader_read_all(self):
        """Test PCMStreamReader reads all data."""
        pcm_data = b"test" * 10
        pcm_io = io.BytesIO(pcm_data)
        
        reader = music.PCMStreamReader(pcm_io)
        all_data = b""
        while True:
            chunk = reader.read(10)
            if not chunk:
                break
            all_data += chunk
        
        assert all_data == pcm_data

    def test_pcm_stream_reader_closed(self):
        """Test PCMStreamReader returns empty when closed."""
        pcm_io = io.BytesIO(b"test")
        reader = music.PCMStreamReader(pcm_io)
        reader.closed = True
        
        chunk = reader.read(10)
        assert chunk == b""

    def test_pcm_stream_reader_cleanup(self):
        """Test PCMStreamReader.cleanup()."""
        pcm_io = io.BytesIO(b"test")
        reader = music.PCMStreamReader(pcm_io)
        
        reader.cleanup()
        assert reader.closed is True
        assert reader.pcm_io is None


# ==================== Download Tests ====================

class TestDownloadSong:
    """Test song downloading with mocked yt_dlp."""

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    @patch("utils.music.threading.Thread")
    @patch("utils.music.yt_dlp.YoutubeDL")
    async def test_download_song_success(
        self, mock_ydl_class, mock_thread_class, mock_fuzz,
        mock_musicsheet_path, mock_song_dir, mock_log_dir,
        sample_musicsheet, mock_discord_context
    ):
        """Test download_song succeeds."""
        mock_fuzz.return_value = 100
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        mock_thread = MagicMock()
        mock_thread.is_alive = MagicMock(side_effect=[True, False])
        mock_thread_class.return_value = mock_thread
        
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=None)
        
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        result = await music.download_song("http://example.com", "Song 1", mock_discord_context)
        
        mock_thread_class.assert_called_once()

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    @patch("utils.music.threading.Thread")
    async def test_download_song_null_url(
        self, mock_thread_class, mock_fuzz,
        mock_musicsheet_path, mock_log_dir, sample_musicsheet,
        mock_discord_context
    ):
        """Test download_song handles null URL."""
        mock_fuzz.return_value = 0
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        mock_thread = MagicMock()
        mock_thread.is_alive = MagicMock(side_effect=[True, False])
        mock_thread_class.return_value = mock_thread
        
        result = await music.download_song(None, "Song 1", mock_discord_context)


# ==================== Play Next Tests ====================

class TestPlayNext:
    """Test play_next function with mocked discord context."""

    @pytest.mark.asyncio
    async def test_play_next_empty_playlist(
        self, mock_discord_context, mock_musicsheet_path,
        mock_log_dir, reset_shared_state
    ):
        """Test play_next with empty playlist."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump({"songs": []}, f)
        
        await music.play_next(mock_discord_context)
        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_play_next_standby_mode(
        self, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_log_dir, reset_shared_state
    ):
        """Test play_next in standby mode."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        shared_state.playback_mode = "播完後待機"
        
        await music.play_next(mock_discord_context)
        # Should not play next song

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_loop_mode(
        self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_song_dir, mock_log_dir, reset_shared_state
    ):
        """Test play_next in loop mode."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        shared_state.playback_mode = "循環播放清單"
        
        await music.play_next(mock_discord_context)

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_single_loop_mode(
        self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_song_dir, mock_log_dir, reset_shared_state
    ):
        """Test play_next in single loop mode."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        shared_state.playback_mode = "單曲循環"
        
        await music.play_next(mock_discord_context)

    @pytest.mark.asyncio
    async def test_play_next_max_attempts(
        self, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_log_dir, reset_shared_state
    ):
        """Test play_next stops after max attempts."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        mock_discord_context.next_song_attempts = 6
        
        await music.play_next(mock_discord_context)
        # Should return early


# ==================== Musicsheet Management Tests ====================

class TestMusicsheetManagement:
    """Test musicsheet creation, deletion, switching."""

    def test_get_next_index(self, sample_musicsheet):
        """Test get_next_index calculates correct index."""
        result = music.get_next_index(sample_musicsheet)
        assert result == "1.3"

    def test_get_next_index_wrap_around(self):
        """Test get_next_index wraps to next section."""
        data = {
            "songs": [
                {"index": f"1.{i}"} for i in range(1, 11)
            ]
        }
        result = music.get_next_index(data)
        assert result == "2.1"

    def test_reorganize_musicsheet(self, sample_musicsheet):
        """Test reorganize_musicsheet reorders indices."""
        music.reorganize_musicsheet(sample_musicsheet)
        
        assert sample_musicsheet["songs"][0]["index"] == "1.1"
        assert sample_musicsheet["songs"][1]["index"] == "1.2"

    @patch("utils.music.fuzz.partial_ratio")
    def test_remove_song(self, mock_fuzz, mock_musicsheet_path, sample_musicsheet, mock_log_dir):
        """Test remove_song removes from musicsheet."""
        mock_fuzz.return_value = 0
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        result = music.remove_song("Song 1")
        assert result is True
        
        loaded = music.load_musicsheet()
        assert len(loaded["songs"]) == 1
        assert loaded["songs"][0]["title"] == "Song 2"

    def test_remove_song_not_found(self, mock_musicsheet_path, sample_musicsheet, mock_log_dir):
        """Test remove_song handles nonexistent song."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        result = music.remove_song("Nonexistent")
        assert result is False

    def test_update_previous_song(self, mock_musicsheet_path, sample_musicsheet, mock_log_dir, reset_shared_state):
        """Test update_previous_song marks previous song."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        shared_state.playback_mode = "隨機播放"
        music.update_previous_song(sample_musicsheet["songs"][0])
        
        loaded = music.load_musicsheet()
        assert loaded["songs"][0]["is_previous"] is True
        assert loaded["songs"][1]["is_previous"] is False

    def test_delete_unlisted_songs(self, mock_song_dir, mock_musicsheet_path, sample_musicsheet, mock_log_dir):
        """Test delete_unlisted_songs removes orphaned files."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        # Create orphaned file
        orphan = os.path.join(mock_song_dir, "Orphan Song.mp3")
        Path(orphan).touch()
        
        music.delete_unlisted_songs()
        
        assert not os.path.exists(orphan)

    def test_scan_and_update_musicsheet(self, mock_song_dir, mock_musicsheet_path, mock_log_dir):
        """Test scan_and_update_musicsheet discovers files."""
        # Create a song file
        song_file = os.path.join(mock_song_dir, "New Song.mp3")
        Path(song_file).touch()
        
        music.scan_and_update_musicsheet()
        
        loaded = music.load_musicsheet()
        assert len(loaded["songs"]) > 0

    def test_init_musicsheet_system(self, temp_dir, monkeypatch, mock_log_dir):
        """Test init_musicsheet_system creates directories."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(
            music, "MUSICSHEET_INDEX_PATH",
            os.path.join(base_dir, "sheets_index.json")
        )
        
        music.init_musicsheet_system()
        
        assert os.path.exists(os.path.join(base_dir, "default"))
        assert os.path.exists(os.path.join(base_dir, "default", "musicsheet.json"))

    def test_list_musicsheets(self, temp_dir, monkeypatch, mock_log_dir):
        """Test list_musicsheets returns sheet list."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        sheets = music.list_musicsheets()
        assert len(sheets) > 0
        assert sheets[0]["name"] == "default"

    def test_create_musicsheet(self, temp_dir, monkeypatch, mock_log_dir):
        """Test create_musicsheet creates new sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.create_musicsheet("test", "Test Sheet")
        assert success is True
        
        sheets = music.list_musicsheets()
        assert any(s["name"] == "test" for s in sheets)

    def test_create_musicsheet_invalid_name(self, temp_dir, monkeypatch, mock_log_dir):
        """Test create_musicsheet rejects invalid names."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.create_musicsheet("test@invalid", "Test")
        assert success is False

    def test_delete_musicsheet(self, temp_dir, monkeypatch, mock_log_dir, reset_shared_state):
        """Test delete_musicsheet removes sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        music.create_musicsheet("test", "Test")
        
        success, msg = music.delete_musicsheet("test")
        assert success is True

    def test_delete_musicsheet_default_protected(self, temp_dir, monkeypatch, mock_log_dir):
        """Test delete_musicsheet protects default sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.delete_musicsheet("default")
        assert success is False

    def test_switch_musicsheet(self, temp_dir, monkeypatch, mock_log_dir, reset_shared_state):
        """Test switch_musicsheet changes current sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        music.create_musicsheet("test", "Test")
        
        success, msg = music.switch_musicsheet("test")
        assert success is True
        assert shared_state.current_musicsheet == "test"

    def test_get_sheet_display_name(self, temp_dir, monkeypatch, mock_log_dir):
        """Test get_sheet_display_name returns display name."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        music.create_musicsheet("test", "My Test Sheet")
        
        name = music.get_sheet_display_name("test")
        assert name == "My Test Sheet"

    def test_rename_musicsheet(self, temp_dir, monkeypatch, mock_log_dir):
        """Test rename_musicsheet changes display name."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        music.create_musicsheet("test", "Old Name")
        
        success, msg = music.rename_musicsheet("test", "New Name")
        assert success is True
        
        name = music.get_sheet_display_name("test")
        assert name == "New Name"

    def test_rename_musicsheet_not_found(self, temp_dir, monkeypatch, mock_log_dir):
        """Test rename_musicsheet handles nonexistent sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.rename_musicsheet("nonexistent", "New Name")
        assert success is False

    def test_rename_musicsheet_empty_name(self, temp_dir, monkeypatch, mock_log_dir):
        """Test rename_musicsheet rejects empty name."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        music.create_musicsheet("test", "Old Name")
        
        success, msg = music.rename_musicsheet("test", "")
        assert success is False

    def test_create_musicsheet_empty_name(self, temp_dir, monkeypatch, mock_log_dir):
        """Test create_musicsheet rejects empty name."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.create_musicsheet("", "Test")
        assert success is False

    def test_create_musicsheet_duplicate(self, temp_dir, monkeypatch, mock_log_dir):
        """Test create_musicsheet rejects duplicate names."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        music.create_musicsheet("test", "Test")
        
        success, msg = music.create_musicsheet("test", "Test 2")
        assert success is False

    def test_switch_musicsheet_not_found(self, temp_dir, monkeypatch, mock_log_dir):
        """Test switch_musicsheet handles nonexistent sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.switch_musicsheet("nonexistent")
        assert success is False

    def test_delete_musicsheet_not_found(self, temp_dir, monkeypatch, mock_log_dir):
        """Test delete_musicsheet handles nonexistent sheet."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        music.init_musicsheet_system()
        
        success, msg = music.delete_musicsheet("nonexistent")
        assert success is False

    def test_list_musicsheets_missing_index(self, temp_dir, monkeypatch, mock_log_dir):
        """Test list_musicsheets handles missing index file."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        sheets = music.list_musicsheets()
        assert len(sheets) > 0
        assert sheets[0]["name"] == "default"

    def test_list_musicsheets_corrupted_index(self, temp_dir, monkeypatch, mock_log_dir):
        """Test list_musicsheets handles corrupted index."""
        base_dir = os.path.join(temp_dir, "musicsheet")
        index_path = os.path.join(base_dir, "sheets_index.json")
        os.makedirs(base_dir, exist_ok=True)
        
        with open(index_path, "w") as f:
            f.write("{ invalid json }")
        
        monkeypatch.setattr(music, "MUSICSHEET_BASE_DIR", base_dir)
        monkeypatch.setattr(music, "MUSICSHEET_INDEX_PATH", index_path)
        
        sheets = music.list_musicsheets()
        assert len(sheets) > 0

    @patch("utils.music.fuzz.partial_ratio")
    def test_scan_and_update_removes_invalid_songs(self, mock_fuzz, mock_song_dir, mock_musicsheet_path, mock_log_dir):
        """Test scan_and_update_musicsheet removes invalid songs."""
        mock_fuzz.return_value = 0
        data = {
            "songs": [
                {
                    "title": "No File Song",
                    "url": None,
                    "is_downloaded": False,
                    "sanitized_title": "noffilesong"
                }
            ]
        }
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        music.scan_and_update_musicsheet()
        
        loaded = music.load_musicsheet()
        assert len(loaded["songs"]) == 0

    def test_update_previous_song_non_random_mode(self, mock_musicsheet_path, sample_musicsheet, mock_log_dir, reset_shared_state):
        """Test update_previous_song does nothing in non-random mode."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        shared_state.playback_mode = "循環播放清單"
        music.update_previous_song(sample_musicsheet["songs"][0])
        
        loaded = music.load_musicsheet()
        assert loaded["songs"][0]["is_previous"] is False

    @patch("utils.music.fuzz.partial_ratio")
    def test_remove_song_with_file(self, mock_fuzz, mock_musicsheet_path, sample_musicsheet, mock_song_dir, mock_log_dir):
        """Test remove_song deletes downloaded file."""
        mock_fuzz.return_value = 100
        sample_musicsheet["songs"][0]["is_downloaded"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(sample_musicsheet, f)
        
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        result = music.remove_song("Song 1")
        assert result is True
        assert not os.path.exists(test_file)

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_random_mode(self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_song_dir, mock_log_dir, reset_shared_state):
        """Test play_next in random mode."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        test_file2 = os.path.join(mock_song_dir, "Song 2.mp3")
        Path(test_file2).touch()
        
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        shared_state.playback_mode = "隨機播放"
        
        await music.play_next(mock_discord_context)

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_missing_file_recursive(self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_log_dir, reset_shared_state):
        """Test play_next handles missing file and recurses."""
        mock_fuzz.return_value = 0
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        shared_state.playback_mode = "循環播放清單"
        
        await music.play_next(mock_discord_context)

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_disconnected_reconnect(self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_song_dir, mock_log_dir, reset_shared_state):
        """Test play_next reconnects when disconnected."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        mock_discord_context.voice_client.is_connected = MagicMock(return_value=False)
        
        await music.play_next(mock_discord_context)

    @pytest.mark.asyncio
    async def test_play_next_author_not_in_voice(self, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_log_dir, reset_shared_state):
        """Test play_next handles author not in voice channel."""
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        mock_discord_context.voice_client.is_connected = MagicMock(return_value=False)
        mock_discord_context.author.voice = None
        
        await music.play_next(mock_discord_context)

    @patch("utils.music.AudioSegment")
    def test_convert_to_pcm_wav(self, mock_audio_segment, mock_song_dir, mock_log_dir):
        """Test convert_to_pcm with WAV file."""
        mock_audio = MagicMock()
        mock_audio.set_channels = MagicMock(return_value=mock_audio)
        mock_audio.set_frame_rate = MagicMock(return_value=mock_audio)
        mock_audio.set_sample_width = MagicMock(return_value=mock_audio)
        mock_audio.normalize = MagicMock(return_value=mock_audio)
        mock_audio.export = MagicMock()
        
        mock_audio_segment.from_wav = MagicMock(return_value=mock_audio)
        
        test_file = os.path.join(mock_song_dir, "test.wav")
        Path(test_file).touch()
        
        result = music.convert_to_pcm(test_file)
        assert result is not None

    @patch("utils.music.AudioSegment")
    def test_convert_to_pcm_generic(self, mock_audio_segment, mock_song_dir, mock_log_dir):
        """Test convert_to_pcm with generic audio file."""
        mock_audio = MagicMock()
        mock_audio.set_channels = MagicMock(return_value=mock_audio)
        mock_audio.set_frame_rate = MagicMock(return_value=mock_audio)
        mock_audio.set_sample_width = MagicMock(return_value=mock_audio)
        mock_audio.normalize = MagicMock(return_value=mock_audio)
        mock_audio.export = MagicMock()
        
        mock_audio_segment.from_file = MagicMock(return_value=mock_audio)
        
        test_file = os.path.join(mock_song_dir, "test.ogg")
        Path(test_file).touch()
        
        result = music.convert_to_pcm(test_file)
        assert result is not None

    def test_check_audio_file_m4a_valid(self, mock_song_dir):
        """Test check_audio_file validates M4A files."""
        test_file = os.path.join(mock_song_dir, "test.m4a")
        with open(test_file, "wb") as f:
            f.write(b"ftyp" + b"\x00" * 12)
        
        result = music.check_audio_file(test_file)
        assert result is True

    def test_check_audio_file_m4a_invalid(self, mock_song_dir):
        """Test check_audio_file detects invalid M4A."""
        test_file = os.path.join(mock_song_dir, "test.m4a")
        with open(test_file, "wb") as f:
            f.write(b"INVALID" + b"\x00" * 10)
        
        result = music.check_audio_file(test_file)
        assert result is False

    @patch("utils.music.os.listdir")
    def test_find_downloaded_file_listdir_error(self, mock_listdir):
        """Test find_downloaded_file handles listdir error."""
        mock_listdir.side_effect = OSError("Permission denied")
        
        try:
            music.find_downloaded_file("Song 1")
        except OSError:
            pass

    def test_check_audio_file_read_error(self, mock_song_dir):
        """Test check_audio_file handles read error."""
        test_file = os.path.join(mock_song_dir, "test.mp3")
        with open(test_file, "wb") as f:
            f.write(b"ID3" + b"\x00" * 13)
        
        with patch("builtins.open", side_effect=IOError("Read error")):
            result = music.check_audio_file(test_file)
            assert result is False


# ==================== Additional Error Handling Tests ====================

class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_load_musicsheet_backup_failure(self, mock_musicsheet_path, mock_log_dir):
        """Test load_musicsheet handles backup failure."""
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")
        
        with patch("shutil.copy", side_effect=Exception("Backup failed")):
            result = music.load_musicsheet()
            assert result == {"songs": []}

    @patch("utils.music.os.listdir")
    def test_find_downloaded_file_listdir_error(self, mock_listdir):
        """Test find_downloaded_file handles listdir error."""
        mock_listdir.side_effect = OSError("Permission denied")
        
        try:
            music.find_downloaded_file("Song 1")
        except OSError:
            pass

    @patch("utils.music.AudioSegment")
    def test_convert_to_pcm_export_error(self, mock_audio_segment, mock_song_dir, mock_log_dir):
        """Test convert_to_pcm handles export error."""
        mock_audio = MagicMock()
        mock_audio.set_channels = MagicMock(return_value=mock_audio)
        mock_audio.set_frame_rate = MagicMock(return_value=mock_audio)
        mock_audio.set_sample_width = MagicMock(return_value=mock_audio)
        mock_audio.normalize = MagicMock(return_value=mock_audio)
        mock_audio.export = MagicMock(side_effect=Exception("Export failed"))
        
        mock_audio_segment.from_mp3 = MagicMock(return_value=mock_audio)
        
        test_file = os.path.join(mock_song_dir, "test.mp3")
        Path(test_file).touch()
        
        result = music.convert_to_pcm(test_file)
        assert result is None

    def test_pcm_stream_reader_total_bytes_error(self):
        """Test PCMStreamReader handles getbuffer error."""
        mock_io = MagicMock()
        mock_io.getbuffer = MagicMock(side_effect=Exception("Buffer error"))
        
        reader = music.PCMStreamReader(mock_io)
        assert reader.total_bytes == 0

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_invoke_error(self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_song_dir, mock_log_dir, reset_shared_state):
        """Test play_next handles invoke error."""
        mock_fuzz.return_value = 100
        test_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(test_file).touch()
        
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        shared_state.playback_mode = "循環播放清單"
        mock_discord_context.invoke = AsyncMock(side_effect=Exception("Invoke error"))
        
        await music.play_next(mock_discord_context)

    @pytest.mark.asyncio
    @patch("utils.music.fuzz.partial_ratio")
    async def test_play_next_reconnect_error(self, mock_fuzz, mock_discord_context, mock_musicsheet_path,
        sample_musicsheet, mock_log_dir, reset_shared_state):
        """Test play_next handles reconnect error."""
        mock_fuzz.return_value = 0
        data = sample_musicsheet.copy()
        data["songs"][0]["is_playing"] = True
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        mock_discord_context.voice_client.is_connected = MagicMock(return_value=False)
        mock_discord_context.author.voice.channel.connect = AsyncMock(side_effect=Exception("Connect error"))
        
        await music.play_next(mock_discord_context)

    def test_reorganize_musicsheet_invalid_index(self, mock_log_dir):
        """Test reorganize_musicsheet handles invalid index format."""
        data = {
            "songs": [
                {"index": "invalid", "title": "Song 1"},
                {"index": "1.2", "title": "Song 2"}
            ]
        }
        
        music.reorganize_musicsheet(data)
        assert data["songs"][0]["index"] == "1.1"
        assert data["songs"][1]["index"] == "1.2"

    @patch("utils.music.fuzz.partial_ratio")
    def test_scan_and_update_duplicate_detection(self, mock_fuzz, mock_song_dir, mock_musicsheet_path, mock_log_dir):
        """Test scan_and_update_musicsheet detects duplicates."""
        mock_fuzz.return_value = 90
        data = {
            "songs": [
                {
                    "title": "Song 1",
                    "url": "http://example.com",
                    "is_downloaded": True,
                    "sanitized_title": "song1"
                }
            ]
        }
        with open(mock_musicsheet_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        song_file = os.path.join(mock_song_dir, "Song 1.mp3")
        Path(song_file).touch()
        
        music.scan_and_update_musicsheet()
        
        loaded = music.load_musicsheet()
        assert len(loaded["songs"]) == 1
