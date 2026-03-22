# Rod Upgrade Stat-Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make rod upgrade fish requirements and bonus scale with the rod's stat strength — weak rods get common requirements and big bonuses, strong rods get rare requirements and diminished bonuses.

**Architecture:** A single `_stat_strength()` function computes a 0.0–1.0 factor from the rod's stat relative to all loaded rods. This factor modulates rarity weight in `_requirement_selection_score` and rarity contribution in `_requirement_bonus_profile`. No save format changes.

**Tech Stack:** Python 3.10+, pytest

**Spec:** `docs/superpowers/specs/2026-03-22-rod-upgrade-stat-scaling-design.md`

---

### Task 1: Add `_stat_strength` function

**Files:**
- Modify: `utils/rod_upgrades.py` (add function + constants near line 48)
- Test: `tests/test_rod_upgrades_characterization.py`

- [ ] **Step 1: Write the failing test**

```python
def test_stat_strength_characterization() -> None:
    weak = _rod("Fraca", luck=0.05, kg_max=3.0, control=0.1)
    mid = _rod("Media", luck=0.25, kg_max=150.0, control=0.5)
    strong = _rod("Forte", luck=0.70, kg_max=3000.0, control=1.5)
    all_rods = [weak, mid, strong]

    from utils.rod_upgrades import _stat_strength

    # Weak rod is near 0
    assert _stat_strength(weak, "luck", all_rods) == pytest.approx(0.0, abs=0.01)
    assert _stat_strength(strong, "luck", all_rods) == pytest.approx(1.0, abs=0.01)

    # kg_max uses log scale
    kg_strength_mid = _stat_strength(mid, "kg_max", all_rods)
    assert 0.3 < kg_strength_mid < 0.7

    # control linear
    ctrl_strength_mid = _stat_strength(mid, "control", all_rods)
    assert 0.2 < ctrl_strength_mid < 0.4

    # Single rod edge case: returns 0.5
    assert _stat_strength(weak, "luck", [weak]) == pytest.approx(0.5)

    # Unknown stat returns 0.5
    assert _stat_strength(weak, "unknown", all_rods) == pytest.approx(0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rod_upgrades_characterization.py::test_stat_strength_characterization -v`
Expected: FAIL with ImportError (function doesn't exist yet)

- [ ] **Step 3: Write the implementation**

Add to `utils/rod_upgrades.py` after the existing constants (around line 48):

```python
_RARITY_SELECTION_FLOOR = 0.2
_RARITY_BONUS_DAMPING = 0.7


def _stat_strength(rod: Rod, stat: str, all_rods: Sequence[Rod]) -> float:
    if stat not in UPGRADEABLE_STATS or not all_rods:
        return 0.5
    values = [float(getattr(r, stat, 0.0)) for r in all_rods]
    value = float(getattr(rod, stat, 0.0))
    if stat == "kg_max":
        values = [math.log10(max(1.0, v)) for v in values]
        value = math.log10(max(1.0, value))
    lo, hi = min(values), max(values)
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rod_upgrades_characterization.py::test_stat_strength_characterization -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/rod_upgrades.py tests/test_rod_upgrades_characterization.py
git commit -m "rod-upgrades: add _stat_strength function and constants"
```

---

### Task 2: Modulate rarity in requirement selection

**Files:**
- Modify: `utils/rod_upgrades.py` — `_requirement_selection_score` and `generate_fish_requirements`
- Test: `tests/test_rod_upgrades_characterization.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_requirements_rarity_scales_with_stat_strength(monkeypatch) -> None:
    # Fish designed so value/weight are similar — rarity is the only differentiator.
    # Common fish has slightly higher value so that when rarity is dampened, it wins.
    common_fish = _DummyFish("Tilapia Dourada", "Comum", 60.0, 5.0, 15.0)
    mythic_fish = _DummyFish("Dragao Abissal", "Mitico", 50.0, 4.0, 12.0)

    monkeypatch.setattr("utils.rod_upgrades.random.randint", lambda _a, _b: 1)
    monkeypatch.setattr(
        "utils.rod_upgrades.random.sample",
        lambda population, count: list(population)[:count],
    )

    pool_fish = [common_fish, mythic_fish]
    weak_rod = _rod("Fraca", luck=0.05)
    strong_rod = _rod("Forte", luck=0.70)
    all_rods = [weak_rod, strong_rod]

    weak_reqs = generate_fish_requirements(pool_fish, weak_rod, "luck", all_rods=all_rods)
    strong_reqs = generate_fish_requirements(pool_fish, strong_rod, "luck", all_rods=all_rods)

    # Weak rod: rarity dampened, so common fish with higher value wins
    assert weak_reqs[0].fish_name == "Tilapia Dourada"
    # Strong rod: rarity fully weighted, so mythic wins despite lower value
    assert strong_reqs[0].fish_name == "Dragao Abissal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rod_upgrades_characterization.py::test_generate_requirements_rarity_scales_with_stat_strength -v`
Expected: FAIL — `generate_fish_requirements` doesn't accept `all_rods` yet

- [ ] **Step 3: Implement rarity dampening**

In `utils/rod_upgrades.py`:

1. Add `stat_strength: float = 0.0` parameter to `_requirement_selection_score` (after the existing `control_bounds` param). Compute `effective_rarity` once at the top of the function body, then replace all 4 occurrences of `rarity_score` in the weighted sums with `effective_rarity`:

   ```python
   effective_rarity = rarity_score * (_RARITY_SELECTION_FLOOR + (1 - _RARITY_SELECTION_FLOOR) * stat_strength)
   ```

   The 4 occurrences are in:
   - `generic_profile` line: `(rarity_score * 0.55)` → `(effective_rarity * 0.55)`
   - `stat_profile` for `kg_max`: `(rarity_score * 0.20)` → `(effective_rarity * 0.20)`
   - `stat_profile` for `control`: `(rarity_score * 0.20)` → `(effective_rarity * 0.20)`
   - `stat_profile` for `luck`: `(rarity_score * 0.70)` → `(effective_rarity * 0.70)`

2. Add `all_rods: Sequence[Rod] = ()` keyword parameter to `generate_fish_requirements`. Compute strength before the `ranked_fish = sorted(...)` call and thread it into the lambda:

   ```python
   strength = _stat_strength(rod, normalized_stat, list(all_rods))
   ranked_fish = sorted(
       available_fish,
       key=lambda fish: _requirement_selection_score(
           fish,
           stat=normalized_stat,
           rod_focus=rod_focus,
           tier_focus=tier_focus,
           rarity_bounds=(...),
           weight_bounds=(...),
           value_bounds=(...),
           control_bounds=(...),
           stat_strength=strength,
       ),
       reverse=True,
   )
   ```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rod_upgrades_characterization.py::test_generate_requirements_rarity_scales_with_stat_strength -v`
Expected: PASS

- [ ] **Step 5: Fix existing tests**

The existing `test_generate_requirements_bias_by_stat_and_rod_characterization` test calls `generate_fish_requirements` without `all_rods`. Since `all_rods` defaults to `()`, `_stat_strength` returns 0.5 (empty list edge case). This may shift the ranking. Run:

```bash
python -m pytest tests/test_rod_upgrades_characterization.py -v
```

If any existing tests fail, update their expected values to match the new behavior (stat_strength=0.5 when all_rods not provided). The characterization tests should reflect the new reality.

- [ ] **Step 6: Commit**

```bash
git add utils/rod_upgrades.py tests/test_rod_upgrades_characterization.py
git commit -m "rod-upgrades: scale requirement rarity with rod stat strength"
```

---

### Task 3: Modulate rarity in bonus calculation

**Files:**
- Modify: `utils/rod_upgrades.py` — `_requirement_bonus_profile` and `calculate_upgrade_bonus`
- Test: `tests/test_rod_upgrades_characterization.py`

- [ ] **Step 1: Write the failing test**

```python
def test_calculate_bonus_diminishes_with_stat_strength(monkeypatch) -> None:
    mythic_fish = _DummyFish("Dragao Abissal", "Mitico", 500.0, 50.0, 200.0)
    # Use count=5 so total_score is high enough relative to _UPGRADE_SCORE_TARGET (4.0)
    mythic_req = [UpgradeRequirement("Dragao Abissal", "Mitico", 5)]
    fish_by_name = {"Dragao Abissal": mythic_fish}

    monkeypatch.setattr("utils.rod_upgrades.random.uniform", lambda _a, _b: 0.0)

    weak_rod = _rod("Fraca", luck=0.05)
    strong_rod = _rod("Forte", luck=0.70)
    all_rods = [weak_rod, strong_rod]

    weak_bonus = calculate_upgrade_bonus(
        mythic_req, stat="luck", fish_by_name=fish_by_name,
        rod=weak_rod, all_rods=all_rods,
    )
    strong_bonus = calculate_upgrade_bonus(
        mythic_req, stat="luck", fish_by_name=fish_by_name,
        rod=strong_rod, all_rods=all_rods,
    )

    # Weak rod gets significantly more bonus from the same mythic fish
    assert weak_bonus > strong_bonus
    # Don't assert exact thresholds — just verify the relative ordering
    # and that the gap is meaningful (at least 3 percentage points)
    assert (weak_bonus - strong_bonus) >= 0.03
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rod_upgrades_characterization.py::test_calculate_bonus_diminishes_with_stat_strength -v`
Expected: FAIL — `calculate_upgrade_bonus` doesn't accept `rod` or `all_rods`

- [ ] **Step 3: Implement bonus dampening**

In `utils/rod_upgrades.py`:

1. Add `stat_strength: float = 0.0` parameter to `_requirement_bonus_profile`. Apply dampening to the rarity component in all stat branches:
   ```python
   effective_rarity = rarity_score * (1.0 - _RARITY_BONUS_DAMPING * stat_strength)
   ```
   Use `effective_rarity` wherever `rarity_score` appears in the weighted sums.

2. Add `rod: Rod | None = None` and `all_rods: Sequence[Rod] = ()` keyword parameters to `calculate_upgrade_bonus`. Compute `strength = _stat_strength(rod, normalized_stat, list(all_rods)) if rod is not None else 0.0` and pass it to `_requirement_bonus_profile` calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rod_upgrades_characterization.py::test_calculate_bonus_diminishes_with_stat_strength -v`
Expected: PASS

- [ ] **Step 5: Fix existing tests**

Run all tests:
```bash
python -m pytest tests/test_rod_upgrades_characterization.py -v
```

Existing tests call `calculate_upgrade_bonus` without `rod`/`all_rods`, so `stat_strength` defaults to 0.0 (no dampening). These should still pass unchanged. If any fail, investigate and update expected values.

- [ ] **Step 6: Commit**

```bash
git add utils/rod_upgrades.py tests/test_rod_upgrades_characterization.py
git commit -m "rod-upgrades: diminish bonus from rare fish for strong rods"
```

---

### Task 4: Update market.py caller and test mocks

**Files:**
- Modify: `utils/market.py:1653` and `utils/market.py:1734`
- Modify: `tests/test_rod_upgrades_characterization.py` (monkeypatch signatures)

Note: The spec lists `utils/pesca.py` as a caller, but it does not call `generate_fish_requirements` or `calculate_upgrade_bonus` directly — `market.py` is the only caller.

- [ ] **Step 1: Update `generate_fish_requirements` call in market.py**

At line 1653, add `all_rods=available_rods`:
```python
requirements = generate_fish_requirements(
    _get_upgrade_pool_fish(),
    selected_rod,
    selected_stat,
    all_rods=available_rods,
)
```

- [ ] **Step 2: Update `calculate_upgrade_bonus` call in market.py**

At line 1734, add `rod=selected_rod` and `all_rods=available_rods`:
```python
bonus = calculate_upgrade_bonus(
    list(requirements),
    stat=selected_stat,
    fish_by_name=fish_by_name,
    rod=selected_rod,
    all_rods=available_rods,
)
```

- [ ] **Step 3: Update monkeypatched test lambdas to accept `all_rods` kwarg**

The market integration tests monkeypatch `generate_fish_requirements` with positional-only lambdas that will break when `all_rods=` is passed. Add `**_kwargs` to each:

- `test_show_market_upgrade_flow_characterization` line 244: `def _capture_requirements(pool_fish, _rod, stat, **_kwargs):`
- `test_show_market_upgrade_ignores_secret_pool_materials_characterization` line 310: `def _capture_requirements(pool_fish, _rod, stat, **_kwargs):`
- `test_show_market_upgrade_blocks_unsellable_materials_characterization` line 374: `lambda _pool_fish, _rod, _stat, **_kwargs: [...]`
- `test_show_market_persists_upgrade_recipe_per_rod_until_upgrade` line 425: `def _generate_requirements(_pool_fish, _rod, stat, **_kwargs):`

The `calculate_upgrade_bonus` monkeypatches already use `**_kwargs` — verify they still work.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/test_rod_upgrades_characterization.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Run entire project test suite**

```bash
python -m pytest -q
```

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add utils/market.py tests/test_rod_upgrades_characterization.py
git commit -m "market: pass all_rods to upgrade functions, update test mocks"
```
