"""
Pytest configuration for utils tests.
Handles mocking of problematic dependencies.
"""

import sys
from unittest.mock import MagicMock

sys.modules['pydub'] = MagicMock()
sys.modules['pydub.AudioSegment'] = MagicMock()
sys.modules['yt_dlp'] = MagicMock()
sys.modules['yt_dlp.utils'] = MagicMock()
sys.modules['fuzzywuzzy'] = MagicMock()
sys.modules['fuzzywuzzy.fuzz'] = MagicMock()
sys.modules['asyncpg'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
