# Design Spec: `shiny_override` Rod Stat

**Date:** 2026-03-21
**Status:** Approved

---

## Overview

Add a new optional rod stat `shiny_override` that, when present, replaces the global shiny chance during fishing. Appraisal shiny chances are unaffected.

---

## Motivation

The global shiny config (`config/shiny.json`) sets a single `catch_chance_percent` that applies to all catches. Some rods should be able to guarantee a different shiny rate — higher (lucky/magical rods) or zero (cursed/mundane rods) — independently of the global setting.

---

## Scope

- **In scope:** fishing catches (main catch, frenzy catch).
- **Dupe catches:** copy `is_shiny` directly from the parent catch variable (the `is_shiny` / `frenzy_is_shiny` variable at the dupe site already reflects the override), so no additional change is required in the dupe block.
- **Out of scope:** appraisal shiny rolls (`roll_shiny_on_appraise`), which remain driven solely by `ShinyConfig.appraise_chance_percent`.

---

## Data Format

Rod JSON gains an optional key `shiny_override`. When absent, shiny rolls use the global config as before.

```json
{ "shiny_override": 5 }
```

Accepted value formats (parsed via `_normalize_probability` in `utils/rods.py`):

| JSON value | Parsed result | Effective chance | Notes |
|------------|--------------|-----------------|-------|
| `5`        | `0.05`       | 5%              | `_parse_number` returns 5.0; outer `> 1.0` branch divides by 100 |
| `"5%"`     | `0.05`       | 5%              | `_parse_number` strips `%`, divides inside the parser |
| `0.05`     | `0.05`       | 5%              | Already a fraction; `≤ 1.0`, kept as-is |
| `"1%"`     | `0.01`       | 1%              | Correct way to write 1% |
| `0.01`     | `0.01`       | 1%              | Also correct |
| **`1`**    | **`1.0`**    | **100%**        | `1 ≤ 1.0` so NOT divided — use `"1%"` or `0.01` for 1% |
| `0`        | `0.0`        | 0% (never)      | |
| `100`      | `1.0`        | 100% (always)   | `100 > 1.0`, divided by 100 |
| `"100%"`   | `1.0`        | 100% (always)   | |
| *(absent)* | —            | Global config   | |

> **Warning for rod authors:** `"shiny_override": 1` means **always shiny (100%)**, not 1%. Write `"shiny_override": "1%"` or `"shiny_override": 0.01` for a 1% chance. This is the same convention used by all other rod probability stats.

The stored value is a fraction in `[0.0, 1.0]`.

---

## Persistence

`Rod` objects are never serialized to the save file — only the equipped rod's name is stored. `shiny_override` is re-read from its JSON source on every game load. No save migration is needed.

---

## Implementation

### `utils/rods.py`

1. Add `Optional` to the existing typing import:
   ```python
   from typing import List, Optional
   ```
2. Add field to `Rod` dataclass (after the last existing field):
   ```python
   shiny_override: Optional[float] = None
   ```
3. In `load_rods`, parse the key before constructing the `Rod`:
   ```python
   raw_shiny_override = data.get("shiny_override")
   shiny_override = (
       _normalize_probability(raw_shiny_override)
       if raw_shiny_override is not None
       else None
   )
   ```
4. Add `shiny_override=shiny_override` to the `Rod(...)` constructor call.

> **Note:** Do not add `shiny_override` to `UPGRADEABLE_STATS` in `rod_upgrades.py`. That list drives linear float scaling; the `None` sentinel would need special-casing and upgrades to shiny chance are out of scope.

### `utils/pesca.py`

`effective_rod` is established at line ~2875 (`effective_rod = get_effective_rod(...)`) at the top of the `while True` loop in `run_fishing_round`. Both roll sites are nested within that same loop iteration, so `effective_rod.shiny_override` is always in scope.

The roll uses `random.random() <= fraction`, matching the convention of all other rod ability checks in `pesca.py` (slash, slam, recover, dupe, frenzy, greed, pierce). In practice `random.random()` returns `[0.0, 1.0)`, so `<= 0.0` is effectively never True and `<= 1.0` is always True.

**Main catch (~line 3101)** — replace:
```python
is_shiny = roll_shiny_on_catch(shiny_config) if shiny_config else False
```
with:
```python
if effective_rod.shiny_override is not None:
    is_shiny = random.random() <= effective_rod.shiny_override
else:
    is_shiny = roll_shiny_on_catch(shiny_config) if shiny_config else False
```

**Frenzy catch (~line 3292)** — replace:
```python
frenzy_is_shiny = roll_shiny_on_catch(shiny_config) if shiny_config else False
```
with:
```python
if effective_rod.shiny_override is not None:
    frenzy_is_shiny = random.random() <= effective_rod.shiny_override
else:
    frenzy_is_shiny = roll_shiny_on_catch(shiny_config) if shiny_config else False
```

### `CLAUDE.md`

Add `shiny_override` to the Rod JSON keys table in `CLAUDE.md`.

No other files require changes.

---

## Testing

Extend `tests/test_rods_characterization.py`:

| Input | Expected `rod.shiny_override` |
|-------|-------------------------------|
| *(absent)* | `None` |
| `5` | `0.05` |
| `"5%"` | `0.05` |
| `0.05` | `0.05` |
| `0` | `0.0` |
| `1` | `1.0` (documents the footgun) |

Fishing logic: patch `random.random` and verify the override path is taken when `shiny_override` is set, and the global config path is taken when it is `None`.

---

## No-Op Guarantee

Rods without `shiny_override` behave identically to before. `ShinyConfig` is passed through unchanged; appraisal is untouched.
