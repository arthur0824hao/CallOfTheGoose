"""
Pytest configuration and shared fixtures for the Discord bot test suite.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_discord_context():
    """Mock Discord context object."""
    ctx = AsyncMock()
    ctx.send = AsyncMock()
    ctx.author = MagicMock()
    ctx.author.id = 123456789
    ctx.guild = MagicMock()
    ctx.guild.id = 987654321
    ctx.channel = MagicMock()
    ctx.channel.id = 555555555
    return ctx


@pytest.fixture
def mock_discord_bot():
    """Mock Discord bot object."""
    bot = AsyncMock()
    bot.user = MagicMock()
    bot.user.id = 111111111
    bot.user.name = "TestBot"
    return bot


@pytest.fixture
def mock_discord_message():
    """Mock Discord message object."""
    message = MagicMock()
    message.id = 999999999
    message.author = MagicMock()
    message.author.id = 123456789
    message.guild = MagicMock()
    message.guild.id = 987654321
    message.channel = MagicMock()
    message.channel.id = 555555555
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    return message
