"""
Comprehensive test suite for utils/character_storage.py

Tests cover:
- save_character: Verify data formatting and database insertion
- get_character: Verify data retrieval and JSON parsing
- delete_character: Verify deletion and return values
- get_all_names: Verify listing and ordering
- Error handling: Database errors, exceptions, edge cases
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from utils.character_storage import (
    save_character,
    get_character,
    delete_character,
    get_all_names
)


# ==================== Fixtures ====================

@pytest.fixture
def sample_char_data():
    """Sample character data from initiative entry"""
    return {
        "hp": 100,
        "elements": ["fire", "water"],
        "atk": 15,
        "def_": 10,
        "favorite_dice": {"initiative": "1d20+5", "attack": "2d6+3"},
        "last_formula": "1d20+5"
    }


@pytest.fixture
def sample_stored_data():
    """Sample data as stored in database"""
    return {
        "stats": {
            "hp": 100,
            "elements": ["fire", "water"],
            "atk": 15,
            "def_": 10
        },
        "favorite_dice": {"initiative": "1d20+5", "attack": "2d6+3"},
        "initiative_formula": "1d20+5"
    }


@pytest.fixture
def mock_database():
    """Mock Database class"""
    with patch('utils.character_storage.Database') as mock_db:
        yield mock_db


@pytest.fixture
def mock_log_message():
    """Mock log_message function"""
    with patch('utils.character_storage.log_message') as mock_log:
        yield mock_log


# ==================== save_character Tests ====================

class TestSaveCharacter:
    """Test save_character function"""

    @pytest.mark.asyncio
    async def test_save_character_new_character(self, mock_database, mock_log_message, sample_char_data, sample_stored_data):
        """Test saving a new character"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)  # No existing data
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character("Aragorn", sample_char_data, ["stats", "dice", "formula"])

        # Verify
        assert result is True
        mock_database.execute.assert_called_once()
        call_args = mock_database.execute.call_args
        assert "INSERT INTO characters" in call_args[0][0]
        assert call_args[0][1] == "Aragorn"
        
        # Verify JSON data structure
        saved_data = json.loads(call_args[0][2])
        assert saved_data["stats"]["hp"] == 100
        assert saved_data["favorite_dice"]["initiative"] == "1d20+5"
        assert saved_data["initiative_formula"] == "1d20+5"
        
        mock_log_message.assert_called()

    @pytest.mark.asyncio
    async def test_save_character_update_existing(self, mock_database, mock_log_message, sample_char_data):
        """Test updating an existing character"""
        # Setup - existing data
        existing_data = {
            "stats": {"hp": 50, "elements": [], "atk": 10, "def_": 5},
            "favorite_dice": {"old": "1d6"},
            "initiative_formula": "1d20"
        }
        mock_database.fetchval = AsyncMock(return_value=json.dumps(existing_data))
        mock_database.execute = AsyncMock(return_value="UPDATE 1")

        # Execute
        result = await save_character("Aragorn", sample_char_data, ["stats"])

        # Verify
        assert result is True
        call_args = mock_database.execute.call_args
        saved_data = json.loads(call_args[0][2])
        
        # Stats should be updated
        assert saved_data["stats"]["hp"] == 100
        # Other fields should remain unchanged
        assert saved_data["favorite_dice"]["old"] == "1d6"
        assert saved_data["initiative_formula"] == "1d20"

    @pytest.mark.asyncio
    async def test_save_character_partial_fields(self, mock_database, mock_log_message, sample_char_data):
        """Test saving only specific fields"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute - only save dice
        result = await save_character("Aragorn", sample_char_data, ["dice"])

        # Verify
        assert result is True
        call_args = mock_database.execute.call_args
        saved_data = json.loads(call_args[0][2])
        
        # Only dice should be set, stats should remain as initialized (empty dict)
        assert saved_data["favorite_dice"]["initiative"] == "1d20+5"
        assert saved_data["stats"] == {}  # Not updated, so remains empty

    @pytest.mark.asyncio
    async def test_save_character_empty_fields_list(self, mock_database, mock_log_message, sample_char_data):
        """Test saving with empty fields list"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character("Aragorn", sample_char_data, [])

        # Verify
        assert result is True
        call_args = mock_database.execute.call_args
        saved_data = json.loads(call_args[0][2])
        
        # No fields selected, so all remain as initialized
        assert saved_data["stats"] == {}
        assert saved_data["favorite_dice"] == {}
        assert saved_data["initiative_formula"] is None

    @pytest.mark.asyncio
    async def test_save_character_database_error(self, mock_database, mock_log_message, sample_char_data):
        """Test handling database errors"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(side_effect=Exception("DB connection failed"))

        # Execute
        result = await save_character("Aragorn", sample_char_data, ["stats"])

        # Verify
        assert result is False
        mock_log_message.assert_called()
        assert "❌" in mock_log_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_save_character_missing_fields_in_data(self, mock_database, mock_log_message):
        """Test saving with missing fields in character data"""
        # Setup
        incomplete_data = {"hp": 100}  # Missing other fields
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character("Aragorn", incomplete_data, ["stats", "dice"])

        # Verify
        assert result is True
        call_args = mock_database.execute.call_args
        saved_data = json.loads(call_args[0][2])
        
        # Should handle missing fields gracefully
        assert saved_data["stats"]["hp"] == 100
        assert saved_data["stats"]["elements"] is None
        assert saved_data["favorite_dice"] == {}


# ==================== get_character Tests ====================

class TestGetCharacter:
    """Test get_character function"""

    @pytest.mark.asyncio
    async def test_get_character_exists(self, mock_database, mock_log_message, sample_stored_data):
        """Test retrieving an existing character"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=json.dumps(sample_stored_data))

        # Execute
        result = await get_character("Aragorn")

        # Verify
        assert result is not None
        assert result["stats"]["hp"] == 100
        assert result["favorite_dice"]["initiative"] == "1d20+5"
        mock_database.fetchval.assert_called_once()
        call_args = mock_database.fetchval.call_args
        assert "SELECT data FROM characters" in call_args[0][0]
        assert call_args[0][1] == "Aragorn"

    @pytest.mark.asyncio
    async def test_get_character_not_found(self, mock_database, mock_log_message):
        """Test retrieving a non-existent character"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)

        # Execute
        result = await get_character("NonExistent")

        # Verify
        assert result is None
        mock_log_message.assert_not_called()  # No error logged for missing character

    @pytest.mark.asyncio
    async def test_get_character_invalid_json(self, mock_database, mock_log_message):
        """Test handling corrupted JSON data"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value="invalid json {{{")

        # Execute
        result = await get_character("Aragorn")

        # Verify
        assert result is None
        mock_log_message.assert_called()
        assert "❌" in mock_log_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_character_database_error(self, mock_database, mock_log_message):
        """Test handling database errors"""
        # Setup
        mock_database.fetchval = AsyncMock(side_effect=Exception("Connection timeout"))

        # Execute
        result = await get_character("Aragorn")

        # Verify
        assert result is None
        mock_log_message.assert_called()
        assert "❌" in mock_log_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_character_empty_string_name(self, mock_database, mock_log_message):
        """Test retrieving with empty character name"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)

        # Execute
        result = await get_character("")

        # Verify
        assert result is None
        mock_database.fetchval.assert_called_once()


# ==================== delete_character Tests ====================

class TestDeleteCharacter:
    """Test delete_character function"""

    @pytest.mark.asyncio
    async def test_delete_character_success(self, mock_database, mock_log_message):
        """Test successful character deletion"""
        # Setup
        mock_database.execute = AsyncMock(return_value="DELETE 1")

        # Execute
        result = await delete_character("Aragorn")

        # Verify
        assert result is True
        mock_database.execute.assert_called_once()
        call_args = mock_database.execute.call_args
        assert "DELETE FROM characters" in call_args[0][0]
        assert call_args[0][1] == "Aragorn"
        mock_log_message.assert_called()
        assert "🗑️" in mock_log_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_character_not_found(self, mock_database, mock_log_message):
        """Test deleting a non-existent character"""
        # Setup
        mock_database.execute = AsyncMock(return_value="DELETE 0")

        # Execute
        result = await delete_character("NonExistent")

        # Verify
        assert result is False
        mock_log_message.assert_not_called()  # No success message

    @pytest.mark.asyncio
    async def test_delete_character_database_error(self, mock_database, mock_log_message):
        """Test handling database errors during deletion"""
        # Setup
        mock_database.execute = AsyncMock(side_effect=Exception("DB error"))

        # Execute
        result = await delete_character("Aragorn")

        # Verify
        assert result is False
        mock_log_message.assert_called()
        assert "❌" in mock_log_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_character_empty_name(self, mock_database, mock_log_message):
        """Test deleting with empty character name"""
        # Setup
        mock_database.execute = AsyncMock(return_value="DELETE 0")

        # Execute
        result = await delete_character("")

        # Verify
        assert result is False


# ==================== get_all_names Tests ====================

class TestGetAllNames:
    """Test get_all_names function"""

    @pytest.mark.asyncio
    async def test_get_all_names_multiple(self, mock_database, mock_log_message):
        """Test retrieving multiple character names"""
        # Setup
        mock_rows = [
            {"name": "Aragorn"},
            {"name": "Legolas"},
            {"name": "Gimli"}
        ]
        mock_database.fetch = AsyncMock(return_value=mock_rows)

        # Execute
        result = await get_all_names()

        # Verify
        assert result == ["Aragorn", "Legolas", "Gimli"]
        mock_database.fetch.assert_called_once()
        call_args = mock_database.fetch.call_args
        assert "SELECT name FROM characters" in call_args[0][0]
        assert "ORDER BY name" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_all_names_empty(self, mock_database, mock_log_message):
        """Test retrieving when no characters exist"""
        # Setup
        mock_database.fetch = AsyncMock(return_value=[])

        # Execute
        result = await get_all_names()

        # Verify
        assert result == []
        mock_log_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_names_single(self, mock_database, mock_log_message):
        """Test retrieving a single character name"""
        # Setup
        mock_rows = [{"name": "Aragorn"}]
        mock_database.fetch = AsyncMock(return_value=mock_rows)

        # Execute
        result = await get_all_names()

        # Verify
        assert result == ["Aragorn"]

    @pytest.mark.asyncio
    async def test_get_all_names_database_error(self, mock_database, mock_log_message):
        """Test handling database errors"""
        # Setup
        mock_database.fetch = AsyncMock(side_effect=Exception("Connection lost"))

        # Execute
        result = await get_all_names()

        # Verify
        assert result == []
        mock_log_message.assert_called()
        assert "❌" in mock_log_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_all_names_ordered(self, mock_database, mock_log_message):
        """Test that names are returned in alphabetical order"""
        # Setup
        mock_rows = [
            {"name": "Aragorn"},
            {"name": "Boromir"},
            {"name": "Legolas"}
        ]
        mock_database.fetch = AsyncMock(return_value=mock_rows)

        # Execute
        result = await get_all_names()

        # Verify
        assert result == ["Aragorn", "Boromir", "Legolas"]
        # Verify ORDER BY is in query
        call_args = mock_database.fetch.call_args
        assert "ORDER BY name" in call_args[0][0]


# ==================== Integration Tests ====================

class TestCharacterStorageIntegration:
    """Integration tests for character storage workflow"""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_workflow(self, mock_database, mock_log_message, sample_char_data, sample_stored_data):
        """Test complete save and retrieve workflow"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Save character
        save_result = await save_character("Aragorn", sample_char_data, ["stats", "dice", "formula"])
        assert save_result is True

        # Setup for retrieval
        mock_database.fetchval = AsyncMock(return_value=json.dumps(sample_stored_data))

        # Retrieve character
        get_result = await get_character("Aragorn")
        assert get_result is not None
        assert get_result["stats"]["hp"] == 100

    @pytest.mark.asyncio
    async def test_save_update_delete_workflow(self, mock_database, mock_log_message, sample_char_data):
        """Test complete save, update, and delete workflow"""
        # Save
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")
        save_result = await save_character("Aragorn", sample_char_data, ["stats"])
        assert save_result is True

        # Update
        mock_database.fetchval = AsyncMock(return_value=json.dumps({"stats": {}, "favorite_dice": {}, "initiative_formula": None}))
        mock_database.execute = AsyncMock(return_value="UPDATE 1")
        update_result = await save_character("Aragorn", sample_char_data, ["dice"])
        assert update_result is True

        # Delete
        mock_database.execute = AsyncMock(return_value="DELETE 1")
        delete_result = await delete_character("Aragorn")
        assert delete_result is True

    @pytest.mark.asyncio
    async def test_list_and_retrieve_multiple(self, mock_database, mock_log_message, sample_stored_data):
        """Test listing and retrieving multiple characters"""
        # Setup list
        mock_rows = [
            {"name": "Aragorn"},
            {"name": "Legolas"},
            {"name": "Gimli"}
        ]
        mock_database.fetch = AsyncMock(return_value=mock_rows)

        # Get all names
        names = await get_all_names()
        assert len(names) == 3

        # Retrieve each character
        mock_database.fetchval = AsyncMock(return_value=json.dumps(sample_stored_data))
        for name in names:
            char = await get_character(name)
            assert char is not None


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_character_name_with_special_characters(self, mock_database, mock_log_message, sample_char_data):
        """Test handling character names with special characters"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character("Aragorn's Heir (v2)", sample_char_data, ["stats"])

        # Verify
        assert result is True
        call_args = mock_database.execute.call_args
        assert call_args[0][1] == "Aragorn's Heir (v2)"

    @pytest.mark.asyncio
    async def test_character_with_unicode_name(self, mock_database, mock_log_message, sample_char_data):
        """Test handling Unicode character names"""
        # Setup
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character("アラゴルン", sample_char_data, ["stats"])

        # Verify
        assert result is True

    @pytest.mark.asyncio
    async def test_character_with_very_long_name(self, mock_database, mock_log_message, sample_char_data):
        """Test handling very long character names"""
        # Setup
        long_name = "A" * 1000
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character(long_name, sample_char_data, ["stats"])

        # Verify
        assert result is True

    @pytest.mark.asyncio
    async def test_character_with_large_data(self, mock_database, mock_log_message):
        """Test handling large character data"""
        # Setup
        large_data = {
            "hp": 100,
            "elements": ["fire"] * 100,
            "atk": 15,
            "def_": 10,
            "favorite_dice": {f"dice_{i}": f"1d20+{i}" for i in range(100)},
            "last_formula": "1d20+5"
        }
        mock_database.fetchval = AsyncMock(return_value=None)
        mock_database.execute = AsyncMock(return_value="INSERT 1")

        # Execute
        result = await save_character("Aragorn", large_data, ["stats", "dice", "formula"])

        # Verify
        assert result is True

    @pytest.mark.asyncio
    async def test_get_character_with_null_values(self, mock_database, mock_log_message):
        """Test retrieving character with null values"""
        # Setup
        data_with_nulls = {
            "stats": {"hp": None, "elements": None, "atk": None, "def_": None},
            "favorite_dice": None,
            "initiative_formula": None
        }
        mock_database.fetchval = AsyncMock(return_value=json.dumps(data_with_nulls))

        # Execute
        result = await get_character("Aragorn")

        # Verify
        assert result is not None
        assert result["stats"]["hp"] is None
        assert result["favorite_dice"] is None
