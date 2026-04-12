---
tags:
 - project/fisching-overhaul
 - type/documentation
---

# Game Data Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encrypt save files and content data, bundle the game as a standalone `.exe` so players cannot read or tamper with game data.

**Architecture:** A new `utils/crypto.py` module provides key derivation and encrypt/decrypt helpers. `save_system.py` uses a per-install key (random salt) for saves. A `build.py` script packs all content JSON into an encrypted blob loaded at runtime in release mode. PyInstaller bundles everything into a single `.exe`.

**Tech Stack:** Python 3.10+, `cryptography` (Fernet/PBKDF2), `pyinstaller`

**Spec:** `docs/superpowers/specs/2026-03-21-data-protection-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `utils/crypto.py` | Key derivation, encrypt/decrypt helpers, content blob load |
| Create | `tests/test_crypto.py` | Tests for crypto module |
| Create | `tests/test_save_encryption.py` | Tests for encrypted save round-trip and tamper detection |
| Create | `tests/test_content_bundle.py` | Tests for content packing/unpacking |
| Modify | `utils/save_system.py:60-144` | Add encrypted save/load alongside existing plain-text |
| Modify | `utils/pesca.py:3386-3451` | Pass pre-loaded content dict to loaders in release mode |
| Modify | `utils/rods.py:102` | Accept optional content dict |
| Modify | `utils/missions.py:272` | Accept optional content dict |
| Modify | `utils/crafting.py:76` | Accept optional content dict |
| Modify | `utils/mutations.py:113` | Accept optional content dict |
| Modify | `utils/weather.py:50` | Accept optional content dict |
| Modify | `utils/baits.py:62` | Accept optional content dict |
| Modify | `utils/bestiary_rewards.py:43` | Accept optional content dict |
| Modify | `utils/shiny.py:41` | Accept optional content dict |
| Modify | `utils/pesca.py:422-698` | Accept optional content dict for pool/fish/event/hunt loaders |
| Modify | `utils/pesca_autosave.py:26-78` | Forward `dev_mode`/`salt_path` to `save_game()` |
| Modify | `pyproject.toml` | Add `cryptography` dependency |
| Create | `build.py` | Build script: pack content → encrypt → PyInstaller |
| Create | `fisching_main.py` | Release entry point (no pip bootstrap) |
| Create | `fisching.spec` | PyInstaller configuration |

---

### Task 1: Add `cryptography` dependency

**Files:**
- Modify: `pyproject.toml:11-14`

- [ ] **Step 1: Add cryptography to dependencies**

In `pyproject.toml`, add `"cryptography"` to the dependencies list:

```toml
dependencies = [
    "rich",
    "pynput",
    "cryptography",
]
```

- [ ] **Step 2: Add pyinstaller as optional build dependency**

Add a new section after `[tool.pytest.ini_options]`:

```toml
[project.optional-dependencies]
build = ["pyinstaller"]
```

- [ ] **Step 3: Install and verify**

Run: `python -m pip install -e ".[build]"`
Expected: installs successfully, `cryptography` and `pyinstaller` available

- [ ] **Step 4: Run existing tests to confirm nothing breaks**

Run: `python -m pytest -q`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add cryptography and pyinstaller build extra"
```

---

### Task 2: Create `utils/crypto.py` — key derivation and encrypt/decrypt

**Files:**
- Create: `utils/crypto.py`
- Create: `tests/test_crypto.py`

- [ ] **Step 1: Write failing tests for key derivation**

Create `tests/test_crypto.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from utils.crypto import derive_save_key, encrypt_blob, decrypt_blob, CONTENT_KEY


def test_derive_save_key_deterministic(tmp_path: Path) -> None:
    """Same salt file produces same key."""
    salt_path = tmp_path / "fisching.salt"
    key1 = derive_save_key(salt_path)
    key2 = derive_save_key(salt_path)
    assert key1 == key2


def test_derive_save_key_creates_salt_file(tmp_path: Path) -> None:
    """Salt file is created on first call."""
    salt_path = tmp_path / "fisching.salt"
    assert not salt_path.exists()
    derive_save_key(salt_path)
    assert salt_path.exists()
    assert len(salt_path.read_bytes()) == 16


def test_different_salt_different_key(tmp_path: Path) -> None:
    """Different salt files produce different keys."""
    key1 = derive_save_key(tmp_path / "salt1")
    key2 = derive_save_key(tmp_path / "salt2")
    assert key1 != key2


def test_encrypt_decrypt_roundtrip() -> None:
    """Encrypt then decrypt returns original data."""
    data = b'{"balance": 100, "level": 5}'
    key = CONTENT_KEY
    encrypted = encrypt_blob(key, data)
    assert encrypted != data
    decrypted = decrypt_blob(key, encrypted)
    assert decrypted == data


def test_decrypt_tampered_blob_raises() -> None:
    """Tampered ciphertext raises an exception."""
    import pytest
    data = b"hello world"
    encrypted = encrypt_blob(CONTENT_KEY, data)
    tampered = encrypted[:-1] + bytes([(encrypted[-1] + 1) % 256])
    with pytest.raises(Exception):
        decrypt_blob(CONTENT_KEY, tampered)


def test_versioned_save_blob_roundtrip(tmp_path: Path) -> None:
    """Versioned save blob prefixes version byte 0x01."""
    from utils.crypto import encrypt_save_blob, decrypt_save_blob
    salt_path = tmp_path / "fisching.salt"
    key = derive_save_key(salt_path)
    data = b'{"test": true}'
    blob = encrypt_save_blob(key, data)
    assert blob[0:1] == b'\x01'
    result = decrypt_save_blob(key, blob)
    assert result == data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_crypto.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `utils/crypto.py`**

Create `utils/crypto.py`:

```python
"""Encryption helpers for save files and content bundles."""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

# ── Constants ──────────────────────────────────────────────────────────
_SAVE_SECRET = b"fisching-overhaul-2026-salt-secret"
_SAVE_FORMAT_VERSION = b'\x01'
_PBKDF2_ITERATIONS = 480_000

# Fixed key for content blob (same across all machines).
# Generated once: Fernet.generate_key()
CONTENT_KEY = b'GTEHnUcXr0QSiyelDGw63ldnxT4CuPq1OT2OCiSdEo0='


# ── Key derivation ─────────────────────────────────────────────────────
def derive_save_key(salt_path: Path) -> bytes:
    """Derive a Fernet key from a per-install random salt.

    Creates the salt file on first call (16 random bytes).
    Returns a 44-byte URL-safe base64 key suitable for Fernet.
    """
    if salt_path.exists():
        salt = salt_path.read_bytes()
    else:
        salt = os.urandom(16)
        salt_path.write_bytes(salt)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    raw_key = kdf.derive(_SAVE_SECRET)
    return base64.urlsafe_b64encode(raw_key)


# ── Low-level encrypt / decrypt ────────────────────────────────────────
def encrypt_blob(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt plaintext with Fernet. Returns ciphertext bytes."""
    return Fernet(key).encrypt(plaintext)


def decrypt_blob(key: bytes, ciphertext: bytes) -> bytes:
    """Decrypt ciphertext with Fernet. Raises on tamper/bad key."""
    return Fernet(key).decrypt(ciphertext)


# ── Save-specific wrappers (with version prefix) ──────────────────────
def encrypt_save_blob(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt save data with a version-byte prefix."""
    return _SAVE_FORMAT_VERSION + encrypt_blob(key, plaintext)


def decrypt_save_blob(key: bytes, data: bytes) -> bytes:
    """Decrypt a versioned save blob. Raises on tamper/bad key."""
    if len(data) < 2 or data[0:1] != _SAVE_FORMAT_VERSION:
        raise InvalidToken
    return decrypt_blob(key, data[1:])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_crypto.py -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/crypto.py tests/test_crypto.py
git commit -m "crypto: add key derivation and encrypt/decrypt helpers"
```

---

### Task 3: Encrypted save in `save_system.py`

**Files:**
- Create: `tests/test_save_encryption.py`
- Modify: `utils/save_system.py:16-17,60-144`

- [ ] **Step 1: Write failing tests for encrypted save**

Create `tests/test_save_encryption.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from utils.inventory import InventoryEntry
from utils.rods import Rod
from utils.save_system import (
    SAVE_VERSION,
    save_game,
    load_game,
)


def _rod(name: str) -> Rod:
    return Rod(
        name=name, luck=0.0, kg_max=100.0, control=0.0,
        description="test", price=0.0, unlocked_default=True,
    )


def _pool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _minimal_save_kwargs(tmp_path: Path) -> dict:
    rod = _rod("TestRod")
    return dict(
        save_path=tmp_path / "savegame.sav",
        balance=500.0,
        inventory=[],
        owned_rods=[rod],
        equipped_rod=rod,
        selected_pool=_pool("TestPool"),
        unlocked_pools=["TestPool"],
        unlocked_rods=["TestRod"],
        level=3,
        xp=150,
        discovered_fish=["Carpa"],
        mission_state={},
        mission_progress={},
    )


def test_encrypted_save_load_roundtrip(tmp_path: Path) -> None:
    """Encrypted save can be loaded back."""
    kwargs = _minimal_save_kwargs(tmp_path)
    salt_path = tmp_path / "fisching.salt"
    save_game(**kwargs, dev_mode=False, salt_path=salt_path)
    result = load_game(kwargs["save_path"], dev_mode=False, salt_path=salt_path)
    assert result is not None
    assert result["balance"] == 500.0
    assert result["level"] == 3


def test_encrypted_save_is_not_readable_json(tmp_path: Path) -> None:
    """Encrypted save file is not valid JSON."""
    kwargs = _minimal_save_kwargs(tmp_path)
    salt_path = tmp_path / "fisching.salt"
    save_game(**kwargs, dev_mode=False, salt_path=salt_path)
    raw = kwargs["save_path"].read_bytes()
    try:
        json.loads(raw)
        assert False, "Should not be valid JSON"
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass


def test_tampered_save_returns_none(tmp_path: Path) -> None:
    """Tampered encrypted save returns None (triggers reset)."""
    kwargs = _minimal_save_kwargs(tmp_path)
    salt_path = tmp_path / "fisching.salt"
    save_game(**kwargs, dev_mode=False, salt_path=salt_path)
    # Tamper with the file
    data = bytearray(kwargs["save_path"].read_bytes())
    data[-1] = (data[-1] + 1) % 256
    kwargs["save_path"].write_bytes(bytes(data))
    result = load_game(kwargs["save_path"], dev_mode=False, salt_path=salt_path)
    assert result is None


def test_dev_mode_save_is_plain_json(tmp_path: Path) -> None:
    """Dev mode still saves plain JSON."""
    kwargs = _minimal_save_kwargs(tmp_path)
    kwargs["save_path"] = tmp_path / "savegame.json"
    save_game(**kwargs, dev_mode=True)
    raw = kwargs["save_path"].read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["balance"] == 500.0


def test_migration_from_plain_json(tmp_path: Path) -> None:
    """Old plain savegame.json is migrated to encrypted .sav on load."""
    from utils.crypto import derive_save_key
    # Write a plain JSON save (old format)
    old_path = tmp_path / "savegame.json"
    old_data = {"version": 11, "balance": 999.0, "level": 10}
    old_path.write_text(json.dumps(old_data), encoding="utf-8")

    sav_path = tmp_path / "savegame.sav"
    salt_path = tmp_path / "fisching.salt"
    result = load_game(sav_path, dev_mode=False, salt_path=salt_path, legacy_json_path=old_path)
    assert result is not None
    assert result["balance"] == 999.0
    # Old file should be deleted after migration
    assert not old_path.exists()
    # New .sav should exist
    assert sav_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_save_encryption.py -v`
Expected: FAIL (signature mismatch — `dev_mode` and `salt_path` params don't exist yet)

- [ ] **Step 3: Modify `save_system.py` — update constants and imports**

At the top of `utils/save_system.py`, add the crypto import and update the save file name:

```python
# Add after existing imports (line 9):
from utils.crypto import (
    derive_save_key,
    encrypt_save_blob,
    decrypt_save_blob,
)

# Update line 17:
SAVE_FILE_NAME = "savegame.sav"
ENCRYPTED_SAVE_FILE_NAME = "savegame.sav"
LEGACY_SAVE_FILE_NAME = "savegame.json"
```

- [ ] **Step 4: Modify `save_game()` — add `dev_mode` and `salt_path` parameters**

Change the `save_game` function signature (line 60) to add `dev_mode` and `salt_path` keyword args at the end (before the closing `)`) and update the write logic:

```python
    # Add these two params after discovered_shiny_fish:
    dev_mode: bool = True,
    salt_path: Optional[Path] = None,
```

Replace the file write block (lines 128-132) with:

```python
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    if dev_mode:
        save_path.write_text(
            json_bytes.decode("utf-8"),
            encoding="utf-8",
        )
    else:
        if salt_path is None:
            salt_path = save_path.parent / "fisching.salt"
        key = derive_save_key(salt_path)
        save_path.write_bytes(encrypt_save_blob(key, json_bytes))
```

- [ ] **Step 5: Modify `load_game()` — add encrypted load + migration**

Replace `load_game` (lines 135-144) with:

```python
def load_game(
    save_path: Path,
    dev_mode: bool = True,
    salt_path: Optional[Path] = None,
    legacy_json_path: Optional[Path] = None,
) -> Optional[Dict[str, object]]:
    if dev_mode:
        if not save_path.exists():
            return None
        try:
            raw = json.loads(save_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        return raw

    # Release mode: encrypted .sav
    if salt_path is None:
        salt_path = save_path.parent / "fisching.salt"

    # Migration: convert old plain JSON to encrypted .sav
    if not save_path.exists() and legacy_json_path and legacy_json_path.exists():
        try:
            raw = json.loads(legacy_json_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                key = derive_save_key(salt_path)
                json_bytes = json.dumps(raw, indent=2, ensure_ascii=False).encode("utf-8")
                save_path.write_bytes(encrypt_save_blob(key, json_bytes))
                legacy_json_path.unlink()
                return raw
        except (OSError, json.JSONDecodeError):
            pass
        return None

    if not save_path.exists():
        return None
    try:
        key = derive_save_key(salt_path)
        decrypted = decrypt_save_blob(key, save_path.read_bytes())
        raw = json.loads(decrypted)
    except Exception:
        # Tampered or corrupted — delete and return None
        try:
            save_path.unlink()
        except OSError:
            pass
        return None
    if not isinstance(raw, dict):
        return None
    return raw
```

- [ ] **Step 6: Run new tests**

Run: `python -m pytest tests/test_save_encryption.py -v`
Expected: all 5 tests PASS

- [ ] **Step 7: Run ALL tests to check for regressions**

Run: `python -m pytest -q`
Expected: all tests pass. Existing tests use `dev_mode=True` (the default), so they should be unaffected.

- [ ] **Step 8: Commit**

```bash
git add utils/save_system.py tests/test_save_encryption.py
git commit -m "save: add Fernet encryption with tamper detection and migration"
```

---

### Task 4: Content packing — `utils/crypto.py` extensions

**Files:**
- Modify: `utils/crypto.py`
- Create: `tests/test_content_bundle.py`

- [ ] **Step 1: Write failing tests for content packing**

Create `tests/test_content_bundle.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from utils.crypto import pack_content, unpack_content, CONTENT_KEY


def test_pack_unpack_roundtrip(tmp_path: Path) -> None:
    """Pack content dirs into encrypted blob, then unpack."""
    # Create fake content
    rods_dir = tmp_path / "rods"
    rods_dir.mkdir()
    (rods_dir / "bambu.json").write_text('{"name": "Bambu"}', encoding="utf-8")

    pools_dir = tmp_path / "pools" / "lago"
    (pools_dir / "fish").mkdir(parents=True)
    (pools_dir / "pool.json").write_text('{"name": "Lago"}', encoding="utf-8")
    (pools_dir / "fish" / "carpa.json").write_text('{"name": "Carpa"}', encoding="utf-8")

    blob = pack_content(tmp_path)
    content = unpack_content(blob)

    assert content["rods/bambu.json"] == {"name": "Bambu"}
    assert content["pools/lago/pool.json"] == {"name": "Lago"}
    assert content["pools/lago/fish/carpa.json"] == {"name": "Carpa"}


def test_unpack_tampered_blob_raises(tmp_path: Path) -> None:
    """Tampered content blob raises."""
    import pytest
    rods_dir = tmp_path / "rods"
    rods_dir.mkdir()
    (rods_dir / "test.json").write_text('{"x": 1}', encoding="utf-8")

    blob = pack_content(tmp_path)
    tampered = blob[:-1] + bytes([(blob[-1] + 1) % 256])
    with pytest.raises(Exception):
        unpack_content(tampered)


def test_pack_includes_config_dirs(tmp_path: Path) -> None:
    """Config and weather config are included."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "shiny.json").write_text('{"chance": 1.0}', encoding="utf-8")

    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "config.json").write_text('{"interval": 5}', encoding="utf-8")

    blob = pack_content(tmp_path)
    content = unpack_content(blob)

    assert content["config/shiny.json"] == {"chance": 1.0}
    assert content["weather/config.json"] == {"interval": 5}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_content_bundle.py -v`
Expected: FAIL (functions not found)

- [ ] **Step 3: Add `pack_content` and `unpack_content` to `utils/crypto.py`**

Append to `utils/crypto.py`:

```python
# ── Content bundle packing ─────────────────────────────────────────────
_CONTENT_DIRS = [
    "pools", "rods", "mutations", "missions", "events",
    "hunts", "baits", "crafting", "weather", "config",
    "bestiary_rewards",
]


def pack_content(project_root: Path) -> bytes:
    """Walk content directories, pack all JSON into an encrypted blob.

    Returns encrypted bytes. Keys are relative paths like 'rods/bambu.json'.
    """
    bundle: dict[str, object] = {}
    for dir_name in _CONTENT_DIRS:
        content_dir = project_root / dir_name
        if not content_dir.is_dir():
            continue
        for json_file in content_dir.rglob("*.json"):
            rel = json_file.relative_to(project_root).as_posix()
            bundle[rel] = json.loads(json_file.read_text(encoding="utf-8"))

    payload = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    return encrypt_blob(CONTENT_KEY, payload)


def unpack_content(blob: bytes) -> dict[str, object]:
    """Decrypt and parse a content blob. Returns dict keyed by relative path."""
    payload = decrypt_blob(CONTENT_KEY, blob)
    return json.loads(payload)
```

You'll need to add `import json` at the top of `utils/crypto.py` if not already present.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_content_bundle.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/crypto.py tests/test_content_bundle.py
git commit -m "crypto: add content packing and unpacking for release builds"
```

---

### Task 5: Refactor loaders to accept pre-loaded content dict

This is the largest task. Each loader needs an optional `content: dict | None = None` parameter. When provided, it reads from the dict instead of the filesystem.

**Files:**
- Modify: `utils/rods.py:102`
- Modify: `utils/missions.py:272`
- Modify: `utils/crafting.py:76`
- Modify: `utils/mutations.py:113`
- Modify: `utils/weather.py:50`
- Modify: `utils/baits.py:62`
- Modify: `utils/bestiary_rewards.py:43`
- Modify: `utils/shiny.py:41`
- Modify: `utils/pesca.py:422-698` (pool/fish/event/hunt loaders)

**Pattern:** Each loader follows the same refactor pattern. Here's the general approach — the loader gets a `content` param. If `content` is not `None`, it filters keys by prefix and loads from the dict. Otherwise, it reads from disk as before.

- [ ] **Step 1: Refactor `load_rods()` in `utils/rods.py`**

At `utils/rods.py:102`, change the signature and add content-dict path:

```python
def load_rods(base_dir: Path, *, content: dict | None = None) -> List[Rod]:
```

At the start of the function body, before the existing filesystem glob, add:

```python
    if content is not None:
        entries = [
            (key, data) for key, data in content.items()
            if key.startswith("rods/") and key.endswith(".json")
        ]
        rods = []
        for key, data in sorted(entries):
            # data is already a parsed dict — use same parsing logic
            # (reuse existing parsing code from the filesystem branch)
            ...
        return rods
```

The exact implementation will mirror the existing parsing logic but read `data` (a dict) instead of `json.load(handle)`. Keep the existing filesystem path untouched for `content=None`.

- [ ] **Step 2: Refactor `load_mutations()` in `utils/mutations.py`**

Same pattern at line 113. Add `content: dict | None = None` parameter. Filter keys with prefix `mutations/`.

- [ ] **Step 3: Refactor `load_missions()` in `utils/missions.py`**

Same pattern at line 272. Filter keys with prefix `missions/` and ending `mission.json`.

- [ ] **Step 4: Refactor `load_crafting_definitions()` in `utils/crafting.py`**

Same pattern at line 76. Filter keys with prefix `crafting/`.

- [ ] **Step 5: Refactor `load_weather()` in `utils/weather.py`**

Same pattern at line 50. Filter keys with prefix `weather/`. Note: this loader also reads `weather/config.json` — ensure that key is also fetched from the dict.

- [ ] **Step 6: Refactor `load_bait_crates()` in `utils/baits.py`**

Same pattern at line 62. Filter keys with prefix `baits/`.

- [ ] **Step 7: Refactor `load_bestiary_rewards()` in `utils/bestiary_rewards.py`**

Same pattern at line 43. Filter keys with prefix `bestiary_rewards/`.

- [ ] **Step 8: Refactor `load_shiny_config()` in `utils/shiny.py`**

Same pattern at line 41. Look for key `config/shiny.json` in the dict.

- [ ] **Step 9: Refactor pool/fish/event/hunt loaders in `utils/pesca.py`**

Modify these functions:
- `load_fish_profiles_from_dir()` (line 422): add `content: dict | None = None`. When provided, filter keys matching the expected fish directory prefix.
- `load_pools()` (line 621): add `content: dict | None = None`. When provided, find pool keys like `pools/<name>/pool.json`, then pass the matching fish keys to `load_fish_profiles_from_dir`.
- `load_events()` (line 488): add `content: dict | None = None`. Filter keys with `events/`.
- `load_hunts()` (line 542): add `content: dict | None = None`. Filter keys with `hunts/`.

- [ ] **Step 10: Run ALL tests**

Run: `python -m pytest -q`
Expected: all tests pass. Since `content` defaults to `None`, all existing callers are unaffected.

- [ ] **Step 11: Commit**

```bash
git add utils/rods.py utils/missions.py utils/crafting.py utils/mutations.py utils/weather.py utils/baits.py utils/bestiary_rewards.py utils/shiny.py utils/pesca.py
git commit -m "loaders: accept optional content dict for release-mode loading"
```

---

### Task 6: Wire content loading in `main()` and autosave

**Files:**
- Modify: `utils/pesca.py:3386-3451`
- Modify: `utils/pesca_autosave.py:26-78`

- [ ] **Step 1: Add content loading at the top of `main()`**

After the `random.seed()` call (line 3391), add content loading logic:

```python
    project_root = Path(__file__).resolve().parent.parent
    content = None
    if not dev_mode:
        content_path = project_root / "content.dat"
        # When running as PyInstaller bundle, content.dat is in the temp dir
        if getattr(sys, 'frozen', False):
            content_path = Path(sys._MEIPASS) / "content.dat"
        if content_path.exists():
            from utils.crypto import unpack_content
            content = unpack_content(content_path.read_bytes())
```

- [ ] **Step 2: Pass `content` to every loader call**

Update each loader call (lines 3394-3434) to pass `content=content`:

```python
    pools = load_pools(base_dir, content=content)
    events = load_events(events_dir, content=content)
    hunts = load_hunts(hunts_dir, valid_pool_names=..., content=content)
    weather_defs, weather_config = load_weather(weather_base_dir, content=content)
    shiny_config = load_shiny_config(project_root, content=content)
    available_rods = load_rods(rods_dir, content=content)
    available_mutations = load_mutations(mutations_dir, content=content)
    bait_crates = load_bait_crates(baits_dir, content=content)
    missions = load_missions(missions_dir, content=content)
    bestiary_rewards = load_bestiary_rewards(bestiary_rewards_dir, content=content)
    crafting_definitions = load_crafting_definitions(crafting_dir, valid_rod_names=..., content=content)
```

- [ ] **Step 3: Wire encrypted save in `main()`**

Update the `load_game` call (line 3451) and any `save_game` calls to pass `dev_mode` and `salt_path`:

```python
    salt_path = project_root / "fisching.salt"
    save_path = get_default_save_path()
    legacy_json_path = save_path.parent / "savegame.json" if not dev_mode else None
    save_data = load_game(
        save_path, dev_mode=dev_mode, salt_path=salt_path,
        legacy_json_path=legacy_json_path,
    )
```

Also update `get_default_save_path()` to return `.sav` in release mode, or change the save path inline:

```python
    if not dev_mode:
        save_path = save_path.parent / "savegame.sav"
```

- [ ] **Step 3b: Update `pesca_autosave.py` to forward encryption params**

The actual `save_game()` call site is in `utils/pesca_autosave.py:53`, not in `pesca.py` directly. Modify `autosave_state()` (line 26) to accept and forward the new params:

Add to `autosave_state` signature (after `discovered_shiny_fish`):
```python
    dev_mode: bool = True,
    salt_path: Optional[Path] = None,
```

Add to the `save_game(...)` call inside `autosave_state` (after `discovered_shiny_fish=...`):
```python
        dev_mode=dev_mode,
        salt_path=salt_path,
```

Then update every `autosave_state(...)` call in `pesca.py` to pass `dev_mode=dev_mode, salt_path=salt_path`.

- [ ] **Step 4: Run ALL tests**

Run: `python -m pytest -q`
Expected: all pass (tests run with `dev_mode=True` default)

- [ ] **Step 5: Commit**

```bash
git add utils/pesca.py utils/pesca_autosave.py
git commit -m "pesca: wire encrypted content and save loading in main() and autosave"
```

---

### Task 7: Release entry point

**Files:**
- Create: `fisching_main.py`

- [ ] **Step 1: Create `fisching_main.py`**

```python
"""Release entry point for the bundled .exe build.

Skips pip bootstrapping (dependencies are bundled by PyInstaller).
"""
import sys

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    from utils.pesca import main as game_main
    game_main(dev_mode=False)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it runs**

Run: `python fisching_main.py`
Expected: game launches in release mode. If `content.dat` doesn't exist yet, it will fail to load content — that's expected at this stage. Verify it at least starts without import errors.

- [ ] **Step 3: Commit**

```bash
git add fisching_main.py
git commit -m "entry: add release entry point for PyInstaller builds"
```

---

### Task 8: Build script and PyInstaller config

**Files:**
- Create: `build.py`
- Create: `fisching.spec`
- Modify: `.gitignore` (add `dist/`, `build/`, `content.dat`, `*.spec` backup)

- [ ] **Step 1: Create `build.py`**

```python
"""Build script: encrypt content and bundle into a standalone .exe."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from utils.crypto import pack_content


def main() -> None:
    project_root = Path(__file__).resolve().parent
    build_dir = project_root / "build_tmp"
    build_dir.mkdir(exist_ok=True)

    # Step 1: Pack and encrypt content
    print("Packing content...")
    blob = pack_content(project_root)
    content_dat = build_dir / "content.dat"
    content_dat.write_bytes(blob)
    print(f"  content.dat: {len(blob):,} bytes")

    # Step 2: Run PyInstaller
    print("Running PyInstaller...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        str(project_root / "fisching.spec"),
        "--noconfirm",
    ])

    # Step 3: Copy content.dat into dist if not embedded by spec
    print("Done! Output: dist/fisching.exe")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `fisching.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / 'fisching_main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'build_tmp' / 'content.dat'), '.'),
    ],
    hiddenimports=['utils'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fisching',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
```

- [ ] **Step 3: Update `.gitignore`**

Add these lines:

```
dist/
build/
build_tmp/
*.exe
content.dat
fisching.salt
savegame.sav
```

- [ ] **Step 4: Test the build**

Run: `python build.py`
Expected: `content.dat` is created in `build_tmp/`, PyInstaller runs and produces `dist/fisching.exe`

- [ ] **Step 5: Test the `.exe`**

Run: `./dist/fisching.exe`
Expected: game launches, content loads from encrypted blob, save file is encrypted `.sav`

- [ ] **Step 6: Commit**

```bash
git add build.py fisching.spec .gitignore
git commit -m "build: add build script and PyInstaller config for release .exe"
```

---

### Task 9: End-to-end verification

- [ ] **Step 1: Clean slate test**

Delete any existing `savegame.json`, `savegame.sav`, `fisching.salt` files.

- [ ] **Step 2: Run dev mode and verify plain JSON still works**

Run: `python start_game_dev.py`
Expected: game creates `savegame.json` (readable plain JSON)

- [ ] **Step 3: Run release build**

Run: `python build.py`
Expected: `dist/fisching.exe` produced

- [ ] **Step 4: Run the `.exe` and play**

Run: `./dist/fisching.exe`
Expected: game works, creates `savegame.sav` (binary, not readable)

- [ ] **Step 5: Tamper test**

Open `savegame.sav` in a hex editor, change a byte, save. Re-run the `.exe`.
Expected: "Save file corrupted. Starting new game." message, save deleted, fresh start.

- [ ] **Step 6: Migration test**

Place a plain `savegame.json` next to the `.exe`. Run the `.exe`.
Expected: old save is migrated to `.sav`, `.json` is deleted, progress preserved.

- [ ] **Step 7: Run all tests one final time**

Run: `python -m pytest -q`
Expected: all pass

- [ ] **Step 8: Final commit if any fixes were needed**

```bash
git commit -m "data-protection: end-to-end verification complete"
```

