"""
Tests for utils/initiative.py
Comprehensive test suite for initiative tracker functionality with mocked Database and shared_state.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import utils.initiative as initiative
import utils.shared_state as shared_state


# ============================================
# FIXTURES
# ============================================


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_database(mocker):
    """Mock the Database class."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.fetchval = AsyncMock()
    mock_db.fetch = AsyncMock()
    mock_db.fetchrow = AsyncMock()
    
    # Patch Database in the initiative module
    mocker.patch("utils.initiative.Database", mock_db)
    return mock_db


@pytest.fixture
def mock_shared_state(mocker):
    """Mock shared_state to isolate tests."""
    # Create a fresh copy of shared_state for each test
    mocker.patch.dict(
        "utils.shared_state.initiative_trackers",
        {},
        clear=True
    )
    return shared_state


@pytest.fixture
def mock_log_message(mocker):
    """Mock log_message to avoid side effects."""
    return mocker.patch("utils.initiative.log_message")


@pytest.fixture
def mock_dice_functions(mocker):
    """Mock dice parsing functions."""
    mock_parse = mocker.patch("utils.initiative.parse_and_roll")
    mock_parse.return_value = (15, [])  # Default: return 15 with no dice rolls
    
    return {
        "parse_and_roll": mock_parse,
    }


@pytest.fixture
def channel_id():
    """Standard test channel ID."""
    return "123456789"


@pytest.fixture
async def clean_tracker(channel_id, mock_shared_state, mock_database, mock_log_message):
    """Get a clean tracker for testing."""
    # Clear any existing trackers
    shared_state.initiative_trackers.clear()
    tracker = await initiative.get_tracker(channel_id)
    return tracker


# ============================================
# TESTS: CRUD OPERATIONS
# ============================================


class TestCRUDOperations:
    """Test Create, Read, Update, Delete operations."""

    @pytest.mark.asyncio
    async def test_add_entry_basic(self, channel_id, clean_tracker, mock_database, mock_log_message):
        """Test adding a basic entry to the tracker."""
        success = await initiative.add_entry(channel_id, "Hero", 15)
        
        assert success is True
        tracker = await initiative.get_tracker(channel_id)
        assert len(tracker["entries"]) == 1
        assert tracker["entries"][0]["name"] == "Hero"
        assert tracker["entries"][0]["initiative"] == 15
        assert tracker["is_active"] is True
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_add_entry_with_details(self, channel_id, clean_tracker, mock_database):
        """Test adding entry with roll details and formula."""
        success = await initiative.add_entry(
            channel_id, 
            "Mage", 
            20, 
            roll_detail="[18] + 2 = 20",
            formula="1d20+2"
        )
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Mage")
        assert entry["roll_detail"] == "[18] + 2 = 20"
        assert entry["last_formula"] == "1d20+2"

    @pytest.mark.asyncio
    async def test_add_entry_duplicate_name(self, channel_id, clean_tracker, mock_database):
        """Test that duplicate names are rejected."""
        await initiative.add_entry(channel_id, "Hero", 15)
        success = await initiative.add_entry(channel_id, "Hero", 20)
        
        assert success is False
        tracker = await initiative.get_tracker(channel_id)
        assert len(tracker["entries"]) == 1

    @pytest.mark.asyncio
    async def test_add_entry_initializes_stats(self, channel_id, clean_tracker):
        """Test that new entries have initialized stats."""
        await initiative.add_entry(channel_id, "Warrior", 12)
        entry = await initiative.get_entry(channel_id, "Warrior")
        
        assert entry["hp"] == 0
        assert entry["elements"] == 0
        assert entry["atk"] == 0
        assert entry["def_"] == 0
        assert entry["status_effects"] == {}
        assert entry["favorite_dice"] == {}

    @pytest.mark.asyncio
    async def test_get_entry_exists(self, channel_id, clean_tracker):
        """Test retrieving an existing entry."""
        await initiative.add_entry(channel_id, "Rogue", 18)
        entry = await initiative.get_entry(channel_id, "Rogue")
        
        assert entry is not None
        assert entry["name"] == "Rogue"
        assert entry["initiative"] == 18

    @pytest.mark.asyncio
    async def test_get_entry_not_exists(self, channel_id, clean_tracker):
        """Test retrieving a non-existent entry."""
        entry = await initiative.get_entry(channel_id, "NonExistent")
        assert entry is None

    @pytest.mark.asyncio
    async def test_remove_entry_success(self, channel_id, clean_tracker, mock_database):
        """Test removing an entry."""
        await initiative.add_entry(channel_id, "Paladin", 14)
        success = await initiative.remove_entry(channel_id, "Paladin")
        
        assert success is True
        tracker = await initiative.get_tracker(channel_id)
        assert len(tracker["entries"]) == 0
        assert tracker["is_active"] is False
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_remove_entry_not_exists(self, channel_id, clean_tracker):
        """Test removing a non-existent entry."""
        success = await initiative.remove_entry(channel_id, "NonExistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_remove_entry_adjusts_current_index(self, channel_id, clean_tracker):
        """Test that removing an entry adjusts current_index if needed."""
        await initiative.add_entry(channel_id, "A", 10)
        await initiative.add_entry(channel_id, "B", 20)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_index"] = 1  # Point to last entry
        
        await initiative.remove_entry(channel_id, "B")
        
        # current_index should be reset to 0
        assert tracker["current_index"] == 0

    @pytest.mark.asyncio
    async def test_remove_entry_clears_selected_character(self, channel_id, clean_tracker):
        """Test that removing selected character clears the selection."""
        await initiative.add_entry(channel_id, "Target", 15)
        await initiative.select_character(channel_id, "Target")
        
        await initiative.remove_entry(channel_id, "Target")
        
        tracker = await initiative.get_tracker(channel_id)
        assert tracker.get("selected_character") is None


# ============================================
# TESTS: TURN MANAGEMENT
# ============================================


class TestTurnManagement:
    """Test turn and round management."""

    @pytest.mark.asyncio
    async def test_next_turn_basic(self, channel_id, clean_tracker, mock_database):
        """Test advancing to next turn."""
        await initiative.add_entry(channel_id, "A", 20)
        await initiative.add_entry(channel_id, "B", 15)
        
        name, new_round = await initiative.next_turn(channel_id)
        
        assert name == "B"
        assert new_round is False
        tracker = await initiative.get_tracker(channel_id)
        assert tracker["current_index"] == 1

    @pytest.mark.asyncio
    async def test_next_turn_wraps_to_new_round(self, channel_id, clean_tracker):
        """Test that next_turn wraps around and increments round."""
        await initiative.add_entry(channel_id, "A", 20)
        await initiative.add_entry(channel_id, "B", 15)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_index"] = 1  # Last entry
        
        name, new_round = await initiative.next_turn(channel_id)
        
        assert name == "A"
        assert new_round is True
        assert tracker["current_round"] == 2
        assert tracker["current_index"] == 0

    @pytest.mark.asyncio
    async def test_next_turn_empty_tracker(self, channel_id, clean_tracker):
        """Test next_turn on empty tracker."""
        name, new_round = await initiative.next_turn(channel_id)
        
        assert name is None
        assert new_round is False

    @pytest.mark.asyncio
    async def test_prev_turn_basic(self, channel_id, clean_tracker):
        """Test going to previous turn."""
        await initiative.add_entry(channel_id, "A", 20)
        await initiative.add_entry(channel_id, "B", 15)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_index"] = 1
        
        name, round_num = await initiative.prev_turn(channel_id)
        
        assert name == "A"
        assert round_num == 1
        assert tracker["current_index"] == 0

    @pytest.mark.asyncio
    async def test_prev_turn_wraps_to_previous_round(self, channel_id, clean_tracker):
        """Test that prev_turn wraps to previous round."""
        await initiative.add_entry(channel_id, "A", 20)
        await initiative.add_entry(channel_id, "B", 15)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_index"] = 0
        tracker["current_round"] = 2
        
        name, round_num = await initiative.prev_turn(channel_id)
        
        assert name == "B"
        assert round_num == 1
        assert tracker["current_index"] == 1

    @pytest.mark.asyncio
    async def test_prev_turn_at_start(self, channel_id, clean_tracker):
        """Test prev_turn at round 1, index 0 (stays at start)."""
        await initiative.add_entry(channel_id, "A", 20)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_index"] = 0
        tracker["current_round"] = 1
        
        name, round_num = await initiative.prev_turn(channel_id)
        
        assert name == "A"
        assert round_num == 1
        assert tracker["current_index"] == 0

    @pytest.mark.asyncio
    async def test_prev_turn_empty_tracker(self, channel_id, clean_tracker):
        """Test prev_turn on empty tracker."""
        tracker = await initiative.get_tracker(channel_id)
        name, round_num = await initiative.prev_turn(channel_id)
        
        assert name is None
        assert round_num == tracker["current_round"]

    @pytest.mark.asyncio
    async def test_reset_tracker(self, channel_id, clean_tracker, mock_database):
        """Test resetting tracker to initial state."""
        await initiative.add_entry(channel_id, "A", 20)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_round"] = 5
        tracker["current_index"] = 1
        
        await initiative.reset_tracker(channel_id)
        
        assert tracker["current_round"] == 1
        assert tracker["current_index"] == 0
        mock_database.execute.assert_called()


# ============================================
# TESTS: STATS AND STATUS EFFECTS
# ============================================


class TestStatsAndStatus:
    """Test stat management and status effects."""

    @pytest.mark.asyncio
    async def test_set_stats_all(self, channel_id, clean_tracker, mock_database):
        """Test setting all stats at once."""
        await initiative.add_entry(channel_id, "Warrior", 15)
        success = await initiative.set_stats(
            channel_id, "Warrior", hp=100, elements=50, atk=20, def_=15
        )
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Warrior")
        assert entry["hp"] == 100
        assert entry["elements"] == 50
        assert entry["atk"] == 20
        assert entry["def_"] == 15
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_set_stats_partial(self, channel_id, clean_tracker):
        """Test setting only some stats."""
        await initiative.add_entry(channel_id, "Mage", 18)
        await initiative.set_stats(channel_id, "Mage", hp=80, atk=10)
        
        entry = await initiative.get_entry(channel_id, "Mage")
        assert entry["hp"] == 80
        assert entry["atk"] == 10
        assert entry["elements"] == 0  # Unchanged
        assert entry["def_"] == 0  # Unchanged

    @pytest.mark.asyncio
    async def test_set_stats_nonexistent_entry(self, channel_id, clean_tracker):
        """Test setting stats on non-existent entry."""
        success = await initiative.set_stats(channel_id, "Ghost", hp=50)
        assert success is False

    @pytest.mark.asyncio
    async def test_modify_hp_increase(self, channel_id, clean_tracker, mock_database):
        """Test increasing HP."""
        await initiative.add_entry(channel_id, "Knight", 12)
        await initiative.set_stats(channel_id, "Knight", hp=100)
        
        success, new_hp = await initiative.modify_hp(channel_id, "Knight", 20)
        
        assert success is True
        assert new_hp == 120
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_modify_hp_decrease(self, channel_id, clean_tracker):
        """Test decreasing HP."""
        await initiative.add_entry(channel_id, "Rogue", 18)
        await initiative.set_stats(channel_id, "Rogue", hp=50)
        
        success, new_hp = await initiative.modify_hp(channel_id, "Rogue", -15)
        
        assert success is True
        assert new_hp == 35

    @pytest.mark.asyncio
    async def test_modify_hp_nonexistent(self, channel_id, clean_tracker):
        """Test modifying HP of non-existent entry."""
        success, msg = await initiative.modify_hp(channel_id, "Ghost", 10)
        assert success is False
        assert msg == "找不到角色"

    @pytest.mark.asyncio
    async def test_modify_elements(self, channel_id, clean_tracker):
        """Test modifying elements."""
        await initiative.add_entry(channel_id, "Mage", 16)
        await initiative.set_stats(channel_id, "Mage", elements=100)
        
        success, new_elements = await initiative.modify_elements(channel_id, "Mage", -25)
        
        assert success is True
        assert new_elements == 75

    @pytest.mark.asyncio
    async def test_add_status(self, channel_id, clean_tracker, mock_database):
        """Test adding a status effect."""
        await initiative.add_entry(channel_id, "Warrior", 14)
        success = await initiative.add_status(channel_id, "Warrior", "中毒", "3回合")
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Warrior")
        assert entry["status_effects"]["中毒"] == "3回合"
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_add_status_multiple(self, channel_id, clean_tracker):
        """Test adding multiple status effects."""
        await initiative.add_entry(channel_id, "Paladin", 13)
        await initiative.add_status(channel_id, "Paladin", "祝福", "永久")
        await initiative.add_status(channel_id, "Paladin", "護盾", "2回合")
        
        entry = await initiative.get_entry(channel_id, "Paladin")
        assert len(entry["status_effects"]) == 2
        assert entry["status_effects"]["祝福"] == "永久"
        assert entry["status_effects"]["護盾"] == "2回合"

    @pytest.mark.asyncio
    async def test_add_status_nonexistent(self, channel_id, clean_tracker):
        """Test adding status to non-existent entry."""
        success = await initiative.add_status(channel_id, "Ghost", "狀態", "值")
        assert success is False

    @pytest.mark.asyncio
    async def test_update_status(self, channel_id, clean_tracker, mock_database):
        """Test updating an existing status."""
        await initiative.add_entry(channel_id, "Ranger", 17)
        await initiative.add_status(channel_id, "Ranger", "冰凍", "2回合")
        
        success = await initiative.update_status(channel_id, "Ranger", "冰凍", "1回合")
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Ranger")
        assert entry["status_effects"]["冰凍"] == "1回合"
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_status_nonexistent_status(self, channel_id, clean_tracker):
        """Test updating non-existent status."""
        await initiative.add_entry(channel_id, "Bard", 16)
        success = await initiative.update_status(channel_id, "Bard", "不存在", "值")
        assert success is False

    @pytest.mark.asyncio
    async def test_remove_status(self, channel_id, clean_tracker, mock_database):
        """Test removing a status effect."""
        await initiative.add_entry(channel_id, "Cleric", 15)
        await initiative.add_status(channel_id, "Cleric", "詛咒", "永久")
        
        success = await initiative.remove_status(channel_id, "Cleric", "詛咒")
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Cleric")
        assert "詛咒" not in entry["status_effects"]
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_remove_status_nonexistent(self, channel_id, clean_tracker):
        """Test removing non-existent status."""
        await initiative.add_entry(channel_id, "Druid", 14)
        success = await initiative.remove_status(channel_id, "Druid", "不存在")
        assert success is False

    @pytest.mark.asyncio
    async def test_set_all_status(self, channel_id, clean_tracker, mock_database):
        """Test batch setting all statuses."""
        await initiative.add_entry(channel_id, "Sorcerer", 19)
        
        new_statuses = {"燃燒": "5回合", "虛弱": "3回合", "混亂": "2回合"}
        success = await initiative.set_all_status(channel_id, "Sorcerer", new_statuses)
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Sorcerer")
        assert entry["status_effects"] == new_statuses
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_status_names(self, channel_id, clean_tracker):
        """Test getting status names."""
        await initiative.add_entry(channel_id, "Warlock", 18)
        await initiative.add_status(channel_id, "Warlock", "契約", "永久")
        await initiative.add_status(channel_id, "Warlock", "詛咒", "5回合")
        
        names = await initiative.get_status_names(channel_id, "Warlock")
        
        assert len(names) == 2
        assert "契約" in names
        assert "詛咒" in names

    @pytest.mark.asyncio
    async def test_get_status_names_nonexistent(self, channel_id, clean_tracker):
        """Test getting status names for non-existent entry."""
        names = await initiative.get_status_names(channel_id, "Ghost")
        assert names == []


# ============================================
# TESTS: SORTING AND INITIATIVE
# ============================================


class TestSortingAndInitiative:
    """Test sorting and initiative management."""

    @pytest.mark.asyncio
    async def test_sort_entries_descending(self, channel_id, clean_tracker):
        """Test that entries are sorted by initiative (descending)."""
        await initiative.add_entry(channel_id, "A", 10)
        await initiative.add_entry(channel_id, "B", 25)
        await initiative.add_entry(channel_id, "C", 15)
        
        tracker = await initiative.get_tracker(channel_id)
        
        # Should be sorted: B(25), C(15), A(10)
        assert tracker["entries"][0]["name"] == "B"
        assert tracker["entries"][1]["name"] == "C"
        assert tracker["entries"][2]["name"] == "A"

    @pytest.mark.asyncio
    async def test_set_initiative(self, channel_id, clean_tracker, mock_database):
        """Test changing initiative value."""
        await initiative.add_entry(channel_id, "Warrior", 10)
        success = await initiative.set_initiative(channel_id, "Warrior", 25)
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Warrior")
        assert entry["initiative"] == 25
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_set_initiative_resorts(self, channel_id, clean_tracker):
        """Test that changing initiative re-sorts entries."""
        await initiative.add_entry(channel_id, "A", 10)
        await initiative.add_entry(channel_id, "B", 20)
        
        await initiative.set_initiative(channel_id, "A", 30)
        
        tracker = await initiative.get_tracker(channel_id)
        # Should now be: A(30), B(20)
        assert tracker["entries"][0]["name"] == "A"
        assert tracker["entries"][1]["name"] == "B"

    @pytest.mark.asyncio
    async def test_set_initiative_nonexistent(self, channel_id, clean_tracker):
        """Test setting initiative on non-existent entry."""
        success = await initiative.set_initiative(channel_id, "Ghost", 50)
        assert success is False


# ============================================
# TESTS: CHARACTER SELECTION
# ============================================


class TestCharacterSelection:
    """Test character selection and targeting."""

    @pytest.mark.asyncio
    async def test_select_character(self, channel_id, clean_tracker, mock_database):
        """Test selecting a character."""
        await initiative.add_entry(channel_id, "Target", 15)
        success = await initiative.select_character(channel_id, "Target")
        
        assert success is True
        tracker = await initiative.get_tracker(channel_id)
        assert tracker["selected_character"] == "Target"
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_select_character_nonexistent(self, channel_id, clean_tracker):
        """Test selecting non-existent character."""
        success = await initiative.select_character(channel_id, "Ghost")
        assert success is False

    @pytest.mark.asyncio
    async def test_deselect_character(self, channel_id, clean_tracker, mock_database):
        """Test deselecting character."""
        await initiative.add_entry(channel_id, "Target", 15)
        await initiative.select_character(channel_id, "Target")
        
        success = await initiative.select_character(channel_id, None)
        
        assert success is True
        tracker = await initiative.get_tracker(channel_id)
        assert tracker["selected_character"] is None
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_deselect_with_none_string(self, channel_id, clean_tracker):
        """Test deselecting with 'None' string."""
        await initiative.add_entry(channel_id, "Target", 15)
        await initiative.select_character(channel_id, "Target")
        
        success = await initiative.select_character(channel_id, "None")
        
        assert success is True
        tracker = await initiative.get_tracker(channel_id)
        assert tracker["selected_character"] is None

    @pytest.mark.asyncio
    async def test_get_selected_character(self, channel_id, clean_tracker):
        """Test getting selected character."""
        await initiative.add_entry(channel_id, "Target", 15)
        await initiative.select_character(channel_id, "Target")
        
        selected = await initiative.get_selected_character(channel_id)
        assert selected == "Target"

    @pytest.mark.asyncio
    async def test_get_selected_character_none(self, channel_id, clean_tracker):
        """Test getting selected character when none selected."""
        selected = await initiative.get_selected_character(channel_id)
        assert selected is None

    @pytest.mark.asyncio
    async def test_get_selected_character_deleted(self, channel_id, clean_tracker):
        """Test that deleted selected character is cleared."""
        await initiative.add_entry(channel_id, "Target", 15)
        await initiative.select_character(channel_id, "Target")
        await initiative.remove_entry(channel_id, "Target")
        
        selected = await initiative.get_selected_character(channel_id)
        assert selected is None


# ============================================
# TESTS: FAVORITE DICE
# ============================================


class TestFavoriteDice:
    """Test favorite dice management."""

    @pytest.mark.asyncio
    async def test_add_favorite_dice(self, channel_id, clean_tracker, mock_database):
        """Test adding a favorite dice."""
        await initiative.add_entry(channel_id, "Warrior", 14)
        success = await initiative.add_favorite_dice(
            channel_id, "Warrior", "攻擊", "1d20+5"
        )
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Warrior")
        assert entry["favorite_dice"]["攻擊"] == "1d20+5"
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_add_favorite_dice_multiple(self, channel_id, clean_tracker):
        """Test adding multiple favorite dice."""
        await initiative.add_entry(channel_id, "Mage", 16)
        await initiative.add_favorite_dice(channel_id, "Mage", "火球", "3d6")
        await initiative.add_favorite_dice(channel_id, "Mage", "冰錐", "2d8")
        
        entry = await initiative.get_entry(channel_id, "Mage")
        assert len(entry["favorite_dice"]) == 2
        assert entry["favorite_dice"]["火球"] == "3d6"
        assert entry["favorite_dice"]["冰錐"] == "2d8"

    @pytest.mark.asyncio
    async def test_add_favorite_dice_nonexistent(self, channel_id, clean_tracker):
        """Test adding favorite dice to non-existent entry."""
        success = await initiative.add_favorite_dice(
            channel_id, "Ghost", "骰子", "1d20"
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_remove_favorite_dice(self, channel_id, clean_tracker, mock_database):
        """Test removing a favorite dice."""
        await initiative.add_entry(channel_id, "Ranger", 17)
        await initiative.add_favorite_dice(channel_id, "Ranger", "射擊", "1d20+3")
        
        success = await initiative.remove_favorite_dice(channel_id, "Ranger", "射擊")
        
        assert success is True
        entry = await initiative.get_entry(channel_id, "Ranger")
        assert "射擊" not in entry["favorite_dice"]
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_remove_favorite_dice_nonexistent(self, channel_id, clean_tracker):
        """Test removing non-existent favorite dice."""
        await initiative.add_entry(channel_id, "Bard", 15)
        success = await initiative.remove_favorite_dice(channel_id, "Bard", "不存在")
        assert success is False

    @pytest.mark.asyncio
    async def test_get_favorite_dice_names(self, channel_id, clean_tracker):
        """Test getting favorite dice names."""
        await initiative.add_entry(channel_id, "Cleric", 13)
        await initiative.add_favorite_dice(channel_id, "Cleric", "治療", "2d8+3")
        await initiative.add_favorite_dice(channel_id, "Cleric", "驅邪", "1d20")
        
        names = await initiative.get_favorite_dice_names(channel_id, "Cleric")
        
        assert len(names) == 2
        assert "治療" in names
        assert "驅邪" in names

    @pytest.mark.asyncio
    async def test_get_favorite_dice_names_nonexistent(self, channel_id, clean_tracker):
        """Test getting favorite dice names for non-existent entry."""
        names = await initiative.get_favorite_dice_names(channel_id, "Ghost")
        assert names == []


# ============================================
# TESTS: PERSISTENCE (DB OPERATIONS)
# ============================================


class TestPersistence:
    """Test database persistence operations."""

    @pytest.mark.asyncio
    async def test_save_tracker(self, channel_id, clean_tracker, mock_database):
        """Test saving tracker to database."""
        await initiative.add_entry(channel_id, "Hero", 15)
        await initiative.save_tracker(channel_id)
        
        # Verify Database.execute was called with correct query
        mock_database.execute.assert_called()
        call_args = mock_database.execute.call_args
        assert "INSERT INTO initiative_trackers" in call_args[0][0]
        assert channel_id in call_args[0]

    @pytest.mark.asyncio
    async def test_save_tracker_nonexistent_channel(self, channel_id, mock_database):
        """Test saving tracker for non-existent channel (should not call DB)."""
        await initiative.save_tracker(channel_id)
        
        # Should not call execute if tracker doesn't exist
        mock_database.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_tracker(self, channel_id, mock_database):
        """Test loading tracker from database."""
        tracker_data = {
            "entries": [{"name": "Hero", "initiative": 15}],
            "current_round": 1,
            "current_index": 0,
            "is_active": True
        }
        mock_database.fetchval.return_value = json.dumps(tracker_data)
        
        success = await initiative.load_tracker(channel_id)
        
        assert success is True
        assert channel_id in shared_state.initiative_trackers
        loaded = shared_state.initiative_trackers[channel_id]
        assert loaded["entries"][0]["name"] == "Hero"

    @pytest.mark.asyncio
    async def test_load_tracker_not_found(self, channel_id, mock_database):
        """Test loading tracker that doesn't exist in DB."""
        mock_database.fetchval.return_value = None
        
        success = await initiative.load_tracker(channel_id)
        
        assert success is False

    @pytest.mark.asyncio
    async def test_get_tracker_from_memory(self, channel_id, clean_tracker, mock_database):
        """Test get_tracker returns from memory if available."""
        await initiative.add_entry(channel_id, "Hero", 15)
        
        # Reset mock to track new calls
        mock_database.reset_mock()
        
        tracker = await initiative.get_tracker(channel_id)
        
        # Should not call DB if already in memory
        mock_database.fetchval.assert_not_called()
        assert len(tracker["entries"]) == 1

    @pytest.mark.asyncio
    async def test_get_tracker_from_db(self, channel_id, mock_database):
        """Test get_tracker loads from DB if not in memory."""
        tracker_data = {
            "entries": [{"name": "Loaded", "initiative": 20}],
            "current_round": 1,
            "current_index": 0,
            "is_active": True
        }
        mock_database.fetchval.return_value = json.dumps(tracker_data)
        
        # Clear memory
        shared_state.initiative_trackers.clear()
        
        tracker = await initiative.get_tracker(channel_id)
        
        assert len(tracker["entries"]) == 1
        assert tracker["entries"][0]["name"] == "Loaded"

    @pytest.mark.asyncio
    async def test_get_tracker_creates_new(self, channel_id, mock_database):
        """Test get_tracker creates new if not in memory or DB."""
        mock_database.fetchval.return_value = None
        shared_state.initiative_trackers.clear()
        
        tracker = await initiative.get_tracker(channel_id)
        
        assert tracker["entries"] == []
        assert tracker["current_round"] == 1
        assert tracker["current_index"] == 0
        assert tracker["is_active"] is False

    @pytest.mark.asyncio
    async def test_save_tracker_exception(self, channel_id, clean_tracker, mock_database, mock_log_message):
        """Test save_tracker handles database exceptions."""
        await initiative.add_entry(channel_id, "Hero", 15)
        mock_database.execute.side_effect = Exception("DB Error")
        
        await initiative.save_tracker(channel_id)
        
        mock_log_message.assert_called()
        assert "❌ 儲存先攻表失敗" in str(mock_log_message.call_args)

    @pytest.mark.asyncio
    async def test_load_tracker_exception(self, channel_id, mock_database, mock_log_message):
        """Test load_tracker handles database exceptions."""
        mock_database.fetchval.side_effect = Exception("DB Error")
        
        success = await initiative.load_tracker(channel_id)
        
        assert success is False
        mock_log_message.assert_called()
        assert "❌ 載入先攻表失敗" in str(mock_log_message.call_args)


# ============================================
# TESTS: DISPLAY AND UTILITY
# ============================================


class TestDisplayAndUtility:
    """Test display and utility functions."""

    @pytest.mark.asyncio
    async def test_get_tracker_display_empty(self, channel_id, clean_tracker):
        """Test display of empty tracker."""
        display = await initiative.get_tracker_display(channel_id)
        
        assert "尚無角色" in display
        assert "!init" in display

    @pytest.mark.asyncio
    async def test_get_tracker_display_with_entries(self, channel_id, clean_tracker):
        """Test display of tracker with entries."""
        await initiative.add_entry(channel_id, "Hero", 20)
        await initiative.add_entry(channel_id, "Villain", 15)
        
        display = await initiative.get_tracker_display(channel_id)
        
        assert "Hero" in display
        assert "Villain" in display
        assert "先攻: 20" in display
        assert "先攻: 15" in display

    @pytest.mark.asyncio
    async def test_get_tracker_display_with_stats(self, channel_id, clean_tracker):
        """Test display includes stats."""
        await initiative.add_entry(channel_id, "Warrior", 18)
        await initiative.set_stats(channel_id, "Warrior", hp=100, atk=20, def_=15)
        
        display = await initiative.get_tracker_display(channel_id)
        
        assert "HP: 100" in display
        assert "ATK: 20" in display
        assert "DEF: 15" in display

    @pytest.mark.asyncio
    async def test_get_tracker_display_with_status(self, channel_id, clean_tracker):
        """Test display includes status effects."""
        await initiative.add_entry(channel_id, "Mage", 16)
        await initiative.add_status(channel_id, "Mage", "中毒", "3回合")
        
        display = await initiative.get_tracker_display(channel_id)
        
        assert "中毒" in display
        assert "3回合" in display

    @pytest.mark.asyncio
    async def test_get_tracker_display_with_selected(self, channel_id, clean_tracker):
        """Test display shows selected character."""
        await initiative.add_entry(channel_id, "Target", 15)
        await initiative.select_character(channel_id, "Target")
        
        display = await initiative.get_tracker_display(channel_id)
        
        assert "當前鎖定" in display
        assert "Target" in display

    @pytest.mark.asyncio
    async def test_get_entry_names(self, channel_id, clean_tracker):
        """Test getting all entry names."""
        await initiative.add_entry(channel_id, "A", 20)
        await initiative.add_entry(channel_id, "B", 15)
        await initiative.add_entry(channel_id, "C", 10)
        
        names = await initiative.get_entry_names(channel_id)
        
        assert len(names) == 3
        assert "A" in names
        assert "B" in names
        assert "C" in names

    @pytest.mark.asyncio
    async def test_end_combat(self, channel_id, clean_tracker, mock_database):
        """Test ending combat."""
        await initiative.add_entry(channel_id, "Hero", 20)
        await initiative.add_entry(channel_id, "Villain", 15)
        await initiative.set_stats(channel_id, "Hero", hp=100)
        await initiative.set_stats(channel_id, "Villain", hp=50)
        
        tracker = await initiative.get_tracker(channel_id)
        tracker["current_round"] = 5
        
        summary = await initiative.end_combat(channel_id)
        
        assert summary["total_rounds"] == 5
        assert summary["total_characters"] == 2
        assert len(summary["survivors"]) == 2
        
        # Tracker should be reset
        assert len(tracker["entries"]) == 0
        assert tracker["current_round"] == 1
        assert tracker["is_active"] is False
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_favorite_dice_display_empty(self, channel_id, clean_tracker):
        """Test favorite dice display when empty."""
        display = await initiative.get_favorite_dice_display(channel_id)
        assert display is None

    @pytest.mark.asyncio
    async def test_get_favorite_dice_display_with_dice(self, channel_id, clean_tracker):
        """Test favorite dice display with entries."""
        await initiative.add_entry(channel_id, "Warrior", 14)
        await initiative.add_favorite_dice(channel_id, "Warrior", "攻擊", "1d20+5")
        await initiative.add_favorite_dice(channel_id, "Warrior", "防禦", "1d20+3")
        
        display = await initiative.get_favorite_dice_display(channel_id)
        
        assert display is not None
        assert "Warrior" in display
        assert "攻擊" in display
        assert "防禦" in display


# ============================================
# TESTS: REROLL FUNCTIONALITY
# ============================================


class TestReroll:
    """Test reroll functionality."""

    @pytest.mark.asyncio
    async def test_reroll_all_initiative(self, channel_id, clean_tracker, mock_database, mock_dice_functions):
        """Test rerolling all initiative values."""
        mock_dice_functions["parse_and_roll"].return_value = (18, [])
        
        await initiative.add_entry(channel_id, "A", 10, formula="1d20+2")
        await initiative.add_entry(channel_id, "B", 15, formula="1d20+5")
        
        results = await initiative.reroll_all_initiative(channel_id)
        
        assert len(results) == 2
        # Results are in order of entries in tracker (which is sorted by initiative)
        # B has higher initiative (15) so it comes first
        assert results[0][0] == "B"
        assert results[0][1] == 15  # old
        assert results[0][2] == 18  # new
        
        assert results[1][0] == "A"
        assert results[1][1] == 10  # old
        assert results[1][2] == 18  # new
        
        # Tracker should be updated
        tracker = await initiative.get_tracker(channel_id)
        assert tracker["entries"][0]["initiative"] == 18
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_reroll_all_initiative_no_formula(self, channel_id, clean_tracker):
        """Test reroll when entry has no formula."""
        await initiative.add_entry(channel_id, "A", 10)  # No formula
        
        results = await initiative.reroll_all_initiative(channel_id)
        
        assert len(results) == 1
        assert results[0][2] == 0  # Should be 0
        assert "無公式" in results[0][3]


# ============================================
# TESTS: ADD ENTRY WITH ROLL
# ============================================


class TestAddEntryWithRoll:
    """Test adding entry with dice roll."""

    @pytest.mark.asyncio
    async def test_add_entry_with_roll_success(self, channel_id, clean_tracker, mock_dice_functions):
        """Test adding entry with successful roll."""
        mock_dice_functions["parse_and_roll"].return_value = (22, [])
        
        success, result, roll_detail = await initiative.add_entry_with_roll(
            channel_id, "1d20+2", "Hero"
        )
        
        assert success is True
        assert result == 22
        entry = await initiative.get_entry(channel_id, "Hero")
        assert entry["initiative"] == 22

    @pytest.mark.asyncio
    async def test_add_entry_with_roll_duplicate(self, channel_id, clean_tracker, mock_dice_functions):
        """Test adding duplicate entry with roll."""
        mock_dice_functions["parse_and_roll"].return_value = (15, [])
        
        await initiative.add_entry_with_roll(channel_id, "1d20", "Hero")
        success, msg, _ = await initiative.add_entry_with_roll(channel_id, "1d20", "Hero")
        
        assert success is False
        assert "角色名稱已存在" in msg

    @pytest.mark.asyncio
    async def test_add_entry_with_roll_parse_error(self, channel_id, clean_tracker, mock_dice_functions):
        """Test adding entry with invalid formula."""
        from utils.dice import DiceParseError
        mock_dice_functions["parse_and_roll"].side_effect = DiceParseError("Invalid formula")
        
        success, msg, _ = await initiative.add_entry_with_roll(
            channel_id, "invalid", "Hero"
        )
        
        assert success is False
        assert "Invalid formula" in msg


# ============================================
# TESTS: ROLL FAVORITE DICE (COMPLEX CASES)
# ============================================


class TestRollFavoriteDice:
    """Test rolling favorite dice with various scenarios."""

    @pytest.mark.asyncio
    async def test_roll_favorite_dice_nonexistent_entry(self, channel_id, clean_tracker):
        """Test rolling dice for non-existent entry."""
        success, msg, formula, result = await initiative.roll_favorite_dice(
            channel_id, "Ghost", "骰子"
        )
        
        assert success is False
        assert msg == "找不到角色"

    @pytest.mark.asyncio
    async def test_roll_favorite_dice_nonexistent_dice(self, channel_id, clean_tracker):
        """Test rolling non-existent favorite dice."""
        await initiative.add_entry(channel_id, "Warrior", 14)
        
        success, msg, formula, result = await initiative.roll_favorite_dice(
            channel_id, "Warrior", "不存在"
        )
        
        assert success is False
        assert msg == "找不到常用骰"

    @pytest.mark.asyncio
    async def test_roll_favorite_dice_simple(self, channel_id, clean_tracker, mock_dice_functions):
        """Test rolling a simple favorite dice."""
        mock_dice_functions["parse_and_roll"].return_value = (15, [])
        
        await initiative.add_entry(channel_id, "Mage", 16)
        await initiative.add_favorite_dice(channel_id, "Mage", "火球", "3d6")
        
        success, result, formula, roll_detail = await initiative.roll_favorite_dice(
            channel_id, "Mage", "火球"
        )
        
        assert success is True
        assert result == 15
        assert formula == "3d6"

    @pytest.mark.asyncio
    async def test_roll_favorite_dice_with_repeat(self, channel_id, clean_tracker, mock_dice_functions):
        """Test rolling favorite dice multiple times."""
        mock_dice_functions["parse_and_roll"].return_value = (10, [])
        
        await initiative.add_entry(channel_id, "Ranger", 17)
        await initiative.add_favorite_dice(channel_id, "Ranger", "射擊", "1d20+3")
        
        success, results, formula, roll_detail = await initiative.roll_favorite_dice(
            channel_id, "Ranger", "射擊"
        )
        
        assert success is True
        assert formula == "1d20+3"

    @pytest.mark.asyncio
    async def test_roll_favorite_dice_parse_error(self, channel_id, clean_tracker, mock_dice_functions):
        """Test rolling favorite dice with invalid formula."""
        from utils.dice import DiceParseError
        mock_dice_functions["parse_and_roll"].side_effect = DiceParseError("Bad formula")
        
        await initiative.add_entry(channel_id, "Cleric", 13)
        await initiative.add_favorite_dice(channel_id, "Cleric", "治療", "invalid")
        
        success, msg, formula, result = await initiative.roll_favorite_dice(
            channel_id, "Cleric", "治療"
        )
        
        assert success is False
        assert "Bad formula" in msg
