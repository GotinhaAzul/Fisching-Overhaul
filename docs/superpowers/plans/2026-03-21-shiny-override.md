# `shiny_override` Rod Stat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `shiny_override` field to rods that overrides the global shiny catch chance while fishing.

**Architecture:** New `Optional[float]` field on `Rod` dataclass, parsed from JSON via existing `_normalize_probability`. Two call sites in `run_fishing_round` (main catch, frenzy catch) gain a conditional check: use override if present, else fall through to global `ShinyConfig`.

**Tech Stack:** Python 3.10+, pytest, JSON data files.

**Spec:** `docs/superpowers/specs/2026-03-21-shiny-override-design.md`

---

### Task 1: Add `shiny_override` field to Rod dataclass and parser

**Files:**
- Modify: `utils/rods.py:4` (typing import)
- Modify: `utils/rods.py:98` (new field after `counts_for_bestiary_completion`)
- Modify: `utils/rods.py:133-164` (parse + pass to constructor)
- Test: `tests/test_rods_characterization.py`

- [ ] **Step 1: Write failing test — rod without `shiny_override` defaults to `None`**

Add to `tests/test_rods_characterization.py`:

```python
def test_shiny_override_absent_defaults_to_none(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Plain Rod", "luck": 0.0, "kg_max": 10.0, "control": 0.0, "description": "", "price": 0},
    )
    rod = load_rods(tmp_path)[0]
    assert rod.shiny_override is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rods_characterization.py::test_shiny_override_absent_defaults_to_none -v`
Expected: FAIL — `Rod` has no attribute `shiny_override`.

- [ ] **Step 3: Add `Optional` import and `shiny_override` field to `Rod`**

In `utils/rods.py`, change the typing import (line 4):

```python
from typing import List, Optional
```

Add new field at the end of the `Rod` dataclass (after line 98, `counts_for_bestiary_completion`):

```python
    shiny_override: Optional[float] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rods_characterization.py::test_shiny_override_absent_defaults_to_none -v`
Expected: PASS

- [ ] **Step 5: Write failing test — rod with `shiny_override` integer parsed correctly**

Add to `tests/test_rods_characterization.py`:

```python
def test_shiny_override_integer_parsed_as_percent(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Shiny Rod", "luck": 0.0, "kg_max": 10.0, "control": 0.0, "description": "", "price": 0, "shiny_override": 5},
    )
    rod = load_rods(tmp_path)[0]
    assert rod.shiny_override == 0.05
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_rods_characterization.py::test_shiny_override_integer_parsed_as_percent -v`
Expected: FAIL — `rod.shiny_override` is `None` because `load_rods` doesn't parse the key yet.

- [ ] **Step 7: Add `shiny_override` parsing to `load_rods`**

In `utils/rods.py`, inside `load_rods`, add these lines just before the `rods.append(Rod(…))` call (after the `counts_for_bestiary_completion` block, around line 133):

```python
        raw_shiny_override = data.get("shiny_override")
        shiny_override = (
            _normalize_probability(raw_shiny_override)
            if raw_shiny_override is not None
            else None
        )
```

Then add `shiny_override=shiny_override,` as the last kwarg in the `Rod(...)` constructor call, after `counts_for_bestiary_completion=counts_for_bestiary_completion,`.

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest tests/test_rods_characterization.py::test_shiny_override_integer_parsed_as_percent -v`
Expected: PASS

- [ ] **Step 9: Write remaining parse-format tests**

Add to `tests/test_rods_characterization.py`:

```python
def test_shiny_override_percent_string(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": "5%"},
    )
    assert load_rods(tmp_path)[0].shiny_override == 0.05


def test_shiny_override_decimal_fraction(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": 0.05},
    )
    assert load_rods(tmp_path)[0].shiny_override == 0.05


def test_shiny_override_zero_means_never(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": 0},
    )
    assert load_rods(tmp_path)[0].shiny_override == 0.0


def test_shiny_override_one_means_always(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": 1},
    )
    assert load_rods(tmp_path)[0].shiny_override == 1.0
```

- [ ] **Step 10: Run all rod tests**

Run: `python -m pytest tests/test_rods_characterization.py -v`
Expected: All PASS (new tests + existing tests unchanged).

- [ ] **Step 11: Commit**

```bash
git add utils/rods.py tests/test_rods_characterization.py
git commit -m "rods: add shiny_override field with normalize_probability parsing"
```

---

### Task 2: Wire `shiny_override` into fishing shiny rolls

**Files:**
- Modify: `utils/pesca.py:3101` (main catch shiny roll)
- Modify: `utils/pesca.py:3292` (frenzy catch shiny roll)

- [ ] **Step 1: Replace the main catch shiny roll (line 3101)**

In `utils/pesca.py`, replace the single line:

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

(`random` is already imported in `pesca.py`.)

- [ ] **Step 2: Replace the frenzy catch shiny roll (line 3292)**

In `utils/pesca.py`, replace the single line:

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

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -q`
Expected: All existing tests still pass. (The fishing logic isn't unit-tested in isolation — the characterization tests cover rod parsing and general game behavior.)

- [ ] **Step 4: Commit**

```bash
git add utils/pesca.py
git commit -m "pesca: use rod shiny_override for catch shiny rolls when set"
```

---

### Task 3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md:58`

- [ ] **Step 1: Add `shiny_override` to the Rod JSON keys line**

In `CLAUDE.md`, line 58, change:

```
Rod JSON keys: `name`, `luck`, `kg_max`, `control`, `price`, `unlocked_default`, `slash_chance`, `slam_chance`, `recover_chance`, `dupe_chance`.
```

to:

```
Rod JSON keys: `name`, `luck`, `kg_max`, `control`, `price`, `unlocked_default`, `slash_chance`, `slam_chance`, `recover_chance`, `dupe_chance`, `shiny_override`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add shiny_override to CLAUDE.md rod keys"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: All tests pass, no regressions.

- [ ] **Step 2: Spot-check a rod JSON to confirm no existing rod accidentally has a `shiny_override` key**

Run: `grep -r "shiny_override" rods/`
Expected: No matches (no existing rods use this key yet).
