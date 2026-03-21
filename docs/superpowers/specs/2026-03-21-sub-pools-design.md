# Sub-Pools (Areas) Design

## Summary

Add sub-pools ("areas") to the fishing game. When a player selects a pool that has areas, a second menu appears asking which area to fish in. Each area has its own fish list and rarity weights. The bestiary merges all areas under the parent pool name. Areas can be individually locked/unlocked.

## Folder Structure & JSON Schema

### Pool with areas (new)

```
pools/geleira_snowcap/
  pool.json                <- parent metadata only
  areas/
    costa_gelada/
      area.json            <- area metadata + rarity_chances
      fish/
        *.json
    lago_congelado/
      area.json
      fish/
        *.json
```

**Parent `pool.json`** (no `rarity_chances`):
```json
{
  "name": "Geleira Snowcap",
  "description": "Uma cadeia de montanhas geladas...",
  "unlocked_default": false
}
```

**`area.json`**:
```json
{
  "name": "Costa Gelada",
  "description": "A costa congelada no pe da montanha.",
  "rarity_chances": { "Comum": 40, "Incomum": 30, "Raro": 20, "Epico": 8, "Lendario": 2 },
  "unlocked_default": true
}
```

### Pool without areas (unchanged)

```
pools/lagoa/
  pool.json
  fish/
    carpa.json
```

Fully backwards compatible. No changes needed.

## Data Model Changes

`FishingPool` gains two new fields:

```python
@dataclass
class FishingPool:
    name: str
    fish_profiles: List[FishProfile]
    folder: Path
    description: str
    rarity_weights: Dict[str, int]
    unlocked_default: bool = False
    # ... existing fields ...
    areas: List["FishingPool"] = field(default_factory=list)  # NEW
    parent_pool_name: str = ""                                 # NEW
```

- **No-area pools**: `areas` is empty, `parent_pool_name` is empty. Unchanged behavior.
- **Parent pools**: `areas` populated with sub-pools. `fish_profiles` and `rarity_weights` are empty (parent is not fishable). `parent_pool_name` is empty.
- **Area pools**: `parent_pool_name` set to parent name (e.g., `"Geleira Snowcap"`). `areas` is empty. Behave like regular `FishingPool` objects for all game mechanics.

Key insight: **areas ARE `FishingPool` objects**. Every subsystem that takes a `FishingPool` (fishing loop, perfect catch, weather, mutations) works unchanged.

### Existing field handling for areas

Areas are full `FishingPool` objects and support all existing fields. Each area reads its own values from `area.json`:

- `hidden_from_pool_selection`, `hidden_from_bestiary_until_unlocked`, `counts_for_bestiary_completion`: read from `area.json` if present, otherwise default (same as regular pools).
- `secret_entry_code`: supported on areas (allows secret areas within a pool).
- `perfect_catch`: read from `area.json` if present, otherwise inherits from parent `pool.json`, otherwise uses the global default.

## `load_pools()` Changes

When loading a pool folder:

1. Check if `areas/` subfolder exists.
2. If yes: load each sub-folder inside `areas/` (read `area.json`, load `fish/*.json`). Build each as a `FishingPool` with `parent_pool_name` set. Parent gets `areas` populated, empty `fish_profiles`, empty `rarity_weights`.
3. If no: load as today. No change.

**Important**: The current guard `if not fish_profiles: continue` (line 652 of `pesca.py`) must be relaxed for parent pools that have areas. A parent pool is valid even with empty `fish_profiles`.

## Pool Selection Flow

1. `select_pool()` shows pools as today. Parent pools (those with `areas`) appear as a single entry using parent name.
2. Player picks "Geleira Snowcap".
3. A second menu appears showing only the unlocked areas of that pool.
4. Player picks "Costa Gelada" -> returns that area's `FishingPool`.
5. If a pool has no areas, it returns immediately as today (no second menu).
6. Back button in area sub-menu returns to pool list.

### UI display

When an area is the active pool, the HUD and other UI elements show `"Geleira Snowcap - Costa Gelada"` (parent name + area name). This uses `parent_pool_name` when set, otherwise just `name`.

## Unlock Tracking

`unlocked_pools` stays a flat `Set[str]`. It now holds both pool names and area compound keys:

- Parent unlock: `"Geleira Snowcap"` -- pool shows up in pool list.
- Area unlock: `"Geleira Snowcap > Costa Gelada"` -- area is selectable within the pool.

**Content authoring constraints**:
- Pool and area names must not contain `" > "`.
- Area names must be globally unique across all pools (avoids ambiguity in `restore_selected_pool` lookups).

A pool with areas only appears in the pool list if the parent name is in `unlocked_pools`. Areas appear if their compound key is also present.

### Mission rewards

- **`unlock_pools`**: When the reward handler unlocks a pool that has areas, it adds the parent name + compound keys for all areas with `unlocked_default: true`. This expansion happens in the reward handler itself (not just in save restore), so it works for fresh unlocks mid-game.
- **New `unlock_areas`**: Unlocks specific areas by compound key. JSON schema:
  ```json
  { "type": "unlock_areas", "area_keys": ["Geleira Snowcap > Costa Gelada"] }
  ```

## Bestiary

`build_fish_bestiary_sections()` changes:

- **Skip** pools where `parent_pool_name` is set (areas don't get their own section).
- **Parent pools** (those with `areas`): merge all fish from all areas into one `FishBestiarySection` with `title = pool.name`. Completion counts all unique fish across all areas.
- **No-area pools**: unchanged.

### Hunt fish in bestiary

Hunt fish are indexed by `hunt.pool_name`. For hunts targeting a parent pool, the fish merge into the parent's bestiary section normally. For hunts targeting a specific area, the hunt `pool_name` should use the parent pool name so they appear in the unified section.

## Hunts

`HuntDefinition.pool_name` references the **parent pool name** (e.g., `"Geleira Snowcap"`), not an area name. When the player is fishing in any area of that pool, the hunt is active. Only one hunt can be active per parent pool — areas do not get independent hunts.

### Implementation: resolving area names to parent

All callers in `pesca.py` pass `selected_pool.name` when querying the hunt system. When that name is an area, `HuntManager` must resolve it to the parent pool name. A helper `resolve_hunt_pool_name(pool: FishingPool) -> str` returns `pool.parent_pool_name if pool.parent_pool_name else pool.name`.

All three `HuntManager` methods that receive a pool name must use the resolved name:

- `get_active_hunt_for_pool(pool_name)` — lookup in `_hunts_by_pool`
- `record_catch(pool_name)` — lookup in `_active_by_pool`
- `restore_state(...)` — validation of `definition.pool_name == pool_name`

`_active_by_pool` is always keyed by `definition.pool_name` (the parent name), both in `serialize_state` and in the background spawn loop. Callers must pass resolved names to match.

## Market Orders

Market orders are **per-area**, keyed by `selected_pool.name` (the area name). Each area has different fish, so each area gets its own market order. This is the natural behavior since areas ARE `FishingPool` objects.

**Save migration for market orders**: Existing saved `pool_market_orders` keyed by an old parent pool name will simply not match any area name. The order expires silently and a new one generates. No special migration needed.

## Mission Requirements

### `bestiary_pool_percent`

`_calculate_pool_percent` currently finds a pool by name and reads `pool.fish_profiles`. For parent pools (empty `fish_profiles`), it must aggregate fish from all areas instead:

- If the matched pool has `areas`: collect fish from all areas, deduplicate by name, and compute completion against that merged list.
- If the matched pool has no areas: unchanged behavior.

This ensures existing missions like `"pool_name": "Geleira Snowcap"` work correctly after a pool is converted to use areas.

### `catch_fish`

The `catch_fish` requirement type has no pool filter currently. This is unchanged and out of scope for this feature.

## Save Serialization & Migration

### `selected_pool`

When saving, `selected_pool.name` stores the area name (e.g., `"Costa Gelada"`). On restore, `restore_selected_pool` must search both top-level pools AND areas within parent pools. Top-level pools are checked first; if no match, search areas. Area names are globally unique (content authoring constraint), so there is no collision risk.

If an old save has `selected_pool: "Geleira Snowcap"` and that is now a parent (not fishable), fall back to the default pool. One-time redirect.

### `unlocked_pools`

`restore_unlocked_pools` checks if any saved name matches a parent pool that has areas. If so, expands to `"ParentName"` + `"ParentName > AreaName"` for each `unlocked_default: true` area. This handles migration of old saves that had the parent name unlocked before the conversion.

No save format version bump needed. Existing fields carry the new data naturally.

## Tests

Characterization tests to add/update:

- **`load_pools`**: test loading a pool with `areas/` subfolder; verify parent has `areas` populated, empty `fish_profiles`; verify each area has `parent_pool_name` set.
- **Bestiary**: test `build_fish_bestiary_sections` merges area fish into a single parent section; verify no duplicate sections for areas.
- **Save migration**: test `restore_selected_pool` finds areas inside parent pools; test `restore_unlocked_pools` expands parent names to area compound keys.
- **Hunts**: test that hunts matching parent pool name trigger when fishing in any area.
- **Mission requirements**: test `bestiary_pool_percent` aggregates across areas for parent pools.
