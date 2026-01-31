"""
Dummy test to verify testing infrastructure is working correctly.
"""

import pytest


class TestSetup:
    """Test suite to verify pytest setup."""

    def test_pytest_installed(self):
        """Verify pytest is installed and working."""
        assert True

    def test_basic_assertion(self):
        """Test basic assertion."""
        assert 1 + 1 == 2

    @pytest.mark.asyncio
    async def test_async_support(self):
        """Test async/await support."""
        async def async_function():
            return "async works"

        result = await async_function()
        assert result == "async works"

    def test_fixtures_available(self, mock_discord_context):
        """Test that fixtures are available."""
        assert mock_discord_context is not None
        assert hasattr(mock_discord_context, 'send')
