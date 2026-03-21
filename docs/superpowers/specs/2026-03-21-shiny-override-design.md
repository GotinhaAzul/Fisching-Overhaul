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

- **In scope:** fishing catches (main catch, frenzy catch). Dupe catches inherit the parent catch's `is_shiny` flag, so they are covered implicitly.
- **Out of scope:** appraisal shiny rolls (`roll_shiny_on_appraise`), which remain driven solely by `ShinyConfig.appraise_chance_percent`.

---

## Data Format

Rod JSON gains an optional key `shiny_override`. When absent, shiny rolls use the global config as before.

```json
{ "shiny_override": 5 }
```

Accepted value formats (consistent with other rod probability stats):

| JSON value | Interpreted as |
|------------|---------------|
| `5`        | 5%            |
| `"5%"`     | 5%            |
| `0.05`     | 5%            |
| `0`        | 0% (never shiny) |
| `100`      | 100% (always shiny) |
| *(absent)* | Use global shiny config |

Parsing uses `_normalize_probability` from `utils/rods.py`, which already handles all these forms and clamps to `[0.0, 1.0]`.

---

## Implementation

### `utils/rods.py`

1. Import `Optional` from `typing` (already present via `List`).
2. Add field to `Rod` dataclass:
   ```python
   shiny_override: Optional[float] = None
   ```
3. In `load_rods`, parse the key — `None` if absent, normalized fraction if present:
   ```python
   raw_shiny_override = data.get("shiny_override")
   shiny_override = (
       _normalize_probability(raw_shiny_override)
       if raw_shiny_override is not None
       else None
   )
   ```
4. Pass `shiny_override=shiny_override` into the `Rod(...)` constructor.

### `utils/pesca.py`

At each of the two fishing shiny roll sites, replace:

```python
is_shiny = roll_shiny_on_catch(shiny_config) if shiny_config else False
```

with:

```python
if effective_rod.shiny_override is not None:
    is_shiny = random.random() < effective_rod.shiny_override
else:
    is_shiny = roll_shiny_on_catch(shiny_config) if shiny_config else False
```

The two sites are:
- Main catch (~line 3101)
- Frenzy catch (~line 3292)

No other files require changes.

---

## Testing

Extend `tests/test_rods_characterization.py`:
- Rod with `shiny_override` absent → field is `None`.
- Rod with `shiny_override: 5` → field is `0.05`.
- Rod with `shiny_override: "5%"` → field is `0.05`.
- Rod with `shiny_override: 0.05` → field is `0.05`.
- Rod with `shiny_override: 0` → field is `0.0`.

Fishing logic can be tested by patching `random.random` to confirm the override path is used when the field is set.

---

## No-Op Guarantee

Rods without `shiny_override` behave identically to before. The `ShinyConfig` is passed through unchanged; appraisal is untouched.
