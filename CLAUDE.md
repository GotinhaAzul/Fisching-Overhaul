# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable, registers `fisching` console command)
python3 -m pip install -e .

# Run the game
python3 start_game.py
python3 start_game_dev.py   # dev mode (dev_mode=True)

# Run all tests
python3 -m pytest -q

# Run a single test file
python3 -m pytest tests/test_rods_characterization.py -q
```

Requires Python 3.10+. Dependencies: `rich`, `pynput`.

## Architecture

**Entry points:** `start_game.py` bootstraps the install and delegates to `utils/pesca.py:main()`. `start_game_dev.py` wraps it with `dev_mode=True`.

**Core game loop** lives in `utils/pesca.py` (~136 KB). It handles menus, fishing mechanics (key-sequence minigame), HUD rendering, and ties together all subsystems.

**Subsystems** in `utils/`:
- `save_system.py` — serializes/deserializes full game state
- `market.py` — rod/bait trading, market orders
- `missions.py` — quest objectives, progression unlocks
- `crafting.py` — rod crafting recipes
- `bestiary.py` — fish tracking and completion rewards
- `hunts.py` — boss-style special encounters
- `events.py` — temporary fishing events
- `mutations.py` — per-fish stat modifiers
- `modern_ui.py` — Rich terminal UI components
- `perfect_catch.py` — key-sequence validation
- `levels.py` — XP/level calculation
- `pesca_boot.py` — game init (loads all JSON content)

**All game content is data-driven JSON** in domain folders. The loaders auto-discover files at startup — adding content never requires Python changes:

| Folder | What to add |
|--------|-------------|
| `pools/<name>/pool.json` + `pools/<name>/fish/*.json` | New fishing pool |
| `rods/<name>.json` | New rod |
| `mutations/<name>.json` | New mutation |
| `missions/<id>/mission.json` | New quest |
| `crafting/<id>/<id>.json` | New rod recipe |
| `events/<id>/event.json` | New temporary event |
| `hunts/<id>/` | New boss hunt |

Rod JSON keys: `name`, `luck`, `kg_max`, `control`, `price`, `unlocked_default`, `slash_chance`, `slam_chance`, `recover_chance`, `dupe_chance`.

Fish JSON keys: `name`, `rarity`, `kg_min`, `kg_max`, `base_value`, `sequence_len`, `reaction_time_s`.

Mission `requirements` types: `catch_fish`, `sell_fish`, `earn_money`, `level`, etc. `rewards` types: `money`, `xp`, `fish`, `unlock_rods`, `unlock_pools`, `unlock_missions`.

## Tests

Tests are **characterization tests** (verify existing behavior). They use internal test helpers like `_DummyFish`, `_ChoiceFeeder`, `_InputFeeder`. When adding content or modifying a module, extend the test file for that domain (e.g., rod changes → `test_rods_characterization.py`).

## Commits

Use imperative, scoped subjects: `market: fix pool order expiration restore`. Keep commits to one behavior/data change. Avoid generic messages like "Updated".