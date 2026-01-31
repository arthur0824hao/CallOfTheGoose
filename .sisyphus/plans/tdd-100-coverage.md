# TDD Implementation Plan: 100% Test Coverage for Discord Bot

## TL;DR

> **Quick Summary**: Implement a comprehensive TDD testing infrastructure for the Discord bot project, starting with pure utility functions and progressively adding tests for DB-dependent modules, cogs, and UI components.
> 
> **Deliverables**:
> - pytest infrastructure with async support and coverage reporting
> - Unit tests for all `utils/` modules (dice, initiative, music, permissions, shared_state)
> - Integration tests for database operations with test DB
> - Command tests for all cogs with mocked Discord context
> - UI component tests with mocked interactions
> - 100% code coverage target
> 
> **Estimated Effort**: Large (40-60 hours)
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 (Infrastructure) → Task 2 (dice.py) → Task 5 (initiative.py) → Task 8 (cogs)

---

## Context

### Original Request
Create a comprehensive TDD plan for the Discord bot project to achieve 100% test coverage, including infrastructure setup, test strategy for all modules, and refactoring recommendations for testability.

### Interview Summary
**Key Discussions**:
- Database testing: Both mock-based (unit) and real test DB (integration)
- Discord testing: Manual mock fixtures (no dpytest dependency)
- Priority: Utils-first approach (pure → DB-dependent → cogs → UI)
- Randomness: Mock `random.randint` for deterministic dice tests

**Research Findings**:
- `utils/dice.py` is highly testable (pure functions, 705 lines)
- `utils/initiative.py` requires async DB mocking (641 lines)
- `utils/music.py` has complex dependencies (yt-dlp, file I/O, 840 lines)
- UI components require Discord interaction mocking (1300+ lines)
- No existing tests in the project

### Codebase Structure
```
DiscordBot/
├── bot.py                    # Entry point
├── cogs/                     # Discord commands
│   ├── dice.py              # !r command
│   ├── general.py           # General commands
│   ├── initiative.py        # !init command
│   └── music.py             # Music commands
├── utils/                    # Core logic
│   ├── dice.py              # Dice parser/roller (HIGHLY TESTABLE)
│   ├── initiative.py        # Initiative tracker (ASYNC, DB)
│   ├── music.py             # Music utilities (COMPLEX)
│   ├── character_storage.py # Character DB ops (ASYNC, DB)
│   ├── shared_state.py      # Global state
│   ├── permissions.py       # Auth check (SIMPLE)
│   └── db.py                # Database class
└── ui/                       # Discord UI components
    ├── init_views.py        # Initiative UI
    ├── init_buttons.py      # Initiative buttons
    ├── music_views.py       # Music UI
    └── music_buttons.py     # Music buttons
```

---

## Work Objectives

### Core Objective
Establish a robust TDD testing infrastructure and achieve 100% code coverage for the Discord bot project through systematic test implementation.

### Concrete Deliverables
- `tests/` directory with organized test structure
- `pytest.ini` configuration file
- `tests/conftest.py` with shared fixtures
- Unit tests for all `utils/*.py` modules
- Integration tests for database operations
- Command tests for all `cogs/*.py` modules
- UI component tests for `ui/*.py` modules
- Coverage report configuration

### Definition of Done
- [ ] `pytest --cov=. --cov-report=term-missing` shows 100% coverage
- [ ] All tests pass: `pytest` returns exit code 0
- [ ] No flaky tests (run 3 times consecutively without failure)

### Must Have
- pytest + pytest-asyncio + pytest-cov installed
- Deterministic dice tests (mocked randomness)
- Database mock fixtures for unit tests
- Discord context mock fixtures
- Test database configuration for integration tests

### Must NOT Have (Guardrails)
- No real Discord bot connections in tests
- No production database modifications
- No external API calls (yt-dlp) in unit tests
- No flaky tests depending on timing
- No hardcoded test data that could break with schema changes

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (will be created)
- **User wants tests**: TDD
- **Framework**: pytest + pytest-asyncio + pytest-cov

### TDD Workflow

Each TODO follows RED-GREEN-REFACTOR:

**Task Structure:**
1. **RED**: Write failing test first
   - Test file: `tests/unit/test_*.py` or `tests/integration/test_*.py`
   - Test command: `pytest tests/unit/test_*.py -v`
   - Expected: FAIL (test exists, implementation verified)
2. **GREEN**: Verify existing implementation passes
   - Command: `pytest tests/unit/test_*.py -v`
   - Expected: PASS
3. **COVERAGE**: Check coverage improvement
   - Command: `pytest --cov=utils --cov-report=term-missing`
   - Expected: Increased coverage percentage

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Infrastructure setup
└── (blocks all other tasks)

Wave 2 (After Wave 1):
├── Task 2: utils/dice.py tests (pure functions)
├── Task 3: utils/permissions.py tests (simple)
└── Task 4: utils/shared_state.py tests (state management)

Wave 3 (After Wave 2):
├── Task 5: utils/initiative.py tests (requires fixtures from Wave 2)
├── Task 6: utils/character_storage.py tests
├── Task 7: utils/music.py tests
└── Task 8: utils/db.py integration tests

Wave 4 (After Wave 3):
├── Task 9: cogs/dice.py tests
├── Task 10: cogs/initiative.py tests
├── Task 11: cogs/music.py tests
└── Task 12: ui/ component tests

Critical Path: Task 1 → Task 2 → Task 5 → Task 9
Parallel Speedup: ~50% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | All | None |
| 2 | 1 | 5, 9 | 3, 4 |
| 3 | 1 | 9, 10, 11 | 2, 4 |
| 4 | 1 | 5, 6, 7 | 2, 3 |
| 5 | 2, 4 | 10 | 6, 7 |
| 6 | 4 | 10 | 5, 7 |
| 7 | 4 | 11 | 5, 6 |
| 8 | 1 | 5, 6, 7 | 2, 3, 4 |
| 9 | 2, 3 | 12 | 10, 11 |
| 10 | 3, 5, 6 | 12 | 9, 11 |
| 11 | 3, 7 | 12 | 9, 10 |
| 12 | 9, 10, 11 | None | None |

---

## TODOs

### Wave 1: Infrastructure

- [ ] 1. Setup Test Infrastructure

  **What to do**:
  - Install testing dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`
  - Create `tests/` directory structure mirroring source
  - Create `pytest.ini` with async mode and coverage settings
  - Create `tests/conftest.py` with base fixtures
  - Create mock factories for Database, Discord ctx, and interactions
  - Verify setup with a simple passing test

  **Must NOT do**:
  - Install dpytest (using manual mocks per user decision)
  - Create real database connections in fixtures
  - Add unnecessary dependencies

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuration and setup task, straightforward implementation
  - **Skills**: [`git-master`]
    - `git-master`: For proper commit of infrastructure files

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (must complete first)
  - **Blocks**: Tasks 2-12
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `requirements.txt` - Current dependencies to extend

  **API/Type References**:
  - `utils/db.py:Database` - Class to mock (lines 12-54)
  - `utils/shared_state.py:get_tracker()` - Function to mock (lines 57-75)

  **External References**:
  - pytest-asyncio docs: https://pytest-asyncio.readthedocs.io/
  - pytest-cov docs: https://pytest-cov.readthedocs.io/

  **WHY Each Reference Matters**:
  - `requirements.txt`: Need to know existing deps to avoid conflicts
  - `Database` class: Primary mock target for all DB-dependent tests
  - pytest-asyncio: Required for testing async functions throughout codebase

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  # Agent runs:
  cd D:\code\雜項\DiscordBot
  
  # 1. Check dependencies installed
  pip list | grep -E "pytest|pytest-asyncio|pytest-cov|pytest-mock"
  # Assert: All 4 packages listed
  
  # 2. Check directory structure
  python -c "import os; assert os.path.isfile('tests/conftest.py'), 'conftest.py missing'"
  # Assert: Exit code 0
  
  # 3. Check pytest.ini exists
  python -c "import os; assert os.path.isfile('pytest.ini'), 'pytest.ini missing'"
  # Assert: Exit code 0
  
  # 4. Run test discovery
  pytest --collect-only
  # Assert: "1 test collected" or more, no errors
  
  # 5. Run initial test
  pytest tests/ -v
  # Assert: PASSED, exit code 0
  ```

  **Evidence to Capture:**
  - [ ] pip list output showing installed packages
  - [ ] pytest --collect-only output
  - [ ] pytest tests/ -v output showing pass

  **Commit**: YES
  - Message: `test(infra): add pytest infrastructure with async support and fixtures`
  - Files: `pytest.ini`, `tests/conftest.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `requirements.txt`
  - Pre-commit: `pytest tests/ -v`

---

### Wave 2: Pure Utility Tests

- [ ] 2. Test utils/dice.py (Tokenizer, Parser, Formatters)

  **What to do**:
  - Create `tests/unit/test_dice.py`
  - Test `Tokenizer` class:
    - Valid tokens: numbers, dice (NdM), operators (+,-,*,/), parentheses
    - Invalid input handling: invalid characters, empty input
    - Edge cases: max dice count (100), max faces (1000)
  - Test `DiceParser` class:
    - Basic expressions: `2d6`, `1d20+5`, `2d6*3`
    - Complex expressions: `(2d6+3)*2`, `1d20+1d6+5`
    - Keep highest/lowest: `3d20kh2`, `5d6kl3`
    - Unary operators: `-1d4`, `+5`
    - Error cases: division by zero, unmatched parentheses
  - Test `parse_and_roll()` high-level API
  - Test `roll_coc_dice()` for Call of Cthulhu mechanics
  - Test formatting functions: `format_dice_result()`, `format_coc_result()`
  - Mock `random.randint` for deterministic results

  **Must NOT do**:
  - Test with real randomness (always mock)
  - Skip edge cases and error conditions
  - Create tests that depend on execution order

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Heavy algorithmic testing with parser logic, needs attention to detail
  - **Skills**: None needed
    - No specialized skills required for pure Python unit tests

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4)
  - **Blocks**: Tasks 5, 9
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `utils/dice.py:Tokenizer` (lines 87-248) - Lexical analyzer to test
  - `utils/dice.py:DiceParser` (lines 253-401) - Parser to test
  - `utils/dice.py:parse_and_roll()` (lines 522-561) - Main API

  **API/Type References**:
  - `utils/dice.py:TokenType` (lines 16-27) - Token enum values
  - `utils/dice.py:DiceRoll` (lines 42-61) - Result dataclass structure
  - `utils/dice.py:CoCRollResult` (lines 65-78) - CoC result structure
  - `utils/dice.py:DiceParseError` (lines 80-82) - Exception to catch

  **Test References**:
  - None (first test file, establishes patterns)

  **Documentation References**:
  - `AGENTS.md:Dice Rolling System` - Command format and parser architecture
  - `AGENTS.md:CoC Mechanics` - Critical success/fumble rules

  **WHY Each Reference Matters**:
  - `Tokenizer`: Core lexical analysis, tests token generation
  - `DiceParser`: Parser logic with operator precedence
  - `AGENTS.md`: Business rules for CoC (critical=1 only, fumble>=96)

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  # Agent runs:
  pytest tests/unit/test_dice.py -v --tb=short
  # Assert: All tests pass
  
  pytest --cov=utils/dice --cov-report=term-missing tests/unit/test_dice.py
  # Assert: Coverage >= 95%
  
  # Verify specific test cases exist
  pytest tests/unit/test_dice.py -v -k "tokenizer" --collect-only
  # Assert: Multiple tests collected for tokenizer
  
  pytest tests/unit/test_dice.py -v -k "coc" --collect-only
  # Assert: Multiple tests collected for CoC
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report showing >= 95% for utils/dice.py

  **Commit**: YES
  - Message: `test(dice): add comprehensive unit tests for dice parser and roller`
  - Files: `tests/unit/test_dice.py`
  - Pre-commit: `pytest tests/unit/test_dice.py -v`

---

- [ ] 3. Test utils/permissions.py

  **What to do**:
  - Create `tests/unit/test_permissions.py`
  - Test `check_authorization()` with authorized user IDs
  - Test `check_authorization()` with unauthorized user IDs
  - Mock Discord context (`ctx`) with `author.id` attribute
  - Verify logging behavior on unauthorized access
  - Test edge cases: None author, missing id attribute

  **Must NOT do**:
  - Use real Discord user objects
  - Modify the AUTHORIZED_USERS set
  - Skip unauthorized access test cases

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small module (15 lines), simple logic
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 4)
  - **Blocks**: Tasks 9, 10, 11
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `utils/permissions.py:check_authorization()` (lines 8-14) - Function to test
  - `utils/permissions.py:AUTHORIZED_USERS` (line 6) - Authorized IDs set

  **WHY Each Reference Matters**:
  - `check_authorization()`: Only function in module, must test both branches
  - `AUTHORIZED_USERS`: Need to know valid IDs for positive tests

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_permissions.py -v
  # Assert: All tests pass
  
  pytest --cov=utils/permissions --cov-report=term-missing tests/unit/test_permissions.py
  # Assert: Coverage = 100%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report showing 100% for utils/permissions.py

  **Commit**: YES
  - Message: `test(permissions): add unit tests for authorization check`
  - Files: `tests/unit/test_permissions.py`
  - Pre-commit: `pytest tests/unit/test_permissions.py -v`

---

- [ ] 4. Test utils/shared_state.py

  **What to do**:
  - Create `tests/unit/test_shared_state.py`
  - Test `get_tracker()` creates new tracker for unknown channel
  - Test `get_tracker()` returns existing tracker for known channel
  - Test `create_empty_tracker()` returns correct structure
  - Test `generate_operation_id()` returns unique UUIDs
  - Add fixture to reset state between tests
  - Test lock objects exist and are asyncio.Lock instances

  **Must NOT do**:
  - Leave global state modified after tests
  - Skip state isolation between test functions
  - Test asyncio.Lock functionality (built-in)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small module (100 lines), state management patterns
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 3)
  - **Blocks**: Tasks 5, 6, 7
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `utils/shared_state.py:get_tracker()` (lines 57-75) - Main function to test
  - `utils/shared_state.py:create_empty_tracker()` (lines 78-85) - Factory function
  - `utils/shared_state.py:initiative_trackers` (line 42) - Global dict to test

  **WHY Each Reference Matters**:
  - `get_tracker()`: Core function used throughout initiative system
  - `initiative_trackers`: Global state that needs reset between tests

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_shared_state.py -v
  # Assert: All tests pass
  
  pytest --cov=utils/shared_state --cov-report=term-missing tests/unit/test_shared_state.py
  # Assert: Coverage >= 90%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for utils/shared_state.py

  **Commit**: YES
  - Message: `test(state): add unit tests for shared state management`
  - Files: `tests/unit/test_shared_state.py`
  - Pre-commit: `pytest tests/unit/test_shared_state.py -v`

---

### Wave 3: Database-Dependent Tests

- [ ] 5. Test utils/initiative.py

  **What to do**:
  - Create `tests/unit/test_initiative.py`
  - Create mock Database fixture that tracks calls
  - Test all async functions with mocked DB:
    - `save_tracker()`, `load_tracker()`, `get_tracker()`
    - `add_entry()`, `add_entry_with_roll()`, `remove_entry()`
    - `select_character()`, `get_selected_character()`
    - `next_turn()`, `prev_turn()`
    - `set_stats()`, `modify_hp()`, `modify_elements()`
    - `add_status()`, `update_status()`, `remove_status()`, `set_all_status()`
    - `add_favorite_dice()`, `remove_favorite_dice()`, `roll_favorite_dice()`
    - `reset_tracker()`, `end_combat()`
    - `get_tracker_display()`, `get_entry_names()`
    - `reroll_all_initiative()`
  - Test edge cases: empty tracker, duplicate names, invalid indices
  - Mock dice rolling for deterministic results in `add_entry_with_roll()`

  **Must NOT do**:
  - Make real database connections
  - Skip async/await syntax in tests
  - Leave shared_state modified after tests

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Complex module with many async functions, needs careful mocking
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 6, 7, 8)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 4

  **References**:

  **Pattern References**:
  - `utils/initiative.py:save_tracker()` (lines 17-33) - DB write pattern
  - `utils/initiative.py:load_tracker()` (lines 36-49) - DB read pattern
  - `utils/initiative.py:add_entry()` (lines 81-112) - Entry creation pattern

  **API/Type References**:
  - `utils/db.py:Database` (lines 12-54) - Class to mock
  - `utils/shared_state.py:initiative_trackers` - State to manage in tests

  **Documentation References**:
  - `AGENTS.md:Initiative Tracker` - Feature description and data structure

  **WHY Each Reference Matters**:
  - `save_tracker()`: Pattern for all DB write operations
  - `Database` class: Must mock `execute()`, `fetchval()`, `fetch()` methods

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_initiative.py -v
  # Assert: All tests pass
  
  pytest --cov=utils/initiative --cov-report=term-missing tests/unit/test_initiative.py
  # Assert: Coverage >= 90%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for utils/initiative.py

  **Commit**: YES
  - Message: `test(initiative): add unit tests for initiative tracker logic`
  - Files: `tests/unit/test_initiative.py`
  - Pre-commit: `pytest tests/unit/test_initiative.py -v`

---

- [ ] 6. Test utils/character_storage.py

  **What to do**:
  - Create `tests/unit/test_character_storage.py`
  - Test all async functions with mocked DB:
    - `save_character()` with various field selections
    - `get_character()` for existing and non-existing characters
    - `get_all_names()` empty and populated cases
    - `delete_character()` success and failure cases
  - Test JSON serialization/deserialization
  - Test error handling when DB operations fail

  **Must NOT do**:
  - Make real database connections
  - Skip error handling test cases

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small module (93 lines), straightforward CRUD operations
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 5, 7, 8)
  - **Blocks**: Task 10
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `utils/character_storage.py:save_character()` (lines 9-56) - Upsert pattern
  - `utils/character_storage.py:get_character()` (lines 58-68) - Read pattern

  **WHY Each Reference Matters**:
  - `save_character()`: Complex logic with field selection and JSON handling

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_character_storage.py -v
  # Assert: All tests pass
  
  pytest --cov=utils/character_storage --cov-report=term-missing tests/unit/test_character_storage.py
  # Assert: Coverage >= 95%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for utils/character_storage.py

  **Commit**: YES
  - Message: `test(character): add unit tests for character storage operations`
  - Files: `tests/unit/test_character_storage.py`
  - Pre-commit: `pytest tests/unit/test_character_storage.py -v`

---

- [ ] 7. Test utils/music.py

  **What to do**:
  - Create `tests/unit/test_music.py`
  - Test pure functions without mocking:
    - `sanitize_filename()` with various inputs
    - `clean_string()` with special characters
    - `get_next_index()` index calculation
    - `reorganize_musicsheet()` reindexing logic
  - Test file I/O functions with mocked file system:
    - `log_message()`, `log_error()` - mock open()
    - `load_musicsheet()`, `save_musicsheet()` - mock file operations
    - `find_downloaded_file()` - mock os.listdir()
    - `check_audio_file()` - mock os.path.exists(), open()
  - Test musicsheet system functions:
    - `init_musicsheet_system()`, `list_musicsheets()`
    - `create_musicsheet()`, `delete_musicsheet()`, `switch_musicsheet()`
  - Mock yt-dlp for `download_song()` tests
  - Skip `play_next()` complex voice client tests (covered in cogs)

  **Must NOT do**:
  - Actually download files from YouTube
  - Create real files in song/ directory
  - Make real network requests

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Large module (840 lines), complex mocking requirements
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 5, 6, 8)
  - **Blocks**: Task 11
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `utils/music.py:sanitize_filename()` (lines 100-104) - Pure function
  - `utils/music.py:load_musicsheet()` (lines 59-84) - File read pattern
  - `utils/music.py:download_song()` (lines 227-296) - External API usage

  **WHY Each Reference Matters**:
  - `sanitize_filename()`: Used throughout, must handle edge cases
  - `load_musicsheet()`: JSON parsing with error handling

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_music.py -v
  # Assert: All tests pass
  
  pytest --cov=utils/music --cov-report=term-missing tests/unit/test_music.py
  # Assert: Coverage >= 80% (some complex paths hard to test)
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for utils/music.py

  **Commit**: YES
  - Message: `test(music): add unit tests for music utilities`
  - Files: `tests/unit/test_music.py`
  - Pre-commit: `pytest tests/unit/test_music.py -v`

---

- [ ] 8. Test utils/db.py (Integration Tests)

  **What to do**:
  - Create `tests/integration/test_db.py`
  - Create test database configuration (separate from production)
  - Test `Database` class methods with real PostgreSQL:
    - `get_pool()` connection creation
    - `execute()` with INSERT/UPDATE
    - `fetch()`, `fetchrow()`, `fetchval()` with SELECT
    - `close()` pool cleanup
  - Test `init_db()` schema creation
  - Add cleanup fixture to reset test data between tests
  - Mark tests with `@pytest.mark.integration` for optional skip

  **Must NOT do**:
  - Use production database
  - Leave test data after test run
  - Run integration tests in CI without DB available

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Database integration requires careful setup and teardown
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 5, 6, 7)
  - **Blocks**: Tasks 5, 6, 7 (provides test patterns)
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `utils/db.py:Database` (lines 12-54) - Class under test
  - `utils/db.py:init_db()` (lines 56-80) - Schema setup

  **External References**:
  - asyncpg docs: https://magicstack.github.io/asyncpg/current/

  **WHY Each Reference Matters**:
  - `Database` class: Core persistence layer, integration tests verify real behavior

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  # Skip if no test DB available
  pytest tests/integration/test_db.py -v -m integration || echo "Integration tests skipped (no DB)"
  # Assert: Tests pass or skip gracefully
  
  pytest --cov=utils/db --cov-report=term-missing tests/integration/test_db.py -m integration || true
  # Assert: Coverage report generated if tests ran
  ```

  **Evidence to Capture:**
  - [ ] pytest output (pass or skip)
  - [ ] Coverage report if tests ran

  **Commit**: YES
  - Message: `test(db): add integration tests for database operations`
  - Files: `tests/integration/test_db.py`, `tests/integration/__init__.py`
  - Pre-commit: `pytest tests/integration/ -v -m integration || true`

---

### Wave 4: Cogs and UI Tests

- [ ] 9. Test cogs/dice.py

  **What to do**:
  - Create `tests/unit/test_cogs_dice.py`
  - Create mock Discord context fixture with:
    - `ctx.author`, `ctx.send()`, `ctx.command`
  - Test `Dice.roll_command()`:
    - Basic dice rolls: `!r 1d20`, `!r 2d6+5`
    - Repeat syntax: `!r .5 1d20`
    - CoC syntax: `!r cc 65`, `!r cc1 65`, `!r ccn2 50`
    - Error handling: invalid formulas, out-of-range values
    - Long output truncation
  - Verify `ctx.send()` called with expected messages
  - Mock `log_message()` to verify logging

  **Must NOT do**:
  - Create real Discord bot instance
  - Skip authorization check tests
  - Ignore error message format

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Command testing requires careful mock setup
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 10, 11)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 2, 3

  **References**:

  **Pattern References**:
  - `cogs/dice.py:roll_command()` (lines 13-163) - Main command
  - `tests/conftest.py` - Mock ctx fixture (created in Task 1)

  **API/Type References**:
  - `utils/dice.py:parse_and_roll()` - Called by command
  - `utils/dice.py:format_dice_result()` - Output formatting

  **WHY Each Reference Matters**:
  - `roll_command()`: Large method with multiple branches, needs comprehensive testing

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_cogs_dice.py -v
  # Assert: All tests pass
  
  pytest --cov=cogs/dice --cov-report=term-missing tests/unit/test_cogs_dice.py
  # Assert: Coverage >= 95%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for cogs/dice.py

  **Commit**: YES
  - Message: `test(cogs): add unit tests for dice cog commands`
  - Files: `tests/unit/test_cogs_dice.py`
  - Pre-commit: `pytest tests/unit/test_cogs_dice.py -v`

---

- [ ] 10. Test cogs/initiative.py

  **What to do**:
  - Create `tests/unit/test_cogs_initiative.py`
  - Test `Initiative` cog commands:
    - `!init` - Display tracker
    - `!init add <name> <value>` - Add entry
    - `!init <formula> <name>` - Add with roll
    - `!init next`, `!init remove`, `!init stats`, etc.
    - `!char list`, `!char show`, `!char delete`
  - Test `display_init_ui()` helper method
  - Mock `utils/initiative.py` functions
  - Mock Discord views and messages

  **Must NOT do**:
  - Create real Discord connections
  - Test UI button callbacks here (covered in Task 12)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Complex cog with many subcommands
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 9, 11)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 3, 5, 6

  **References**:

  **Pattern References**:
  - `cogs/initiative.py:init_command()` (lines 89-277) - Main command
  - `cogs/initiative.py:char_command` (lines 279-332) - Character commands

  **WHY Each Reference Matters**:
  - `init_command()`: Large command with many subcommands and edge cases

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_cogs_initiative.py -v
  # Assert: All tests pass
  
  pytest --cov=cogs/initiative --cov-report=term-missing tests/unit/test_cogs_initiative.py
  # Assert: Coverage >= 90%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for cogs/initiative.py

  **Commit**: YES
  - Message: `test(cogs): add unit tests for initiative cog commands`
  - Files: `tests/unit/test_cogs_initiative.py`
  - Pre-commit: `pytest tests/unit/test_cogs_initiative.py -v`

---

- [ ] 11. Test cogs/music.py and cogs/general.py

  **What to do**:
  - Create `tests/unit/test_cogs_music.py`
  - Create `tests/unit/test_cogs_general.py`
  - Test music commands with mocked voice client:
    - `!play`, `!skip`, `!stop`, `!queue`, etc.
    - Mock `voice_client.play()`, `is_playing()`, `is_connected()`
  - Test general commands
  - Skip complex audio streaming tests (hard to mock)

  **Must NOT do**:
  - Actually play audio
  - Download real files
  - Create real voice connections

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Complex mocking for voice client
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 9, 10)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 3, 7

  **References**:

  **Pattern References**:
  - `cogs/music.py` - Music commands (need to read file)
  - `cogs/general.py` - General commands (need to read file)

  **WHY Each Reference Matters**:
  - Complex voice client interaction patterns need consistent mocking

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_cogs_music.py tests/unit/test_cogs_general.py -v
  # Assert: All tests pass
  
  pytest --cov=cogs --cov-report=term-missing tests/unit/test_cogs_*.py
  # Assert: Combined cogs coverage >= 80%
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for cogs/

  **Commit**: YES
  - Message: `test(cogs): add unit tests for music and general cogs`
  - Files: `tests/unit/test_cogs_music.py`, `tests/unit/test_cogs_general.py`
  - Pre-commit: `pytest tests/unit/test_cogs_music.py tests/unit/test_cogs_general.py -v`

---

- [ ] 12. Test UI Components (Views, Buttons, Modals)

  **What to do**:
  - Create `tests/unit/test_ui_init.py`
  - Create mock Discord Interaction fixture
  - Test initiative UI components:
    - `InitiativeTrackerView` setup
    - Modal `on_submit()` callbacks: `InitAddModal`, `InitStatsModal`, etc.
    - Button callbacks: `InitNextButton`, `InitPrevButton`, etc.
    - Select menu callbacks: `InitTargetSelect`, `InitCharacterSelect`
  - Test `refresh_tracker_view()` helper
  - Mock all Discord UI primitives

  **Must NOT do**:
  - Test actual Discord rendering
  - Skip callback error handling
  - Create real Discord interactions

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Large UI module (1300+ lines), complex interaction patterns
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (final task)
  - **Blocks**: None (final)
  - **Blocked By**: Tasks 9, 10, 11

  **References**:

  **Pattern References**:
  - `ui/init_views.py:InitAddModal.on_submit()` (lines 76-105) - Modal callback
  - `ui/init_views.py:InitTargetSelect.callback()` (lines 1238-1253) - Select callback
  - `ui/init_views.py:refresh_tracker_view()` (lines 1256-1332) - Helper

  **WHY Each Reference Matters**:
  - Modal callbacks contain business logic that needs testing
  - `refresh_tracker_view()` coordinates multiple async operations

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  pytest tests/unit/test_ui_init.py -v
  # Assert: All tests pass
  
  pytest --cov=ui --cov-report=term-missing tests/unit/test_ui_*.py
  # Assert: UI coverage >= 70% (some Discord primitives hard to test)
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests pass
  - [ ] Coverage report for ui/

  **Commit**: YES
  - Message: `test(ui): add unit tests for initiative UI components`
  - Files: `tests/unit/test_ui_init.py`
  - Pre-commit: `pytest tests/unit/test_ui_init.py -v`

---

- [ ] 13. Final Coverage Verification and CI Configuration

  **What to do**:
  - Run full test suite with coverage report
  - Identify any uncovered lines and add targeted tests
  - Create `.coveragerc` for coverage configuration
  - Add coverage thresholds to fail if below target
  - Create GitHub Actions workflow for CI (optional)
  - Document test running instructions in README

  **Must NOT do**:
  - Accept coverage below 95% without justification
  - Skip failing tests
  - Merge without green CI

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuration and documentation task
  - **Skills**: [`git-master`]
    - For final commit with all changes

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (final verification)
  - **Blocks**: None (final)
  - **Blocked By**: Tasks 1-12

  **References**:

  **Documentation References**:
  - pytest-cov: https://pytest-cov.readthedocs.io/en/latest/config.html

  **WHY Each Reference Matters**:
  - Coverage configuration ensures CI enforcement

  **Acceptance Criteria**:

  **Automated Verification:**
  ```bash
  # Run full test suite
  pytest --cov=. --cov-report=term-missing --cov-report=html
  # Assert: Exit code 0, all tests pass
  
  # Check coverage
  pytest --cov=. --cov-fail-under=95
  # Assert: Exit code 0 (coverage >= 95%)
  
  # Verify HTML report generated
  python -c "import os; assert os.path.isfile('htmlcov/index.html')"
  # Assert: Exit code 0
  ```

  **Evidence to Capture:**
  - [ ] Full pytest output
  - [ ] Coverage summary showing >= 95%
  - [ ] htmlcov/index.html exists

  **Commit**: YES
  - Message: `test(ci): add coverage configuration and final verification`
  - Files: `.coveragerc`, `README.md` (test instructions section)
  - Pre-commit: `pytest --cov=. --cov-fail-under=95`

---

## Commit Strategy

| After Task | Message | Key Files | Verification |
|------------|---------|-----------|--------------|
| 1 | `test(infra): add pytest infrastructure` | pytest.ini, conftest.py | `pytest --collect-only` |
| 2 | `test(dice): add dice parser tests` | test_dice.py | `pytest tests/unit/test_dice.py` |
| 3 | `test(permissions): add auth tests` | test_permissions.py | `pytest tests/unit/test_permissions.py` |
| 4 | `test(state): add state tests` | test_shared_state.py | `pytest tests/unit/test_shared_state.py` |
| 5 | `test(initiative): add tracker tests` | test_initiative.py | `pytest tests/unit/test_initiative.py` |
| 6 | `test(character): add storage tests` | test_character_storage.py | `pytest tests/unit/test_character_storage.py` |
| 7 | `test(music): add music utility tests` | test_music.py | `pytest tests/unit/test_music.py` |
| 8 | `test(db): add integration tests` | test_db.py | `pytest tests/integration/ -m integration` |
| 9 | `test(cogs): add dice cog tests` | test_cogs_dice.py | `pytest tests/unit/test_cogs_dice.py` |
| 10 | `test(cogs): add initiative cog tests` | test_cogs_initiative.py | `pytest tests/unit/test_cogs_initiative.py` |
| 11 | `test(cogs): add music/general tests` | test_cogs_music.py, test_cogs_general.py | `pytest tests/unit/test_cogs_*.py` |
| 12 | `test(ui): add UI component tests` | test_ui_init.py | `pytest tests/unit/test_ui_*.py` |
| 13 | `test(ci): final verification` | .coveragerc, README.md | `pytest --cov=. --cov-fail-under=95` |

---

## Success Criteria

### Verification Commands
```bash
# Full test suite
pytest -v
# Expected: All tests pass

# Coverage check
pytest --cov=. --cov-report=term-missing --cov-fail-under=95
# Expected: Coverage >= 95%, exit code 0

# Integration tests (optional, requires DB)
pytest tests/integration/ -v -m integration
# Expected: Pass or skip gracefully
```

### Final Checklist
- [ ] All "Must Have" requirements present
- [ ] All "Must NOT Have" guardrails respected
- [ ] All tests pass consistently (no flaky tests)
- [ ] Coverage >= 95% overall
- [ ] Each module has dedicated test file
- [ ] Fixtures properly isolate test state
- [ ] Documentation updated with test instructions
