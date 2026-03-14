from __future__ import annotations

from utils.inventory import InventoryEntry, format_inventory_entry
from utils.storage_ui import render_storage


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
