# Major Areas System Design

**Date:** 2026-04-04
**Scope:** Pool organization and pool selection UI only. No content additions and no gameplay identity migration.

---

## Context

Fisching currently loads pools from `pools/<pool-folder>/pool.json` and uses a flat pool selection flow in `utils/pesca.py`. Core systems still rely on existing pool identities:

- saves restore `selected_pool` and `unlocked_pools` by `pool.name`
- some market and requirement paths still also use `pool.folder.name`
- hunts, missions, crafting, and bestiary rewards match pools by existing names

The feature goal is to improve navigation as pool count grows without forcing a save migration or broad content rewrite.

---

## Goal

When the player changes fishing location, the flow becomes:

1. Choose a major area
2. Choose a pool inside that major area

This is a navigation and content-organization feature only. No gameplay rule, unlock rule, or save format changes are required for the first version.

---

## Chosen Approach

Use metadata on each pool plus grouped UI.

- Add an optional `major_area` field to each `pool.json`
- Extend `FishingPool` with `major_area: str`
- Parse and normalize `major_area` in `load_pools()`
- Keep the current folder layout unchanged
- Keep `pool.name` as the canonical gameplay identity
- Keep folder slug behavior unchanged for systems that still depend on `pool.folder.name`

This is the lowest-risk cut because it provides grouped navigation without introducing a new pool identity layer.

---

## Alternatives Considered

### 1. Metadata plus grouped UI

This is the selected approach.

Pros:
- low migration risk
- aligns with current data model
- compatible with save restore and content references
- easy to roll out incrementally across pool JSON files

Cons:
- does not solve future duplicate-name scenarios
- still depends on legacy assumptions around `pool.name` and folder slug usage

### 2. Derived grouping with no content metadata

Infer major areas from current pool names or folder names instead of adding `major_area`.

Pros:
- fastest short-term implementation
- no content file edits required

Cons:
- brittle naming-based heuristics
- hard to scale when more sub-pools are added
- unclear authoring model for future content

### 3. Full area and pool identity model

Introduce stronger IDs or nested content structure now.

Pros:
- cleaner long-term extensibility
- better support for duplicate display names later

Cons:
- unnecessary complexity for this feature
- higher migration and compatibility risk
- touches systems outside the real scope of the request

---

## Architecture

### Data model

`FishingPool` in `utils/pesca.py` gains a new field:

```python
major_area: str
```

The loader populates this value from `pool.json`.

Normalization rules:

- if `major_area` is a string, trim surrounding whitespace
- if the trimmed value is empty, treat it as missing
- if `major_area` is missing or invalid, fall back to `pool.name`

That fallback keeps legacy content valid during rollout and avoids blocking the feature on a full content pass.

### Loading behavior

`load_pools()` continues to scan the same flat folder structure under `pools/`.

It must continue to preserve current behavior for:

- secret pool loading
- hidden pool handling
- rarity weight normalization
- `perfect_catch` parsing
- pool naming and folder slug behavior

Only the additive `major_area` field is introduced.

### Selection flow

`select_pool()` changes from one flat list into a two-step selector:

1. Build a grouped structure from unlocked, non-hidden pools keyed by `major_area`
2. Show the major area list
3. After area selection, show the pool list for that area
4. Return the selected `FishingPool`

Both modern UI and fallback text UI keep the same overall interaction style the project already uses.

---

## UI Behavior

### Area list

- only show major areas that contain at least one unlocked, non-hidden pool
- sort major areas alphabetically
- preserve pagination if the area count exceeds one page

### Pool list within an area

- show unlocked, non-hidden pools for the chosen area
- sort pools alphabetically inside that area
- preserve pagination if needed
- include a back action that returns to the area list instead of leaving pool selection entirely

### Secret pools

Secret pools remain hidden from the visible grouped menus.

The current secret entry code behavior stays available:

- if the user enters a valid secret code, unlock that pool and return it immediately
- hidden pools are still absent from the visible grouped lists

Secret entry codes should continue to work from the new selection flow without requiring a separate menu.

---

## Compatibility Constraints

### Save system

No save schema change is required.

The design is safe as long as pool names do not change because saves currently restore:

- `selected_pool` by `pool.name`
- `unlocked_pools` by `pool.name`

### Name-based systems

These systems remain keyed to the current pool name behavior:

- save restore
- mission requirements and rewards
- hunt pool references
- market pool order references
- crafting requirements that depend on unlocked pool keys
- bestiary reward targeting

### Folder-slug-based behavior

Some code paths still use `pool.folder.name` as an accepted key. That remains valid because the folder layout does not change.

---

## Explicit Non-Goals

This feature does not include:

- moving pools into nested area folders
- renaming existing pool display names
- introducing duplicate pool names across areas
- introducing a new `pool_id`
- area-scoped events
- bestiary reorganization by major area
- HUD changes that display the major area
- new pools, fish, hunts, rods, missions, or mutations

---

## Risks

### Low risk

- extending `FishingPool`
- parsing `major_area`
- adding `major_area` to existing pool JSON files

### Medium risk

- preserving secret-code access cleanly in the new two-step flow
- keeping pagination intuitive in both menus
- keeping modern UI and fallback text UI behavior aligned

### Risk controls

- additive data change only
- deterministic sorting for predictable menu tests
- focused characterization tests around loader and menu behavior
- no identity migration

---

## Test Strategy

Add or extend characterization tests for:

1. explicit `major_area` loading from `pool.json`
2. fallback to `pool.name` when `major_area` is missing or invalid
3. deterministic area ordering
4. deterministic pool ordering inside each area
5. back navigation from pool list to area list
6. secret pool entry codes still unlocking hidden pools
7. save restore still matching selected and unlocked pools by `pool.name`

Primary files:

- `utils/pesca.py`
- `tests/test_events_hunts_characterization.py` (loader tests)
- `tests/test_inventory_characterization.py` (selection flow tests)
- `tests/test_save_system_characterization.py`

---

## File Impact

### Code

- Modify `utils/pesca.py`

### Content

- Update existing `pools/*/pool.json` files to add `major_area` where known

### Tests

- Modify `tests/test_events_hunts_characterization.py`
- Modify `tests/test_inventory_characterization.py`
- Modify `tests/test_save_system_characterization.py`

---

## Recommendation

Ship Major Areas as pool metadata plus grouped selection UI.

It solves the real user problem, fits the current codebase, and avoids turning a simple navigation feature into a risky identity migration. If the project later needs duplicate pool names or stronger area-specific systems, that can be handled as a separate design with an explicit migration plan.
