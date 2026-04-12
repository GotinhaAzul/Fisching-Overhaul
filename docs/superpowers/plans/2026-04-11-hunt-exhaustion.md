# Hunt Exhaustion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make active hunts remove caught hunt fish from that hunt instance and end immediately when no hunt fish remain, while preserving the existing timer limit.

**Architecture:** Keep hunt depletion state inside `HuntManager` by extending `ActiveHunt` with per-activation remaining fish names and adding manager APIs for reading and consuming that state. Then update the fishing round to build hunt fish availability from the manager instead of `HuntDefinition.fish_profiles`, so hunt exhaustion affects live round selection, serialization, restore, and notifications through one source of truth.

**Tech Stack:** Python 3.10+, pytest, data-driven hunt definitions loaded by `utils.pesca`, runtime hunt state managed in `utils.hunts`

---

## File Map

- Modify: `utils/hunts.py:30-314`
  Purpose: store per-active-hunt remaining fish, serialize/restore it, expose availability and consume helpers, and share one termination path for timer expiry and hunt exhaustion.
- Modify: `utils/pesca.py:3050-3124,3297-3298`
  Purpose: use `HuntManager` runtime availability during round setup and consume hunt fish on successful catches.
- Modify: `utils/pesca_round_helpers.py:43-54`
  Purpose: accept runtime hunt fish profiles instead of always reading from the static hunt definition.
- Modify: `tests/test_events_hunts_characterization.py:118-214`
  Purpose: characterize initialization, depletion, early ending, serialize/restore, reset-on-next-activation, and legacy restore behavior.

### Task 1: Hunt Manager Active-Fish State

**Files:**
- Modify: `tests/test_events_hunts_characterization.py:118-214`
- Modify: `utils/hunts.py:30-314`
- Test: `tests/test_events_hunts_characterization.py`

- [ ] **Step 1: Write the failing tests**

Add and update characterization tests so the manager must expose remaining hunt fish state, preserve it across save/restore, handle legacy active state without remaining names, and end only when the final hunt fish is consumed.

```python
from typing import Any


def test_hunt_manager_force_hunt_notification_queue_characterization(monkeypatch) -> None:
    now = {"value": 80.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt("h1", name="Caos", fish_profiles=[_fish("Lula Gigante")])
    manager = HuntManager([hunt], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.record_catch("Rio")
    selected = manager.force_hunt("h1")

    assert selected is not None
    active = manager.get_active_hunt_for_pool("Rio")
    assert active is not None
    assert active.remaining_fish_names == ["Lula Gigante"]


def test_hunt_manager_serialize_restore_roundtrip_characterization(monkeypatch) -> None:
    now = {"value": 500.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunts = [
        _hunt("h1", name="Caos", fish_profiles=[_fish("Lula Gigante"), _fish("Kraken Jovem")]),
        _hunt("h2", name="Marola", pool_name="Lagoa", fish_profiles=[_fish("Pirarucu Ancestral")]),
    ]
    manager = HuntManager(hunts, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.force_hunt("h1")
    ended = manager.consume_hunt_fish(
        "Rio",
        "Lula Gigante",
        catchable_fish_names={"Kraken Jovem"},
    )

    assert ended is False
    raw_state = manager.serialize_state()

    restored = HuntManager(hunts, dev_tools_enabled=True)
    restored.restore_state(raw_state)
    restored_state = restored.serialize_state()

    active_by_pool: Any = restored_state["active_by_pool"]
    assert active_by_pool["Rio"]["remaining_fish_names"] == ["Kraken Jovem"]
    assert [fish.name for fish in restored.get_available_fish_for_pool("Rio")] == ["Kraken Jovem"]


def test_hunt_manager_restores_legacy_active_hunt_with_full_fish_list(monkeypatch) -> None:
    now = {"value": 1200.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt(
        "h1",
        name="Guardiao",
        fish_profiles=[_fish("Mossjaw"), _fish("Awakened Mossjaw")],
    )
    manager = HuntManager([hunt], dev_tools_enabled=True)

    manager.restore_state(
        {
            "hunts": {"h1": {"disturbance": 0.0, "cooldown_remaining_s": 0.0, "next_check_in_s": 0.0}},
            "active_by_pool": {"Rio": {"hunt_id": "h1", "remaining_s": 15.0}},
        }
    )

    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Mossjaw",
        "Awakened Mossjaw",
    ]
```

- [ ] **Step 2: Run the hunt manager tests to verify they fail**

Run: `python -m pytest tests/test_events_hunts_characterization.py -k hunt_manager -q`
Expected: `FAIL` with `AttributeError` or assertion failures because `ActiveHunt` does not yet carry `remaining_fish_names` and `HuntManager` does not yet expose depletion-aware availability/restore behavior.

- [ ] **Step 3: Write the minimal hunt manager implementation**

Update `utils/hunts.py` so active hunts keep their own remaining fish names, use that state for availability, and share a helper for timer-based or depletion-based ending.

```python
@dataclass
class ActiveHunt:
    definition: HuntDefinition
    started_at: float
    ends_at: float
    remaining_fish_names: List[str]

    def time_left(self) -> float:
        return max(0.0, self.ends_at - time.monotonic())


class HuntManager:
    def force_hunt(self, hunt_id: str) -> Optional[HuntDefinition]:
        if not self._dev_tools_enabled:
            return None

        target_id = hunt_id.casefold()
        selected: Optional[HuntDefinition] = None
        now = time.monotonic()
        replaced: Optional[ActiveHunt] = None

        with self._lock:
            for hunt in self._hunts:
                if hunt.hunt_id.casefold() == target_id:
                    selected = hunt
                    break
            if not selected:
                return None

            replaced = self._active_by_pool.get(selected.pool_name)
            self._active_by_pool[selected.pool_name] = self._build_active_hunt(selected, now)
            progress = self._progress_by_hunt.get(selected.hunt_id)
            if progress:
                progress.disturbance = 0.0

        if replaced and replaced.definition.hunt_id != selected.hunt_id:
            self._emit_notification(f"A hunt '{replaced.definition.name}' foi encerrada (forcada).")
        self._emit_notification(f"Hunt iniciada em {selected.pool_name}: {selected.name}")
        return selected

    def get_available_fish_for_pool(self, pool_name: str) -> List["FishProfile"]:
        with self._lock:
            active = self._active_by_pool.get(pool_name)
            if not active:
                return []
            return self._resolve_remaining_fish(active)

    def consume_hunt_fish(
        self,
        pool_name: str,
        fish_name: str,
        *,
        catchable_fish_names: set[str],
    ) -> bool:
        notification: Optional[str] = None
        ended = False
        with self._lock:
            active = self._active_by_pool.get(pool_name)
            if not active:
                return False
            matching_names = [name for name in active.remaining_fish_names if name == fish_name]
            if not matching_names:
                return False
            active.remaining_fish_names = [name for name in active.remaining_fish_names if name != fish_name]
            if active.remaining_fish_names:
                return False
            ended = True
            notification = self._end_active_hunt_locked(pool_name, ended_at=time.monotonic())

        if notification:
            self._emit_notification(notification)
        return ended

    def serialize_state(self) -> Dict[str, object]:
        now = time.monotonic()
        with self._lock:
            hunts_data: Dict[str, Dict[str, float]] = {}
            for definition in self._hunts:
                progress = self._progress_by_hunt.get(definition.hunt_id)
                if not progress:
                    continue
                next_check_in = 0.0
                if definition.check_interval_s > 0:
                    elapsed = now - progress.last_check
                    next_check_in = max(0.0, definition.check_interval_s - elapsed)
                hunts_data[definition.hunt_id] = {
                    "disturbance": self._clamp_disturbance(definition, progress.disturbance),
                    "cooldown_remaining_s": max(0.0, progress.cooldown_ends_at - now),
                    "next_check_in_s": next_check_in,
                }

            active_data: Dict[str, Dict[str, object]] = {}
            for pool_name, active in self._active_by_pool.items():
                remaining_s = max(0.0, active.ends_at - now)
                if remaining_s <= 0:
                    continue
                active_data[pool_name] = {
                    "hunt_id": active.definition.hunt_id,
                    "remaining_s": remaining_s,
                    "remaining_fish_names": list(active.remaining_fish_names),
                }

        return {"hunts": hunts_data, "active_by_pool": active_data}

    def restore_state(self, raw_state: object) -> None:
        now = time.monotonic()
        with self._lock:
            self._active_by_pool.clear()
            self._progress_by_hunt = {
                hunt.hunt_id: HuntProgressState(disturbance=0.0, last_check=now, cooldown_ends_at=0.0)
                for hunt in self._hunts
            }
            if not isinstance(raw_state, dict):
                return

            raw_hunts = raw_state.get("hunts")
            if isinstance(raw_hunts, dict):
                for hunt_id, raw_progress in raw_hunts.items():
                    if not isinstance(hunt_id, str) or not isinstance(raw_progress, dict):
                        continue
                    definition = self._hunts_by_id.get(hunt_id)
                    progress = self._progress_by_hunt.get(hunt_id)
                    if not definition or not progress:
                        continue
                    disturbance = self._safe_float(raw_progress.get("disturbance"))
                    cooldown_remaining = max(0.0, self._safe_float(raw_progress.get("cooldown_remaining_s")))
                    next_check_in = max(0.0, self._safe_float(raw_progress.get("next_check_in_s")))
                    if definition.check_interval_s > 0:
                        next_check_in = min(definition.check_interval_s, next_check_in)
                        elapsed = definition.check_interval_s - next_check_in
                        progress.last_check = now - elapsed
                    else:
                        progress.last_check = now
                    progress.disturbance = self._clamp_disturbance(definition, disturbance)
                    progress.cooldown_ends_at = now + cooldown_remaining

            raw_active = raw_state.get("active_by_pool")
            if not isinstance(raw_active, dict):
                return

            for pool_name, raw_entry in raw_active.items():
                if not isinstance(pool_name, str) or not isinstance(raw_entry, dict):
                    continue
                hunt_id = raw_entry.get("hunt_id")
                if not isinstance(hunt_id, str):
                    continue
                definition = self._hunts_by_id.get(hunt_id)
                if not definition or definition.pool_name != pool_name or pool_name in self._active_by_pool:
                    continue
                remaining_s = max(0.0, self._safe_float(raw_entry.get("remaining_s")))
                if remaining_s <= 0:
                    continue
                raw_remaining_names = raw_entry.get("remaining_fish_names")
                remaining_names = self._restore_remaining_fish_names(definition, raw_remaining_names)
                self._active_by_pool[pool_name] = ActiveHunt(
                    definition=definition,
                    started_at=now,
                    ends_at=now + remaining_s,
                    remaining_fish_names=remaining_names,
                )

    def _build_active_hunt(self, definition: HuntDefinition, now: float) -> ActiveHunt:
        return ActiveHunt(
            definition=definition,
            started_at=now,
            ends_at=now + definition.duration_s,
            remaining_fish_names=[fish.name for fish in definition.fish_profiles],
        )

    def _resolve_remaining_fish(self, active: ActiveHunt) -> List["FishProfile"]:
        remaining_name_set = set(active.remaining_fish_names)
        return [fish for fish in active.definition.fish_profiles if fish.name in remaining_name_set]

    def _restore_remaining_fish_names(
        self,
        definition: HuntDefinition,
        raw_remaining_names: object,
    ) -> List[str]:
        default_names = [fish.name for fish in definition.fish_profiles]
        if not isinstance(raw_remaining_names, list):
            return default_names
        allowed_names = {fish.name for fish in definition.fish_profiles}
        restored = [name for name in raw_remaining_names if isinstance(name, str) and name in allowed_names]
        return restored or default_names

    def _end_active_hunt_locked(self, pool_name: str, *, ended_at: float) -> Optional[str]:
        active = self._active_by_pool.pop(pool_name, None)
        if not active:
            return None
        progress = self._progress_by_hunt.get(active.definition.hunt_id)
        if progress:
            progress.cooldown_ends_at = max(
                progress.cooldown_ends_at,
                ended_at + max(0.0, active.definition.cooldown_s),
            )
        return f"A hunt '{active.definition.name}' terminou."
```

Also replace the timer-expiry branch in `_run_loop()` so it reuses `_end_active_hunt_locked(...)`, and replace both hunt-start sites with `_build_active_hunt(...)`.

- [ ] **Step 4: Run the hunt manager tests to verify they pass**

Run: `python -m pytest tests/test_events_hunts_characterization.py -k hunt_manager -q`
Expected: `PASS` for the hunt-manager characterization cases, including early ending and legacy restore fallback.

- [ ] **Step 5: Commit the hunt manager slice**

```bash
git add tests/test_events_hunts_characterization.py utils/hunts.py
git commit -m "hunts: track remaining fish in active hunts"
```

### Task 2: Fishing Round Uses Runtime Hunt Availability

**Files:**
- Modify: `utils/pesca_round_helpers.py:43-54`
- Modify: `utils/pesca.py:3050-3124,3297-3298`
- Modify: `tests/test_events_hunts_characterization.py:186-214`
- Test: `tests/test_events_hunts_characterization.py`

- [ ] **Step 1: Write the failing tests for multi-fish continuation and reset-on-next-hunt**

Extend the existing consumption characterization so a multi-fish hunt stays active after the first distinct catch, then ends only when the last remaining hunt fish is consumed, and starts fresh on the next activation.

```python
def test_hunt_manager_consumes_only_current_hunt_instance_and_ends_when_exhausted(
    monkeypatch,
) -> None:
    now = {"value": 900.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt(
        "h1",
        name="Ataque",
        fish_profiles=[_fish("Mossjaw"), _fish("Awakened Mossjaw")],
    )
    manager = HuntManager([hunt], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.force_hunt("h1")
    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Mossjaw",
        "Awakened Mossjaw",
    ]

    ended = manager.consume_hunt_fish(
        "Rio",
        "Mossjaw",
        catchable_fish_names={"Awakened Mossjaw"},
    )
    assert ended is False
    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Awakened Mossjaw",
    ]
    assert manager.get_active_hunt_for_pool("Rio") is not None

    ended = manager.consume_hunt_fish(
        "Rio",
        "Awakened Mossjaw",
        catchable_fish_names=set(),
    )
    assert ended is True
    assert manager.get_active_hunt_for_pool("Rio") is None

    now["value"] = 930.0
    manager.force_hunt("h1")
    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Mossjaw",
        "Awakened Mossjaw",
    ]
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python -m pytest tests/test_events_hunts_characterization.py -k "consumes_only_current_hunt_instance or serialize_restore_roundtrip" -q`
Expected: `FAIL` if the manager still ends too early, preserves the wrong remaining fish set, or resets incorrectly between activations.

- [ ] **Step 3: Wire the fishing round to runtime hunt fish availability**

Update `utils/pesca_round_helpers.py` so the helper receives explicit runtime hunt fish, then update `utils/pesca.py` to fetch those fish from `HuntManager`, compute hunt membership by fish name, and consume the hunt fish after a successful catch.

```python
def combine_fish_profiles(
    selected_pool: "FishingPool",
    event_def: Optional["EventDefinition"],
    hunt_fish_profiles: Optional[Sequence["FishProfile"]],
) -> List["FishProfile"]:
    event_fish = event_def.fish_profiles if event_def else []
    hunt_fish = list(hunt_fish_profiles or [])
    return list(selected_pool.fish_profiles) + list(event_fish) + hunt_fish
```

```python
active_event = event_manager.get_active_event() if event_manager else None
event_def = active_event.definition if active_event else None
active_hunt = (
    hunt_manager.get_active_hunt_for_pool(selected_pool.name)
    if hunt_manager
    else None
)
hunt_fish = (
    hunt_manager.get_available_fish_for_pool(selected_pool.name)
    if hunt_manager
    else []
)
hunt_fish_names = {fish.name for fish in hunt_fish}
combined_fish = combine_fish_profiles(selected_pool, event_def, hunt_fish)
eligible_fish = filter_eligible_fish(combined_fish, kg_max=effective_kg_max)

...

if pending_reengage_fish_name:
    matching_fish = next(
        (candidate for candidate in eligible_fish if candidate.name == pending_reengage_fish_name),
        None,
    )
    if matching_fish is not None:
        fish = matching_fish
        is_hunt_fish = pending_reengage_hunt_flag and fish.name in hunt_fish_names
    else:
        pending_reengage_fish_name = None
        pending_reengage_hunt_flag = False
        fish = selected_pool.choose_fish(
            eligible_fish,
            rod_luck,
            rarity_weights_override=combined_weights,
        )
        is_hunt_fish = fish.name in hunt_fish_names
else:
    fish = selected_pool.choose_fish(
        eligible_fish,
        rod_luck,
        rarity_weights_override=combined_weights,
    )
    is_hunt_fish = fish.name in hunt_fish_names

...

if hunt_manager:
    hunt_manager.record_catch(selected_pool.name)
    if is_hunt_fish:
        hunt_manager.consume_hunt_fish(
            selected_pool.name,
            fish.name,
            catchable_fish_names={candidate.name for candidate in eligible_fish},
        )
```

This keeps round setup aligned with the manager's depleted state, so fish removed from an active hunt cannot be offered again during the same activation.

- [ ] **Step 4: Run the focused regression tests to verify they pass**

Run: `python -m pytest tests/test_events_hunts_characterization.py -k hunt_manager -q`
Expected: `PASS` for initialization, depletion, restore, reset-on-next-hunt, and final-fish early termination.

Then run: `python -m pytest tests/test_events_hunts_characterization.py -q`
Expected: `PASS` for the full hunt/event characterization file, confirming no unrelated hunt-loading behavior regressed.

- [ ] **Step 5: Commit the round-integration slice**

```bash
git add tests/test_events_hunts_characterization.py utils/pesca.py utils/pesca_round_helpers.py
git commit -m "fishing: end hunts when hunt fish are exhausted"
```

## Verification Checklist

- Run: `python -m pytest tests/test_events_hunts_characterization.py -q`
  Expected: full hunt/event characterization file passes.
- Run: `python -m pytest -q`
  Expected: full suite passes with no hunt serialization or round-selection regressions.
- Manually inspect `utils/hunts.py` to confirm both timer expiry and hunt exhaustion route through the same end-notification message.
- Manually inspect `utils/pesca.py` to confirm active hunt fish selection now uses `hunt_manager.get_available_fish_for_pool(...)` instead of `hunt_def.fish_profiles`.

## Self-Review

- Spec coverage: covered active-hunt state, catch depletion rules, multi-fish hunts, timer coexistence, save compatibility, and reset-on-next-hunt.
- Placeholder scan: no `TODO`, `TBD`, or unnamed helpers remain in the tasks.
- Type consistency: the plan uses `remaining_fish_names`, `get_available_fish_for_pool(...)`, and `consume_hunt_fish(...)` consistently across tests, hunt manager code, and fishing-loop integration.
