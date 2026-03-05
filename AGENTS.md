# Repository Guidelines

## Project Structure & Module Organization
Core gameplay entrypoints are `start_game.py` (normal mode) and `start_game_dev.py` (dev mode). Runtime logic lives in `utils/` (market, crafting, inventory, save system, UI helpers). Content is data-driven and split by domain folders:
- `pools/`, `rods/`, `baits/`, `mutations/`, `missions/`, `events/`, `hunts/`, `crafting/`, `cosmetics_catalog/`, `bestiary_rewards/`
- Tests are under `tests/` and follow characterization style.
Keep generated artifacts out of commits (`__pycache__/`, `*.egg-info/`).

## Build, Test, and Development Commands
Use Python 3.10+ (`pyproject.toml`).

```bash
python3 -m pip install -e .
python3 start_game.py
python3 start_game_dev.py
python3 -m pytest -q
```

- `install -e .`: editable install with console entrypoint `fisching`.
- `start_game.py`: run the game without installing command entrypoints.
- `start_game_dev.py`: run with `dev_mode=True`.
- `pytest`: run all tests in `tests/` (`test_*.py`).

## Coding Style & Naming Conventions
Follow existing Python style:
- 4-space indentation, type hints, and `from __future__ import annotations` where already used.
- `snake_case` for functions/variables/files; `PascalCase` for dataclasses/classes.
- Keep modules focused by feature (for example, market rules in `utils/market.py`).
For JSON content, use UTF-8 and consistent key names with existing schema in each folder.

## Testing Guidelines
Framework: `pytest` (configured in `pyproject.toml`).
- Place tests in `tests/` and name files `test_*.py`.
- Prefer deterministic characterization tests for gameplay and data-loading behavior.
- When adding content or rules, add/extend tests near the affected domain (example: rod parsing in `test_rods_characterization.py`).

## Commit & Pull Request Guidelines
Current history uses generic subjects like `Updated`; improve this going forward.
- Commit format: imperative, specific subject (example: `market: fix pool order expiration restore`).
- Keep commits scoped to one behavior/data change.
- PRs should include: concise summary, affected folders/modules, test evidence (`python3 -m pytest -q`), and screenshots/terminal snippets for UI-flow changes when relevant.
