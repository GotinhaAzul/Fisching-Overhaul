---
tags:
 - project/fisching-overhaul
 - type/documentation
---

# Game Data Protection System

## Problem

All game data (save files, content JSON) is stored as plain-text JSON. Players can:
- Edit `savegame.json` to give themselves unlimited money, items, XP, unlocked content
- Read content files to spoil fish stats, rod abilities, mission rewards, boss mechanics
- Modify rod/fish JSON to alter game balance (e.g., make a rod overpowered)

## Goals

1. Prevent casual players from reading or tampering with game data
2. Detect save file tampering and reset to a fresh game
3. Bundle the game as a standalone `.exe` (no Python install required)
4. Keep the development workflow unchanged (plain JSON, `start_game_dev.py`)

## Design

### 1. Save File Encryption

**Library:** `cryptography.fernet` (AES-128-CBC + HMAC-SHA256)

**How it works:**
- On save: serialize game state to JSON string -> encrypt with Fernet -> write binary `.sav` file
- On load: read `.sav` file -> decrypt with Fernet -> deserialize JSON -> restore state
- Fernet includes built-in HMAC integrity verification — any byte changed in the file causes decryption to fail

**Tamper detection:**
- If decryption fails (tampered or corrupted file), delete the save and show a warning message (e.g., "Save file corrupted. Starting new game.")
- Player loses all progress — this is the deterrent

**Key derivation (save key):**
- Uses `PBKDF2HMAC` with SHA-256, 480,000 iterations, 32-byte output
- Input: a hardcoded secret string baked into the source
- Salt: generated randomly on first run and stored in a small unencrypted file (`fisching.salt`) alongside the save. This avoids fragility of hostname/username-based approaches — if the salt file is deleted, the save is simply unrecoverable (same as tamper)
- The derived key is base64-encoded for Fernet compatibility
- Save files are not transferable between installs (different salt), preventing save-sharing

**Format versioning:**
- The encrypted `.sav` file is prefixed with a 1-byte version number (currently `0x01`) before the Fernet token
- This allows future changes to encryption scheme without silently corrupting old saves

**File change:**
- `savegame.json` becomes `savegame.sav` (binary, not human-readable)
- Dev mode (`start_game_dev.py`) continues using plain `savegame.json` for easy debugging

**Migration from plain JSON:**
- On first launch after the update, if `savegame.json` exists but `savegame.sav` does not, the game reads the old JSON save, encrypts it, writes `savegame.sav`, and deletes `savegame.json`
- This is a one-time automatic migration so players don't lose progress on upgrade

### 2. Content File Bundling

**Two separate encryption keys:**
- **Save key:** per-install, derived from random salt (see Section 1). Used only for save files.
- **Content key:** fixed, hardcoded in source. Used to encrypt `content.dat` at build time. Must be the same across all machines since `content.dat` is distributed inside the `.exe`.

**Build-time encryption:**
- A `build.py` script walks all content directories: `pools/`, `rods/`, `fish/`, `mutations/`, `missions/`, `events/`, `hunts/`, `baits/`, `crafting/`, `weather/`, and root-level config files (e.g., `shiny_config`)
- Reads every JSON file and packs them into a single dict keyed by relative path from the project root (e.g., `rods/serenidade.json`, `pools/devcoffe/fish/devpass.json`)
- Serializes to JSON, encrypts with Fernet (content key), writes to `content.dat`

**Runtime loading:**
- Release mode: `content.dat` is embedded inside the `.exe` via PyInstaller `--add-data`. At runtime, the game reads it from `sys._MEIPASS` (PyInstaller's temp extraction dir). No encrypted files are visible on disk.
- Dev mode: game loads plain JSON files from disk as it does today
- The `dev_mode` flag (already exists) controls which path is used

**Loader changes:**
- All loader functions need modification to accept an optional pre-loaded content dict:
  - `pesca.py`: `load_pools()`, `load_fish_profiles_from_dir()`, `load_events()`, `load_hunts()`
  - `rods.py`: `load_rods()`
  - `missions.py`: `load_missions()`
  - `crafting.py`: `load_crafting_definitions()`
  - `mutations.py`: mutation loader
  - `weather.py`: weather loader
  - `baits/` loader: `load_bait_crates()`, `build_bait_lookup()`
- When pre-loaded dict is provided (release mode), loaders filter keys by their expected prefix (e.g., `load_rods` reads keys matching `rods/*.json`) instead of globbing the filesystem
- When not provided (dev mode), loaders read from disk as today
- **Note:** `load_pools()` internally calls `load_fish_profiles_from_dir()` for each pool subdirectory. In release mode, `load_pools()` will filter content keys matching `pools/<name>/fish/*.json` and pass those entries to the fish loader, replicating the directory-walk behavior without filesystem access.

### 3. PyInstaller Bundling

**Entry point:** A new `fisching_main.py` that calls `main(dev_mode=False)` directly, skipping the pip bootstrap logic in `start_game.py`. Detects frozen environment via `getattr(sys, 'frozen', False)`.

**What gets bundled:**
- All Python source files
- The encrypted `content.dat` blob (via `--add-data`)
- Dependencies (`rich`, `pynput`, `cryptography`)

**What is NOT bundled:**
- Plain JSON content files
- `savegame.sav` (created at runtime in the `.exe`'s directory)
- Dev-only files (`start_game_dev.py`, `tests/`)

**Output:** Single `fisching.exe` file

**Spec file:** `fisching.spec` is hand-authored and checked into the repo. `build.py` references it when invoking PyInstaller.

### 4. Build Script (`build.py`)

Steps:
1. Read all content JSON files from disk
2. Pack into a single dict, keyed by relative path from project root (e.g., `rods/serenidade.json`)
3. Encrypt with Fernet (content key) and write `content.dat` to a temp/build directory
4. Run PyInstaller with `fisching.spec` to produce `fisching.exe`
5. Output goes to `dist/fisching.exe`

Usage:
```bash
python build.py
```

### 5. Dev Workflow (Unchanged)

| Action | Before | After |
|--------|--------|-------|
| Edit content | Edit JSON files directly | Same |
| Run game (dev) | `python start_game_dev.py` | Same (plain JSON, plain save) |
| Run game (release) | `python start_game.py` | `fisching.exe` (encrypted content + save) |
| Push code | `git commit + push` | Same |
| Distribute | Players clone repo | Players download `.exe` from GitHub Releases |

> **Note:** The build step (`python build.py`) can be automated with a GitHub Action in the future — push a version tag, CI builds the `.exe`, and attaches it to a GitHub Release automatically. This is optional and can be added later.

### 6. New Dependencies

- `cryptography` — for Fernet encryption (add to `setup.py` / `pyproject.toml`)
- `pyinstaller` — dev/build dependency only (not shipped)

### 7. File Structure Changes

```
Fisching-Overhaul/
  build.py              # NEW - build script
  fisching.spec         # NEW - PyInstaller config (checked in)
  fisching_main.py      # NEW - release entry point (skips pip bootstrap)
  utils/
    save_system.py      # MODIFIED - add encryption/decryption for saves
    pesca_boot.py       # MODIFIED - support loading from encrypted blob
    pesca.py            # MODIFIED - pass pre-loaded content to loaders
    rods.py             # MODIFIED - accept optional pre-loaded dict
    missions.py         # MODIFIED - accept optional pre-loaded dict
    crafting.py         # MODIFIED - accept optional pre-loaded dict
    mutations.py        # MODIFIED - accept optional pre-loaded dict
    weather.py          # MODIFIED - accept optional pre-loaded dict
    crypto.py           # NEW - shared encryption/decryption helpers, key derivation
  dist/                 # gitignored
    fisching.exe        # build output
```

## Security Notes

- This protects against **casual tampering**. A determined reverse-engineer could decompile the PyInstaller bundle (tools like `pyinstxtractor` exist) and extract the keys from the Python bytecode. This is an inherent limitation of client-side games.
- The goal is to make it impractical for the average player, not impossible for a skilled attacker.
- Save files tied to per-install random salt prevent simple file-sharing of cheated saves.
- Two separate keys are used: a per-install derived key for saves, and a fixed key for content. This separation ensures `content.dat` works on all machines while saves remain install-specific.

