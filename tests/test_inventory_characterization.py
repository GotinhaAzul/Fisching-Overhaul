from __future__ import annotations

from typing import Iterator

import utils.pesca as pesca
from utils.crafting import CraftingProgress
from utils.inventory import RARITY_COLORS, InventoryEntry, format_inventory_entry
from utils.cosmetics import create_default_cosmetics_state
from utils.rod_upgrades import RodUpgradeState
from utils.rods import Rod
from utils.storage_ui import render_storage


class _ChoiceFeeder:
    def __init__(self, values: list[str]) -> None:
        self._iter: Iterator[str] = iter(values)

    def __call__(self, _prompt: str, *, instant_keys=()) -> str:
        del instant_keys
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise AssertionError("Unexpected extra choice prompt.") from exc


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


def test_format_inventory_entry_closes_rarity_color_before_fish_name() -> None:
    entry = InventoryEntry(
        name="Dourado",
        rarity="Epico",
        kg=5.0,
        base_value=40.0,
    )

    rendered = format_inventory_entry(1, entry)

    assert f"[{RARITY_COLORS['Epico']}]\\[Epico][/]" in rendered


def test_show_inventory_modern_hides_rod_abilities_from_header_and_options(
    monkeypatch,
) -> None:
    equipped_rod = Rod(
        name="Perforatio",
        luck=0.0,
        kg_max=100.0,
        control=0.0,
        description="Perfura a captura.",
        price=0.0,
        can_pierce=True,
        pierce_chance=0.3,
    )
    spare_rod = Rod(
        name="Midas",
        luck=0.0,
        kg_max=100.0,
        control=0.0,
        description="Rouba valor.",
        price=0.0,
        can_greed=True,
        greed_chance=0.12,
    )
    captured_panels: list[dict[str, object]] = []
    feeder = _ChoiceFeeder(["1", "1", "0"])

    monkeypatch.setattr(pesca, "use_modern_ui", lambda: True)
    monkeypatch.setattr(pesca, "clear_screen", lambda: None)
    monkeypatch.setattr(pesca, "render_inventory", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pesca,
        "print_menu_panel",
        lambda title, **kwargs: captured_panels.append({"title": title, **kwargs}),
    )
    monkeypatch.setattr(pesca, "read_menu_choice", feeder)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")

    pesca.show_inventory(
        inventory=[],
        storage=[],
        owned_rods=[equipped_rod, spare_rod],
        equipped_rod=equipped_rod,
        rod_upgrade_state=RodUpgradeState(),
        bait_inventory={},
        bait_by_id={},
        equipped_bait_id=None,
        cosmetics_state=create_default_cosmetics_state(),
    )

    inventory_panel = next(panel for panel in captured_panels if panel["title"] == "INVENTARIO")
    header_lines = inventory_panel["header_lines"]
    assert isinstance(header_lines, list)
    assert all("Habilidades:" not in str(line) for line in header_lines)

    rod_panel = next(panel for panel in captured_panels if panel["title"] == "EQUIPAR VARA")
    options = rod_panel["options"]
    rendered_hints = "\n".join(getattr(option, "hint", "") for option in options)
    assert "Habilidades:" not in rendered_hints


def test_finalize_market_appraise_updates_shiny_discovery_and_progress() -> None:
    entry = InventoryEntry(
        name="Tilapia",
        rarity="Comum",
        kg=2.0,
        base_value=10.0,
        is_shiny=True,
        mutation_name="Albino",
    )
    crafting_progress = CraftingProgress()
    discovered_shiny_fish: set[str] = set()
    dirty_markers: list[str] = []

    notes = pesca._finalize_market_appraise(
        entry,
        crafting_progress,
        lambda: ["Nova receita desbloqueada: Vara Cristal"],
        discovered_shiny_fish=discovered_shiny_fish,
        mark_inventory_counts_dirty=lambda: dirty_markers.append("dirty"),
    )

    assert discovered_shiny_fish == {"Tilapia"}
    assert crafting_progress.find_fish_counts_by_name == {"Tilapia": 1}
    assert crafting_progress.find_mutation_counts_by_name == {"Albino": 1}
    assert dirty_markers == ["dirty"]
    assert notes == ["Nova receita desbloqueada: Vara Cristal"]
