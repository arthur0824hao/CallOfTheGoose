# Draft: TDD Implementation Plan for 100% Test Coverage

## Requirements (confirmed)
- TDD approach for all new tests
- Target: 100% test coverage
- Framework: pytest + pytest-asyncio + pytest-cov
- No existing tests in the project

## Codebase Analysis

### Project Structure
```
DiscordBot/
├── bot.py                    # Entry point, GooseBot class
├── cogs/
│   ├── dice.py              # !r command (dice rolling)
│   ├── general.py           # General commands
│   ├── initiative.py        # !init command (initiative tracker)
│   └── music.py             # Music commands
├── utils/
│   ├── dice.py              # Dice parser/roller (705 lines) - HIGHLY TESTABLE
│   ├── initiative.py        # Initiative tracker logic (641 lines) - NEEDS DB MOCK
│   ├── music.py             # Music utilities (840 lines) - COMPLEX DEPENDENCIES
│   ├── character_storage.py # Character DB operations (93 lines) - NEEDS DB MOCK
│   ├── shared_state.py      # Global state (100 lines) - TESTABILITY CHALLENGE
│   ├── permissions.py       # Auth check (15 lines) - SIMPLE
│   ├── db.py                # Database class (86 lines) - MOCK TARGET
│   ├── debug.py             # Debug utilities
│   ├── setup_postgres.py    # DB setup
│   └── migrate_json_to_db.py
├── ui/
│   ├── views.py             # Re-exports
│   ├── init_views.py        # Initiative UI (1300+ lines) - COMPLEX UI
│   ├── init_buttons.py      # Initiative buttons
│   ├── music_views.py       # Music UI
│   ├── music_buttons.py     # Music buttons
│   └── buttons.py           # Re-exports
└── config/
    └── cookies_config.py    # YouTube cookies config
```

### Testability Assessment

| Module | Testability | Challenges | Strategy |
|--------|-------------|------------|----------|
| `utils/dice.py` | HIGH | None (pure functions) | Direct unit tests |
| `utils/permissions.py` | HIGH | Mock ctx | Simple mock |
| `utils/shared_state.py` | MEDIUM | Global state mutations | Reset state between tests |
| `utils/initiative.py` | MEDIUM | Async DB calls | Mock Database class |
| `utils/character_storage.py` | MEDIUM | Async DB calls | Mock Database class |
| `utils/db.py` | MEDIUM | Real DB connection | Test DB or mock pool |
| `utils/music.py` | LOW | File I/O, external calls | Heavy mocking needed |
| `cogs/*.py` | MEDIUM | Discord.py ctx/bot | dpytest or mock ctx |
| `ui/*.py` | LOW | Discord interactions | Mock interactions |

## Technical Decisions

### Test Framework Stack
- pytest (core)
- pytest-asyncio (async support)
- pytest-cov (coverage reporting)
- unittest.mock / pytest-mock (mocking)
- dpytest (Discord.py testing) - optional

### Mocking Strategy
1. **Database**: Create `AsyncMock` for `Database` class methods
2. **Discord Context**: Create mock `ctx` fixture with common attributes
3. **Voice Client**: Mock `voice_client.play()`, `is_playing()`, etc.
4. **File I/O**: Mock `open()`, `os.path.exists()`, etc.
5. **External APIs**: Mock `yt_dlp`, `aiohttp`

### Directory Structure
```
tests/
├── conftest.py              # Shared fixtures
├── pytest.ini               # pytest configuration
├── unit/
│   ├── test_dice.py         # utils/dice.py tests
│   ├── test_permissions.py  # utils/permissions.py tests
│   ├── test_shared_state.py # utils/shared_state.py tests
│   └── test_initiative.py   # utils/initiative.py tests
├── integration/
│   ├── test_cogs_dice.py    # cogs/dice.py tests
│   ├── test_cogs_init.py    # cogs/initiative.py tests
│   └── test_db.py           # Database integration
└── ui/
    └── test_init_views.py   # UI component tests
```

## Research Findings

### dice.py Analysis (705 lines)
- **Tokenizer class**: Lexical analysis (highly testable)
- **DiceParser class**: Recursive descent parser (highly testable)
- **DiceRoll dataclass**: Result structure (easy to verify)
- **CoCRollResult dataclass**: CoC results (easy to verify)
- **format_* functions**: Output formatting (string comparison)
- **parse_and_roll()**: Main API (integration tests)
- **roll_coc_dice()**: CoC mechanics (stateful, mock random)

### initiative.py Analysis (641 lines)
- All functions are async
- Heavy reliance on `Database` class
- Uses `shared_state` for in-memory caching
- Functions to test:
  - `save_tracker()`, `load_tracker()`, `get_tracker()`
  - `add_entry()`, `remove_entry()`, `select_character()`
  - `next_turn()`, `prev_turn()`
  - `set_stats()`, `modify_hp()`, `modify_elements()`
  - `add_status()`, `update_status()`, `remove_status()`
  - `add_favorite_dice()`, `roll_favorite_dice()`
  - `reroll_all_initiative()`

### music.py Analysis (840 lines)
- Mix of sync and async functions
- File I/O operations (musicsheet JSON)
- External dependency on yt-dlp
- Audio processing with pydub
- Complex state management
- Functions to test:
  - `log_message()`, `log_error()` (mock file I/O)
  - `load_musicsheet()`, `save_musicsheet()` (mock file I/O)
  - `sanitize_filename()` (pure function)
  - `find_downloaded_file()` (mock os.listdir)
  - `download_song()` (mock yt-dlp)
  - `play_next()` (complex, mock voice_client)

### UI Analysis
- Discord.py Views and Modals
- Heavy interaction-based
- Need to test callbacks
- Consider testing Modal.on_submit() separately from Discord

## User Decisions (confirmed)
- **Database Testing**: Both approaches - Mocks for unit tests, test DB for integration
- **Discord Testing**: Manual mocks (custom fixtures for ctx, bot, interaction)
- **Implementation Priority**: Utils first - pure utils → DB-dependent utils → cogs → UI
- **Randomness Handling**: Mock random.randint for deterministic tests

## Scope Boundaries

### INCLUDE
- Unit tests for all utils/ modules
- Unit tests for cogs/ command logic
- Integration tests for DB operations
- Mocking infrastructure
- Coverage configuration

### EXCLUDE
- End-to-end tests with real Discord bot
- Performance/load tests
- UI screenshot tests
- Real database setup (use mocks)

## Refactoring Needs for Testability

1. **shared_state.py**: Consider adding reset function for tests
2. **music.py**: Extract pure functions, reduce global state
3. **db.py**: Add interface/protocol for easier mocking
4. **initiative.py**: Dependency injection for Database
