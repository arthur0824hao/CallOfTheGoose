# Unified TTRPG System Architecture (Tri-Force)

**Date:** 2026-01-16
**Goal:** Unify Google Sheets (Data), Discord Bot (Runtime), and Obsidian (Lore) into a cohesive system.

## 1. Core Philosophy: "Sheet as Database, Bot as Runtime"

Instead of building a complex database UI in Discord or Obsidian, we leverage the existing, powerful Google Sheet as the **Source of Truth**.

| Component | Role | Responsibility |
|-----------|------|----------------|
| **Google Sheet** | **Database (Source of Truth)** | Player editing, stats calculation, inventory management, complex logic (Cyberware SAN loss). |
| **Discord Bot** | **Runtime Engine** | Combat tracking, dice rolling, music, reading cached data from Sheet for speed. |
| **Obsidian** | **Lore & Reference** | World building, NPC database, Rulebook lookup. |

## 2. Data Flow Architecture

```mermaid
graph TD
    User[Player] -->|Edits| Sheet[Google Sheet (PC)]
    Sheet -->|Auto-Calc| BotView[Hidden 'BotData' Tab]
    BotView -->|CSV Export| Bot[Discord Bot]
    Bot -->|Cache| DB[(PostgreSQL/JSON)]
    Bot -->|Combat| Discord[Discord Channel]
    DM[Game Master] -->|Reference| Obsidian
    Obsidian -.->|Iframe| Sheet
```

## 3. Implementation Steps

### Phase 1: Google Sheet Preparation ( The "API" )
Do not let the bot read the complex "人物表" tab directly. It's fragile.
1.  **Create a new tab named `BotData`**.
2.  **Structure**: Key-Value pairs designed for machine reading.
    *   Col A: `Key` (e.g., `char_name`, `hp_current`, `hp_max`, `str`, `dex`, `sanity`, `cyberware_list`)
    *   Col B: `Value` (Formula linking to main sheet, e.g., `=人物表!C2`)
3.  **Publish**: File > Share > Publish to Web > Select `BotData` > Format: **CSV**.
4.  **Result**: You get a stable URL that returns clean data.

### Phase 2: Discord Bot Upgrade (`sheet_sync`)
Add the ability to pull this CSV and update the local DB.

1.  **New Utility**: `utils/sheet_client.py`
    *   Function `fetch_character_data(csv_url)`: Downloads and parses the CSV into a Python dict.
2.  **New Command**: `!sync <url>` (or register url once via `!char link <url>`)
    *   Action: Fetches data, updates `characters` table in PostgreSQL.
3.  **Update Initiative**:
    *   When `!init join` is called, check if character has synced data. If yes, use those stats.

### Phase 3: Obsidian Integration
1.  **Player Notes**: In `2-People/PC/CharacterName.md`:
    *   Add Frontmatter: `sheet_url: "https://..."`
    *   Add Meta Bind Button: `Button("Sync to Bot")` (Can copy the command to clipboard).
    *   Embed Sheet: `<iframe src="..."></iframe>` for live viewing.

## 4. Technical Specifications (Bot)

### Schema Mapping (Proposed)
`BotData` Tab in Sheet should map to `characters` table JSONB:

```json
{
  "name": "Goose",
  "stats": {
    "str": 12,
    "dex": 14,
    "con": 16,
    "int": 10,
    "wis": 8,
    "cha": 12
  },
  "attributes": {
    "hp": 45,
    "max_hp": 45,
    "ac": 15,
    "initiative_bonus": 2
  },
  "cyberware": [
    {"slot": "Eye", "name": "Kiroshi Optics", "effect": "Darkvision"}
  ]
}
```

### New Dependencies
*   `aiohttp` (Existing) - To fetch CSV.
*   `csv` (Standard Lib) - To parse response.

## 5. Migration Strategy
1.  **Keep existing JSON** (`data/characters.json`) as backup.
2.  **Enable DB**: Ensure `utils/db.py` is working with a local Postgres or SQLite.
3.  **Pilot**: Test with one character sheet first.
