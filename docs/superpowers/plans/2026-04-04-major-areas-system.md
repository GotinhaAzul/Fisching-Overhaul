# Major Areas System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Major Areas as pool metadata and replace the flat pool selector with a grouped two-step area -> pool flow without changing pool identity, save compatibility, or folder layout.

**Architecture:** Keep `pool.name` and `pool.folder.name` as the current identity layer. Extend `FishingPool` with additive `major_area` metadata, parse it in `load_pools()`, and refactor `select_pool()` to group unlocked visible pools by major area while preserving secret pool entry codes, pagination, and both modern and fallback UI paths.

**Tech Stack:** Python 3.10+, pytest, JSON content files under `pools/`, runtime logic in `utils/pesca.py`.

---

## File Map

### Modify

- `utils/pesca.py`
  - add `major_area` to `FishingPool`
  - normalize `major_area` in `load_pools()`
  - add grouping helpers for pool selection
  - refactor `select_pool()` to area-first flow
- `tests/test_events_hunts_characterization.py`
  - add loader characterization tests for explicit and fallback `major_area`
- `tests/test_inventory_characterization.py`
  - add `select_pool()` characterization tests for grouped ordering, back navigation, and secret code handling
- `tests/test_save_system_characterization.py`
  - add compatibility characterization proving restore remains name-based
- `pools/mar/pool.json`
- `pools/lagoa/pool.json`
- `pools/rio/pool.json`
- `pools/baiadosol/pool.json`
- `pools/Grandreef/pool.json`
- `pools/farseas/pool.json`
- `pools/brinepool/pool.json`
- `pools/pantano/pool.json`
- `pools/o_jardim/pool.json`
- `pools/templomicelio/pool.json`
- `pools/crystalcove/pool.json`
- `pools/aguas_calmas/pool.json`
- `pools/caverna_luminosa/pool.json`
- `pools/celestia/pool.json`
- `pools/Vertigo/pool.json`
- `pools/thedepths/pool.json`
- `pools/desolatedeep/pool.json`
- `pools/zenite_abissal/pool.json`
- `pools/ponto_zero/pool.json`
- `pools/snowcap/pool.json`
- `pools/zona_glacial/pool.json`
- `pools/vulcaodosol/pool.json`
- `pools/rachadura_vulcanica/pool.json`
- `pools/caverna_carmesim/pool.json`
- `pools/deserto_taara/pool.json`
- `pools/a_fonte/pool.json`
- `pools/devcoffe/pool.json`

### No-change verification targets

- `utils/save_system.py`
- `utils/market.py`
- `utils/crafting.py`
- `utils/bestiary.py`

These files should be read during execution but not modified unless verification reveals an actual mismatch.

---

## Major Area Assignment Table

Use these values when tagging existing pools:

| Pool | `major_area` |
|---|---|
| `Mar Aberto` | `Costa Inicial` |
| `Lagoa Tranquila` | `Costa Inicial` |
| `Rio Correnteza` | `Costa Inicial` |
| `Baia do Sol` | `Costa Coralina` |
| `Grande Recife` | `Costa Coralina` |
| `Farseas` | `Mar Distante` |
| `Piscina de Salmoura` | `Mar Distante` |
| `Pantano Mushgrove` | `Mushgrove` |
| `O Jardim` | `Mushgrove` |
| `Templo de Micelio` | `Mushgrove` |
| `Angra Cristal` | `Cristalinas` |
| `Aguas Calmas` | `Cristalinas` |
| `Caverna Luminosa` | `Cristalinas` |
| `Celestia` | `Ceu Arcano` |
| `Vertigo` | `Profundezas` |
| `As profundezas` | `Profundezas` |
| `Profundezas Desoladas` | `Profundezas` |
| `Zenite Abissal` | `Profundezas` |
| `Ponto Zero` | `Profundezas` |
| `Geleira Snowcap` | `Snowcap` |
| `Zona Glacial` | `Snowcap` |
| `Vulcao do Sol` | `Vulcanico` |
| `Rachadura Vulcanica` | `Vulcanico` |
| `Caverna Carmesim` | `Vulcanico` |
| `Deserto Taara` | `Taara` |
| `A Fonte` | `Taara` |
| `Cafeteria` | `Dev` |

If execution reveals a user-facing naming preference conflict, update the table before touching JSON files.

---

### Task 0: Isolate The Work Before Any Commits

**Files:**
- Modify: none
- Verify: git worktree / branch state

- [ ] **Step 1: Inspect the current worktree before touching implementation**

Run:

```bash
git status --short
```

Expected: this repo may already contain unrelated tracked and untracked changes. Do not commit implementation work on top of a dirty shared worktree.

- [ ] **Step 2: Create or switch to an isolated branch/worktree for this plan**

Preferred:

```bash
git worktree add ..\\Fisching-Overhaul-major-areas -b feat/major-areas-system HEAD
```

Fallback if worktrees are unavailable:

```bash
git switch -c feat/major-areas-system
```

Expected: you now have an isolated execution surface for the plan. All later commit steps assume this isolation is already in place.

- [ ] **Step 3: Re-open the repo from the isolated location and verify the branch**

Run from the execution location:

```bash
git branch --show-current
git status --short
```

Expected: branch is `feat/major-areas-system` and the isolated worktree starts clean or only contains intentional plan-related edits.

---

### Task 1: Characterize Pool Loading With `major_area`

**Files:**
- Modify: `tests/test_events_hunts_characterization.py`
- Modify: `tests/test_save_system_characterization.py`
- Test: `tests/test_events_hunts_characterization.py`
- Test: `tests/test_save_system_characterization.py`

- [ ] **Step 1: Write the failing loader tests**

Add to `tests/test_events_hunts_characterization.py`:

```python
def test_load_pools_reads_explicit_major_area_characterization(tmp_path: Path) -> None:
    pool_dir = tmp_path / "snowcap"
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir(parents=True)

    (pool_dir / "pool.json").write_text(
        """
        {
          "name": "Geleira Snowcap",
          "major_area": "  Snowcap  ",
          "description": "Frio.",
          "rarity_chances": { "Comum": 100 }
        }
        """.strip(),
        encoding="utf-8",
    )
    (fish_dir / "truta.json").write_text(
        """
        {
          "name": "Truta Artica",
          "rarity": "Comum",
          "description": "",
          "kg_min": 1.0,
          "kg_max": 2.0,
          "base_value": 5.0,
          "sequence_len": 4,
          "reaction_time_s": 2.0
        }
        """.strip(),
        encoding="utf-8",
    )

    pools = load_pools(tmp_path)
    assert len(pools) == 1
    assert pools[0].name == "Geleira Snowcap"
    assert pools[0].major_area == "Snowcap"


def test_load_pools_falls_back_to_pool_name_when_major_area_missing_characterization(
    tmp_path: Path,
) -> None:
    pool_dir = tmp_path / "rio"
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir(parents=True)

    (pool_dir / "pool.json").write_text(
        """
        {
          "name": "Rio Correnteza",
          "description": "Correntezas rapidas.",
          "rarity_chances": { "Comum": 100 }
        }
        """.strip(),
        encoding="utf-8",
    )
    (fish_dir / "dourado.json").write_text(
        """
        {
          "name": "Dourado",
          "rarity": "Comum",
          "description": "",
          "kg_min": 1.0,
          "kg_max": 2.0,
          "base_value": 5.0,
          "sequence_len": 4,
          "reaction_time_s": 2.0
        }
        """.strip(),
        encoding="utf-8",
    )

    pools = load_pools(tmp_path)
    assert len(pools) == 1
    assert pools[0].major_area == "Rio Correnteza"
```

- [ ] **Step 2: Write the failing save-compatibility test**

Add to `tests/test_save_system_characterization.py`:

```python
def test_restore_helpers_ignore_major_area_and_remain_name_based() -> None:
    fallback_pool = SimpleNamespace(name="Lagoa Tranquila", major_area="Costa Inicial")
    other_pool = SimpleNamespace(name="Rio Correnteza", major_area="Costa Inicial")
    pools = [fallback_pool, other_pool]

    restored_selected = restore_selected_pool("Rio Correnteza", pools, fallback_pool)
    restored_unlocked = restore_unlocked_pools(
        ["Rio Correnteza", "Lagoa Tranquila"],
        pools,
        fallback_pool,
    )

    assert restored_selected.name == "Rio Correnteza"
    assert restored_selected.major_area == "Costa Inicial"
    assert restored_unlocked == ["Rio Correnteza", "Lagoa Tranquila"]
```

- [ ] **Step 3: Run the focused tests to verify they fail**

Run:

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_load_pools_reads_explicit_major_area_characterization tests/test_events_hunts_characterization.py::test_load_pools_falls_back_to_pool_name_when_major_area_missing_characterization tests/test_save_system_characterization.py::test_restore_helpers_ignore_major_area_and_remain_name_based -v
```

Expected: FAIL because `FishingPool` does not yet expose `major_area`.

- [ ] **Step 4: Commit the failing tests once they are in place**

```bash
git add tests/test_events_hunts_characterization.py tests/test_save_system_characterization.py
git commit -m "test: characterize major area pool loading and save compatibility"
```

---

### Task 2: Add `major_area` To `FishingPool` And `load_pools()`

**Files:**
- Modify: `utils/pesca.py`
- Test: `tests/test_events_hunts_characterization.py`
- Test: `tests/test_save_system_characterization.py`

- [ ] **Step 1: Add the new dataclass field**

Update `FishingPool` in `utils/pesca.py`:

```python
@dataclass
class FishingPool:
    name: str
    fish_profiles: List[FishProfile]
    folder: Path
    description: str
    major_area: str
    rarity_weights: Dict[str, int]
    unlocked_default: bool = False
    hidden_from_pool_selection: bool = False
    hidden_from_bestiary_until_unlocked: bool = False
    counts_for_bestiary_completion: bool = True
    secret_entry_code: str = ""
    perfect_catch: PerfectCatchConfig = field(default_factory=PerfectCatchConfig)
```

- [ ] **Step 2: Add a normalization helper**

Insert near the other small normalization helpers in `utils/pesca.py`:

```python
def _normalize_major_area(raw_value: object, pool_name: str) -> str:
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if normalized:
            return normalized
    return pool_name
```

- [ ] **Step 3: Populate `major_area` in `load_pools()`**

Update the append block in `load_pools()`:

```python
        pool_name = data.get("name", pool_dir.name)
        if not isinstance(pool_name, str) or not pool_name:
            pool_name = pool_dir.name
        major_area = _normalize_major_area(data.get("major_area"), pool_name)

        pools.append(
            FishingPool(
                name=pool_name,
                fish_profiles=fish_profiles,
                folder=pool_dir,
                description=data.get("description", ""),
                major_area=major_area,
                rarity_weights=rarity_weights,
                unlocked_default=bool(data.get("unlocked_default", False)),
                hidden_from_pool_selection=hidden_from_pool_selection,
                hidden_from_bestiary_until_unlocked=hidden_from_bestiary_until_unlocked,
                counts_for_bestiary_completion=counts_for_bestiary_completion,
                secret_entry_code=secret_entry_code,
                perfect_catch=pool_perfect_catch,
            )
        )
```

- [ ] **Step 4: Update any direct `FishingPool(...)` construction in tests that now needs `major_area`**

For example in `tests/test_devtools_characterization.py`:

```python
    return FishingPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa_tranquila"),
        description="",
        major_area="Costa Inicial",
        rarity_weights={"Comum": 1},
    )
```

Apply the same fix to any other direct instantiations across `tests/`.

- [ ] **Step 5: Run the focused tests to verify they pass**

Run:

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_load_pools_reads_explicit_major_area_characterization tests/test_events_hunts_characterization.py::test_load_pools_falls_back_to_pool_name_when_major_area_missing_characterization tests/test_save_system_characterization.py::test_restore_helpers_ignore_major_area_and_remain_name_based tests/test_devtools_characterization.py -v
```

Expected: PASS

- [ ] **Step 6: Run the full suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit the loader/model change**

```bash
git add utils/pesca.py tests/test_devtools_characterization.py tests/test_events_hunts_characterization.py tests/test_save_system_characterization.py
git commit -m "pools: add major area metadata to pool loading"
```

---

### Task 3: Characterize The Grouped Pool Selection Flow

**Files:**
- Modify: `tests/test_inventory_characterization.py`
- Test: `tests/test_inventory_characterization.py`

- [ ] **Step 1: Add helpers for grouped pool menu tests**

Add near the top of `tests/test_inventory_characterization.py`:

```python
from pathlib import Path


def _pool(
    name: str,
    *,
    major_area: str,
    hidden_from_pool_selection: bool = False,
    secret_entry_code: str = "",
) -> pesca.FishingPool:
    return pesca.FishingPool(
        name=name,
        fish_profiles=[],
        folder=Path(name.casefold().replace(" ", "_")),
        description="",
        major_area=major_area,
        rarity_weights={"Comum": 1},
        hidden_from_pool_selection=hidden_from_pool_selection,
        secret_entry_code=secret_entry_code,
    )
```

- [ ] **Step 2: Write the failing grouped-order test**

Add to `tests/test_inventory_characterization.py`:

```python
def test_select_pool_groups_by_major_area_in_modern_ui_characterization(monkeypatch) -> None:
    pools = [
        _pool("Zona Glacial", major_area="Snowcap"),
        _pool("Mar Aberto", major_area="Costa Inicial"),
        _pool("Lagoa Tranquila", major_area="Costa Inicial"),
        _pool("Geleira Snowcap", major_area="Snowcap"),
    ]
    feeder = _ChoiceFeeder(["1", "2"])
    captured_panels: list[dict[str, object]] = []

    monkeypatch.setattr(pesca, "use_modern_ui", lambda: True)
    monkeypatch.setattr(pesca, "clear_screen", lambda: None)
    monkeypatch.setattr(pesca, "read_menu_choice", feeder)
    monkeypatch.setattr(
        pesca,
        "print_menu_panel",
        lambda title, **kwargs: captured_panels.append({"title": title, **kwargs}),
    )

    selected = pesca.select_pool(pools, {"Mar Aberto", "Lagoa Tranquila", "Geleira Snowcap", "Zona Glacial"})

    assert selected.name == "Mar Aberto"
    area_panel = captured_panels[0]
    area_labels = [option.label for option in area_panel["options"]]
    # Areas are sorted alphabetically: "Costa Inicial" < "Snowcap"
    assert area_labels[:2] == ["Costa Inicial", "Snowcap"]

    pool_panel = captured_panels[1]
    pool_labels = [option.label for option in pool_panel["options"]]
    # Pools within an area are sorted alphabetically: "Lagoa Tranquila" < "Mar Aberto"
    assert pool_labels[:2] == ["Lagoa Tranquila", "Mar Aberto"]
```

- [ ] **Step 3: Write the failing back-navigation and secret-code test**

Add to `tests/test_inventory_characterization.py`:

```python
def test_select_pool_allows_back_navigation_and_secret_code_characterization(monkeypatch) -> None:
    pools = [
        _pool("Mar Aberto", major_area="Costa Inicial"),
        _pool("Lagoa Tranquila", major_area="Costa Inicial"),
        _pool(
            "Cafeteria",
            major_area="Dev",
            hidden_from_pool_selection=True,
            secret_entry_code="devcoffe",
        ),
    ]
    feeder = _ChoiceFeeder(["1", "0", "devcoffe"])
    captured_panels: list[dict[str, object]] = []
    unlocked = {"Mar Aberto", "Lagoa Tranquila"}

    monkeypatch.setattr(pesca, "use_modern_ui", lambda: True)
    monkeypatch.setattr(pesca, "clear_screen", lambda: None)
    monkeypatch.setattr(pesca, "read_menu_choice", feeder)
    monkeypatch.setattr(
        pesca,
        "print_menu_panel",
        lambda title, **kwargs: captured_panels.append({"title": title, **kwargs}),
    )

    selected = pesca.select_pool(pools, unlocked)

    assert selected.name == "Cafeteria"
    assert "Cafeteria" in unlocked
    assert captured_panels[0]["title"] == "AREAS"
    assert captured_panels[1]["title"] == "POOLS"
    assert captured_panels[2]["title"] == "AREAS"
```

- [ ] **Step 4: Write the failing fallback text UI test**

Add to `tests/test_inventory_characterization.py`:

```python
def test_select_pool_groups_by_major_area_in_fallback_ui_characterization(monkeypatch) -> None:
    pools = [
        _pool("Zona Glacial", major_area="Snowcap"),
        _pool("Mar Aberto", major_area="Costa Inicial"),
        _pool("Lagoa Tranquila", major_area="Costa Inicial"),
    ]
    feeder = _ChoiceFeeder(["1", "0", "2", "1"])
    printed: list[str] = []

    monkeypatch.setattr(pesca, "use_modern_ui", lambda: False)
    monkeypatch.setattr(pesca, "clear_screen", lambda: None)
    monkeypatch.setattr(pesca, "read_menu_choice", feeder)
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )

    selected = pesca.select_pool(
        pools,
        {"Mar Aberto", "Lagoa Tranquila", "Zona Glacial"},
    )

    assert selected.name == "Zona Glacial"
    rendered = "\n".join(printed)
    assert "1. Costa Inicial (2 pools)" in rendered
    assert "2. Snowcap (1 pools)" in rendered
    assert "Pools em Costa Inicial:" in rendered
    assert "0. Voltar" in rendered
    assert "Pools em Snowcap:" in rendered
```

- [ ] **Step 5: Run the focused tests to verify they fail**

Run:

```bash
python -m pytest tests/test_inventory_characterization.py::test_select_pool_groups_by_major_area_in_modern_ui_characterization tests/test_inventory_characterization.py::test_select_pool_allows_back_navigation_and_secret_code_characterization tests/test_inventory_characterization.py::test_select_pool_groups_by_major_area_in_fallback_ui_characterization -v
```

Expected: FAIL because `select_pool()` is still flat.

- [ ] **Step 6: Commit the failing interaction tests**

```bash
git add tests/test_inventory_characterization.py
git commit -m "test: characterize grouped major area pool selection"
```

---

### Task 4: Refactor `select_pool()` To Area -> Pool Navigation

**Files:**
- Modify: `utils/pesca.py`
- Test: `tests/test_inventory_characterization.py`

- [ ] **Step 1: Add helpers to group visible pools**

Insert near `select_pool()` in `utils/pesca.py`:

```python
def _available_pools_by_major_area(
    pools: List[FishingPool],
    unlocked_pools: set[str],
) -> Dict[str, List[FishingPool]]:
    grouped: Dict[str, List[FishingPool]] = {}
    for pool in pools:
        if pool.name not in unlocked_pools or pool.hidden_from_pool_selection:
            continue
        grouped.setdefault(pool.major_area, []).append(pool)

    return {
        major_area: sorted(area_pools, key=lambda pool: pool.name.casefold())
        for major_area, area_pools in sorted(grouped.items(), key=lambda item: item[0].casefold())
    }
```

- [ ] **Step 2: Add a reusable secret pool lookup helper**

```python
def _secret_pools_by_code(pools: List[FishingPool]) -> Dict[str, FishingPool]:
    return {
        pool.secret_entry_code: pool
        for pool in pools
        if pool.secret_entry_code
    }
```

- [ ] **Step 3: Replace the flat modern UI flow with two loops**

Use this structure inside `select_pool()`:

```python
def select_pool(pools: List[FishingPool], unlocked_pools: set[str]) -> FishingPool:
    grouped_pools = _available_pools_by_major_area(pools, unlocked_pools)
    secret_pools_by_code = _secret_pools_by_code(pools)

    if not grouped_pools and not secret_pools_by_code:
        raise RuntimeError("Nenhuma pool desbloqueada.")

    area_names = list(grouped_pools.keys())
    area_page_size = 12
    pool_page_size = 12
    area_page = 0

    if use_modern_ui():
        while True:
            clear_screen()
            area_slice = get_page_slice(len(area_names), area_page, area_page_size)
            area_page = area_slice.page
            areas_on_page = area_names[area_slice.start:area_slice.end]

            area_options = [
                MenuOption(str(idx), area_name, f"{len(grouped_pools[area_name])} pools")
                for idx, area_name in enumerate(areas_on_page, start=1)
            ]
            if area_slice.total_pages > 1:
                area_options.extend(
                    [
                        MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina", enabled=area_page < area_slice.total_pages - 1),
                        MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior", enabled=area_page > 0),
                    ]
                )

            print_menu_panel(
                "AREAS",
                subtitle="Escolha a grande area",
                header_lines=[f"Disponiveis: {len(area_names)}"],
                options=area_options,
                prompt="Digite o numero da area:",
                show_badge=False,
            )
            choice = read_menu_choice(
                "> ",
                instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if area_slice.total_pages > 1 else set(),
            ).lower()

            secret_pool = secret_pools_by_code.get(choice.casefold())
            if secret_pool:
                unlocked_pools.add(secret_pool.name)
                return secret_pool

            area_page, moved = apply_page_hotkey(choice, area_page, area_slice.total_pages)
            if moved:
                continue
            if not choice.isdigit():
                print("Entrada invalida. Digite apenas o numero da area.")
                continue

            idx = int(choice)
            if not 1 <= idx <= len(areas_on_page):
                print("Numero fora do intervalo. Tente novamente.")
                continue

            selected_area = areas_on_page[idx - 1]
            pool_page = 0
            while True:
                clear_screen()
                area_pools = grouped_pools[selected_area]
                pool_slice = get_page_slice(len(area_pools), pool_page, pool_page_size)
                pool_page = pool_slice.page
                pools_on_page = area_pools[pool_slice.start:pool_slice.end]

                pool_options = [
                    MenuOption(str(pidx), pool.name, "Desbloqueada")
                    for pidx, pool in enumerate(pools_on_page, start=1)
                ]
                if pool_slice.total_pages > 1:
                    pool_options.extend(
                        [
                            MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina", enabled=pool_page < pool_slice.total_pages - 1),
                            MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior", enabled=pool_page > 0),
                        ]
                    )
                pool_options.append(MenuOption("0", "Voltar", f"Retorna para {selected_area}"))

                print_menu_panel(
                    "POOLS",
                    subtitle=selected_area,
                    header_lines=[f"Disponiveis: {len(area_pools)}"],
                    options=pool_options,
                    prompt="Digite o numero da pool:",
                    show_badge=False,
                )
                choice = read_menu_choice(
                    "> ",
                    instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if pool_slice.total_pages > 1 else set(),
                ).lower()

                secret_pool = secret_pools_by_code.get(choice.casefold())
                if secret_pool:
                    unlocked_pools.add(secret_pool.name)
                    return secret_pool
                if choice == "0":
                    break

                pool_page, moved = apply_page_hotkey(choice, pool_page, pool_slice.total_pages)
                if moved:
                    continue
                if not choice.isdigit():
                    print("Entrada invalida. Digite apenas o numero da pool.")
                    continue

                pidx = int(choice)
                if 1 <= pidx <= len(pools_on_page):
                    return pools_on_page[pidx - 1]

                print("Numero fora do intervalo. Tente novamente.")
```

- [ ] **Step 4: Mirror the same structure in the fallback text UI**

Use the same control flow as the modern path, but replace panels with plain `print()` output:

```python
    while True:
        clear_screen()
        area_slice = get_page_slice(len(area_names), area_page, area_page_size)
        area_page = area_slice.page
        areas_on_page = area_names[area_slice.start:area_slice.end]

        print("Escolha uma grande area:")
        for idx, area_name in enumerate(areas_on_page, start=1):
            print(f"{idx}. {area_name} ({len(grouped_pools[area_name])} pools)")
        if area_slice.total_pages > 1:
            print(f"{PAGE_NEXT_KEY.upper()}. Proxima pagina ({area_page + 1}/{area_slice.total_pages})")
            print(f"{PAGE_PREV_KEY.upper()}. Pagina anterior ({area_page + 1}/{area_slice.total_pages})")

        choice = read_menu_choice(
            "Digite o numero da area: ",
            instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if area_slice.total_pages > 1 else set(),
        ).lower()
        if not choice:
            print("Entrada invalida. Digite apenas o numero da area.")
            continue

        secret_pool = secret_pools_by_code.get(choice.casefold())
        if secret_pool:
            unlocked_pools.add(secret_pool.name)
            return secret_pool

        area_page, moved = apply_page_hotkey(choice, area_page, area_slice.total_pages)
        if moved:
            continue

        if not choice.isdigit():
            print("Entrada invalida. Digite apenas o numero da area.")
            continue

        idx = int(choice)
        if not 1 <= idx <= len(areas_on_page):
            print("Numero fora do intervalo. Tente novamente.")
            continue

        selected_area = areas_on_page[idx - 1]
        pool_page = 0
        while True:
            clear_screen()
            area_pools = grouped_pools[selected_area]
            pool_slice = get_page_slice(len(area_pools), pool_page, pool_page_size)
            pool_page = pool_slice.page
            pools_on_page = area_pools[pool_slice.start:pool_slice.end]

            print(f"Pools em {selected_area}:")
            for pidx, pool in enumerate(pools_on_page, start=1):
                print(f"{pidx}. {pool.name}")
            if pool_slice.total_pages > 1:
                print(f"{PAGE_NEXT_KEY.upper()}. Proxima pagina ({pool_page + 1}/{pool_slice.total_pages})")
                print(f"{PAGE_PREV_KEY.upper()}. Pagina anterior ({pool_page + 1}/{pool_slice.total_pages})")
            print("0. Voltar")

            choice = read_menu_choice(
                "Digite o numero da pool: ",
                instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if pool_slice.total_pages > 1 else set(),
            ).lower()
            if not choice:
                print("Entrada invalida. Digite apenas o numero da pool.")
                continue

            secret_pool = secret_pools_by_code.get(choice.casefold())
            if secret_pool:
                unlocked_pools.add(secret_pool.name)
                return secret_pool
            if choice == "0":
                break

            pool_page, moved = apply_page_hotkey(choice, pool_page, pool_slice.total_pages)
            if moved:
                continue

            if not choice.isdigit():
                print("Entrada invalida. Digite apenas o numero da pool.")
                continue

            pidx = int(choice)
            if 1 <= pidx <= len(pools_on_page):
                return pools_on_page[pidx - 1]

            print("Numero fora do intervalo. Tente novamente.")
```

Do not leave the fallback text path flat; keep behavior aligned with the modern path.

- [ ] **Step 5: Run the focused selection tests**

Run:

```bash
python -m pytest tests/test_inventory_characterization.py::test_select_pool_groups_by_major_area_in_modern_ui_characterization tests/test_inventory_characterization.py::test_select_pool_allows_back_navigation_and_secret_code_characterization tests/test_inventory_characterization.py::test_select_pool_groups_by_major_area_in_fallback_ui_characterization -v
```

Expected: PASS

- [ ] **Step 6: Run related regression tests**

Run:

```bash
python -m pytest tests/test_inventory_characterization.py tests/test_devtools_characterization.py tests/test_bestiary_and_menu_characterization.py -q
```

Expected: PASS

- [ ] **Step 7: Commit the menu refactor**

```bash
git add utils/pesca.py tests/test_inventory_characterization.py
git commit -m "ui: group pool selection by major area"
```

---

### Task 5: Tag Existing Pools With `major_area`

**Files:**
- Modify: every `pools/*/pool.json` listed in the file map
- Test: `tests/test_events_hunts_characterization.py`

- [ ] **Step 1: Validate all pool JSON files before editing**

Read every `pools/*/pool.json` file and confirm each one:
- parses as valid JSON
- has a `"name"` key matching the assignment table
- does not already have a `"major_area"` key (to avoid double-tagging)

If any file has an unexpected structure, stop and fix it before proceeding with the tagging pass.

- [ ] **Step 2: Update starter pools**

Apply these edits:

`pools/mar/pool.json`
```json
{
  "name": "Mar Aberto",
  "major_area": "Costa Inicial",
  "description": "Águas abertas com peixes mais ágeis.",
  "unlocked_default": true,
  "rarity_chances": {
    "Comum": 40,
    "Incomum": 30,
    "Raro": 18,
    "Epico": 9,
    "Lendario": 3
  }
}
```

`pools/lagoa/pool.json`
```json
{
  "name": "Lagoa Tranquila",
  "major_area": "Costa Inicial",
  "description": "Uma lagoa calma com peixes de água doce.",
  "unlocked_default": true,
  "rarity_chances": {
    "Comum": 65,
    "Incomum": 20,
    "Raro": 10,
    "Epico": 4,
    "Lendario": 1
  }
}
```

`pools/rio/pool.json`
```json
{
  "name": "Rio Correnteza",
  "major_area": "Costa Inicial",
  "description": "Correntezas rápidas com peixes fortes.",
  "rarity_chances": {
    "Comum": 60,
    "Incomum": 20,
    "Raro": 12,
    "Epico": 6,
    "Lendario": 2
  }
}
```

- [ ] **Step 3: Update the rest of the pool JSON files using the assignment table**

For each remaining pool JSON, insert the `major_area` line immediately after `name`.

Example pattern:

```json
{
  "name": "Geleira Snowcap",
  "major_area": "Snowcap",
  "description": "Frio...! Muuuito frioo!.",
  "unlocked_default": false,
  "rarity_chances": {
    "Comum": 49,
    "Incomum": 35,
    "Raro": 16,
    "Epico": 6,
    "Lendario": 1,
    "Mitico": 0
  }
}
```

Do this for every pool in the table, including hidden/dev pools.

- [ ] **Step 4: Add a real-repo characterization to lock in tagged groups**

Add to `tests/test_events_hunts_characterization.py`:

```python
def test_real_repo_major_area_assignments_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    pools_by_name = {pool.name: pool for pool in load_pools(repo_root / "pools")}

    assert pools_by_name["Mar Aberto"].major_area == "Costa Inicial"
    assert pools_by_name["Lagoa Tranquila"].major_area == "Costa Inicial"
    assert pools_by_name["Rio Correnteza"].major_area == "Costa Inicial"
    assert pools_by_name["Geleira Snowcap"].major_area == "Snowcap"
    assert pools_by_name["Zona Glacial"].major_area == "Snowcap"
    assert pools_by_name["Deserto Taara"].major_area == "Taara"
    assert pools_by_name["A Fonte"].major_area == "Taara"
    assert pools_by_name["Farseas"].major_area == "Mar Distante"
    assert pools_by_name["Farseas"].hidden_from_pool_selection is True
    assert pools_by_name["Cafeteria"].major_area == "Dev"
    assert pools_by_name["Cafeteria"].hidden_from_pool_selection is True
```

- [ ] **Step 5: Run the pool-loading test slice**

Run:

```bash
python -m pytest tests/test_events_hunts_characterization.py -q
```

Expected: PASS

- [ ] **Step 6: Commit the content tagging pass**

```bash
git add pools tests/test_events_hunts_characterization.py
git commit -m "content: tag pools with major areas"
```

---

### Task 6: Final Verification And Compatibility Check

**Files:**
- Modify: none expected
- Test: `tests/test_events_hunts_characterization.py`
- Test: `tests/test_inventory_characterization.py`
- Test: `tests/test_save_system_characterization.py`

- [ ] **Step 1: Run the targeted feature suite**

Run:

```bash
python -m pytest tests/test_events_hunts_characterization.py tests/test_inventory_characterization.py tests/test_save_system_characterization.py tests/test_devtools_characterization.py -q
```

Expected: PASS

- [ ] **Step 2: Run the full project suite**

Run:

```bash
python -m pytest -q
```

Expected: PASS

- [ ] **Step 3: Manual smoke-check the pool selection flow**

Run:

```bash
python start_game_dev.py
```

Expected manual checks:
- open the pool selector from the main menu
- confirm the first screen shows major areas instead of a flat pool list
- confirm selecting `Snowcap` shows `Geleira Snowcap` and `Zona Glacial`
- confirm `0` returns from the pool list to the area list
- confirm an existing secret code still unlocks and selects its hidden pool

- [ ] **Step 4: Stop after verification and hand off for review**

Expected: no extra verification-only commit is needed here. The implementation should already be captured by the earlier scoped commits.

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|---|---|
| Add `major_area` to `FishingPool` | Task 2 |
| Parse `major_area` in `load_pools()` | Task 2 |
| Fallback to pool name when missing | Task 1, Task 2 |
| Keep pool identity name-based | Task 1, Task 6 |
| Group `select_pool()` by major area | Task 3, Task 4 |
| Preserve secret pool access | Task 3, Task 4 |
| Preserve pagination and both UI modes | Task 3, Task 4 |
| Tag existing pool JSON files | Task 5 |
| Add characterization coverage | Tasks 1, 3, 5 |

**Gaps found:** none.

**Placeholder scan:** no TBDs, TODOs, or “implement later” placeholders remain.

**Type consistency checks:**

- `FishingPool` uses `fish_profiles`, not `fish`; all snippets use `fish_profiles`.
- Save restore tests remain `name`-based and do not require changes in `utils/save_system.py`.
- Direct `FishingPool(...)` constructions in tests must be updated everywhere once `major_area` becomes required.
- Hidden pools such as `Farseas` and `Cafeteria` are tagged and explicitly covered in repo-level characterization.
