from __future__ import annotations

from dataclasses import dataclass
from utils.inventory import InventoryEntry, format_inventory_entry
from pathlib import Path

from utils.pesca import FishingPool, select_pool
from utils.storage_ui import render_storage


@dataclass
class _MenuChoiceFeeder:
    values: list[str]

    def __post_init__(self) -> None:
        self._index = 0
        self.calls = 0

    def __call__(self, _prompt: str = "> ", *, instant_keys=()) -> str:
        del instant_keys
        self.calls += 1
        if self._index >= len(self.values):
            raise AssertionError("Unexpected extra menu prompt.")
        value = self.values[self._index]
        self._index += 1
        return value


def _make_pool(
    name: str,
    *,
    major_area: str | None,
    hidden_from_pool_selection: bool = False,
    secret_entry_code: str = "",
) -> FishingPool:
    return FishingPool(
        name=name,
        major_area=major_area,
        fish_profiles=[],
        folder=Path(name.lower().replace(" ", "_")),
        description="",
        rarity_weights={"Comum": 1},
        hidden_from_pool_selection=hidden_from_pool_selection,
        secret_entry_code=secret_entry_code,
    )


def test_format_inventory_entry_uses_custom_shiny_display_characterization() -> None:
    entry = InventoryEntry(
        name="Tilapia",
        rarity="Comum",
        kg=2.0,
        base_value=10.0,
        is_shiny=True,
    )

    rendered = format_inventory_entry(
        1,
        entry,
        shiny_label_text="Shimmer",
        shiny_color="#00FFAA",
    )

    assert "Shimmer" in rendered
    assert "#00FFAA" in rendered
    assert "✦ Shiny" not in rendered


def test_render_storage_uses_custom_shiny_display_characterization(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "utils.storage_ui.print_menu_panel",
        lambda title, **kwargs: captured.update({"title": title, **kwargs}),
    )

    render_storage(
        [
            InventoryEntry(
                name="Dourado",
                rarity="Epico",
                kg=5.0,
                base_value=40.0,
                is_shiny=True,
            )
        ],
        shiny_label_text="Shimmer",
        shiny_color="#00FFAA",
    )

    header_lines = captured["header_lines"]
    assert isinstance(header_lines, list)
    rendered_lines = "\n".join(str(line) for line in header_lines)
    assert "Shimmer" in rendered_lines
    assert "#00FFAA" in rendered_lines


def test_select_pool_modern_groups_and_sorts_characterization(monkeypatch) -> None:
    pools = [
        _make_pool("Zeta Pool", major_area="beta"),
        _make_pool("Bravo Pool", major_area="Alpha"),
        _make_pool("alpha Pool", major_area="alpha"),
    ]
    unlocked_pools = {pool.name for pool in pools}
    captured_panels: list[dict[str, object]] = []
    feeder = _MenuChoiceFeeder(["1", "1"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: True)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr(
        "utils.pesca.print_menu_panel",
        lambda *args, **kwargs: captured_panels.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    assert selected.name == "alpha Pool"
    assert [panel["args"][0] for panel in captured_panels[:2]] == ["AREAS", "POOLS"]
    assert [option.label for option in captured_panels[0]["options"]] == [
        "Alpha",
        "beta",
    ]
    assert captured_panels[0]["options"][0].hint == "2 pool(s)"
    assert [option.label for option in captured_panels[1]["options"]] == [
        "alpha Pool",
        "Bravo Pool",
        "Voltar",
    ]


def test_select_pool_modern_back_navigation_characterization(monkeypatch) -> None:
    pools = [
        _make_pool("Zeta Pool", major_area="beta"),
        _make_pool("Bravo Pool", major_area="Alpha"),
        _make_pool("alpha Pool", major_area="Alpha"),
    ]
    unlocked_pools = {pool.name for pool in pools}
    captured_panels: list[dict[str, object]] = []
    feeder = _MenuChoiceFeeder(["1", "0", "2", "1"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: True)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr(
        "utils.pesca.print_menu_panel",
        lambda *args, **kwargs: captured_panels.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    assert selected.name == "Zeta Pool"
    assert [panel["args"][0] for panel in captured_panels[:4]] == [
        "AREAS",
        "POOLS",
        "AREAS",
        "POOLS",
    ]


def test_select_pool_modern_secret_code_unlocks_from_area_characterization(
    monkeypatch,
) -> None:
    secret_pool = _make_pool(
        "Hidden Cove",
        major_area="Secret Coast",
        hidden_from_pool_selection=True,
        secret_entry_code="moon",
    )
    visible_pool = _make_pool("Visible Pool", major_area="Open Sea")
    pools = [secret_pool, visible_pool]
    unlocked_pools = {visible_pool.name}
    captured_panels: list[dict[str, object]] = []
    feeder = _MenuChoiceFeeder(["moon"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: True)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr(
        "utils.pesca.print_menu_panel",
        lambda *args, **kwargs: captured_panels.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    assert selected.name == "Hidden Cove"
    assert "Hidden Cove" in unlocked_pools
    assert [panel["args"][0] for panel in captured_panels] == ["AREAS"]


def test_select_pool_modern_secret_code_unlocks_from_pool_characterization(
    monkeypatch,
) -> None:
    secret_pool = _make_pool(
        "Hidden Cove",
        major_area="Secret Coast",
        hidden_from_pool_selection=True,
        secret_entry_code="moon",
    )
    visible_pool = _make_pool("Visible Pool", major_area="Open Sea")
    pools = [secret_pool, visible_pool]
    unlocked_pools = {visible_pool.name}
    captured_panels: list[dict[str, object]] = []
    feeder = _MenuChoiceFeeder(["1", "moon"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: True)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr(
        "utils.pesca.print_menu_panel",
        lambda *args, **kwargs: captured_panels.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    assert selected.name == "Hidden Cove"
    assert "Hidden Cove" in unlocked_pools
    assert [panel["args"][0] for panel in captured_panels[:2]] == ["AREAS", "POOLS"]


def test_select_pool_modern_shows_standalone_pools_alongside_areas_characterization(
    monkeypatch,
) -> None:
    pools = [
        _make_pool("Mar Aberto", major_area=None),
        _make_pool("Rio Correnteza", major_area="Costa Inicial"),
    ]
    unlocked_pools = {pool.name for pool in pools}
    captured_panels: list[dict[str, object]] = []
    feeder = _MenuChoiceFeeder(["2"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: True)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr(
        "utils.pesca.print_menu_panel",
        lambda *args, **kwargs: captured_panels.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    assert selected.name == "Mar Aberto"
    assert [panel["args"][0] for panel in captured_panels] == ["AREAS"]
    assert [option.label for option in captured_panels[0]["options"]] == [
        "Costa Inicial",
        "Mar Aberto",
    ]
    assert [option.hint for option in captured_panels[0]["options"]] == [
        "1 pool(s)",
        "Pool desbloqueada",
    ]


def test_select_pool_fallback_groups_and_back_navigation_characterization(
    monkeypatch,
    capsys,
) -> None:
    pools = [
        _make_pool("Zeta Pool", major_area="beta"),
        _make_pool("Bravo Pool", major_area="Alpha"),
        _make_pool("alpha Pool", major_area="Alpha"),
    ]
    unlocked_pools = {pool.name for pool in pools}
    feeder = _MenuChoiceFeeder(["1", "0", "2", "1"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: False)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    captured = capsys.readouterr().out
    assert selected.name == "Zeta Pool"
    assert captured.index("=== AREAS ===") < captured.index("1. Alpha (2 pool(s))")
    assert captured.index("1. Alpha (2 pool(s))") < captured.index("2. beta (1 pool(s))")
    assert captured.index("=== POOLS ===") < captured.index("1. alpha Pool")
    assert captured.index("1. alpha Pool") < captured.index("2. Bravo Pool")
    first_pool_screen = captured.index("=== POOLS ===")
    assert "0. Voltar" not in captured[:first_pool_screen]
    assert captured.count("0. Voltar") == 2


def test_select_pool_fallback_merges_case_variants_characterization(
    monkeypatch,
    capsys,
) -> None:
    pools = [
        _make_pool("Lower Pool", major_area="alpha"),
        _make_pool("Upper Pool", major_area="Alpha"),
        _make_pool("Other Pool", major_area="beta"),
    ]
    unlocked_pools = {pool.name for pool in pools}
    feeder = _MenuChoiceFeeder(["1", "1"])
    captured_panels: list[dict[str, object]] = []

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: False)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr(
        "utils.pesca.print_menu_panel",
        lambda *args, **kwargs: captured_panels.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    captured = capsys.readouterr().out
    assert selected.name == "Lower Pool"
    assert captured_panels == []
    assert captured.count("=== AREAS ===") == 1
    assert captured.count("1. Alpha (2 pool(s))") == 1
    assert "alpha (1 pool(s))" not in captured
    assert captured.count("2. beta (1 pool(s))") == 1


def test_select_pool_fallback_shows_standalone_pools_alongside_areas_characterization(
    monkeypatch,
    capsys,
) -> None:
    pools = [
        _make_pool("Mar Aberto", major_area=None),
        _make_pool("Rio Correnteza", major_area="Costa Inicial"),
    ]
    unlocked_pools = {pool.name for pool in pools}
    feeder = _MenuChoiceFeeder(["2"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: False)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    captured = capsys.readouterr().out
    assert selected.name == "Mar Aberto"
    assert "1. Costa Inicial (1 pool(s))" in captured
    assert "2. Mar Aberto" in captured
    assert "2. Mar Aberto (1 pool(s))" not in captured
    assert "=== POOLS ===" not in captured


def test_select_pool_fallback_secret_code_unlocks_characterization(monkeypatch) -> None:
    secret_pool = _make_pool(
        "Hidden Cove",
        major_area="Secret Coast",
        hidden_from_pool_selection=True,
        secret_entry_code="moon",
    )
    visible_pool = _make_pool("Visible Pool", major_area="Open Sea")
    pools = [secret_pool, visible_pool]
    unlocked_pools = {visible_pool.name}
    feeder = _MenuChoiceFeeder(["moon"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: False)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr("utils.pesca.read_menu_choice", feeder)

    selected = select_pool(pools, unlocked_pools)

    assert selected.name == "Hidden Cove"
    assert "Hidden Cove" in unlocked_pools
