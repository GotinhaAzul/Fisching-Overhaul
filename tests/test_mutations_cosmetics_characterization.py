from __future__ import annotations

import json
from pathlib import Path

from utils.cosmetics import (
    DEFAULT_UI_COLOR_ID,
    DEFAULT_UI_ICON_ID,
    UI_COLOR_DEFINITIONS,
    UI_COLORS_ORDER,
    UI_ICON_DEFINITIONS,
    UI_ICONS_ORDER,
    create_default_cosmetics_state,
    equip_icon_color,
    equip_ui_color,
    equip_ui_icon,
    list_unlocked_ui_colors,
    list_unlocked_ui_icons,
    restore_cosmetics_state,
    serialize_cosmetics_state,
    unlock_ui_color,
    unlock_ui_icon,
)
from utils.mutations import load_mutations, load_mutations_optional


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_mutation_loaders_characterization(tmp_path: Path) -> None:
    mutations_dir = tmp_path / "mutations"
    mutations_dir.mkdir()

    _write_json(
        mutations_dir / "a.json",
        {
            "name": "Albino",
            "description": "",
            "xp_multiplier": 1.2,
            "gold_multiplier": 1.1,
            "chance_percent": 25,
            "required_rods": ["Vara Bambu"],
        },
    )
    _write_json(
        mutations_dir / "b.json",
        {
            "name": "Noir",
            "description": "",
            "xp_multiplier": 2.0,
            "gold_multiplier": 1.8,
            "chance": 0.05,
        },
    )
    _write_json(mutations_dir / "invalid.json", {"description": "missing name"})

    required = load_mutations(mutations_dir)
    optional = load_mutations_optional(mutations_dir)

    assert [mutation.name for mutation in required] == ["Albino", "Noir"]
    assert [mutation.name for mutation in optional] == ["Albino", "Noir"]
    assert required[0].chance == 0.25
    assert required[0].required_rods == ("Vara Bambu",)
    assert required[1].chance == 0.05
    assert required[1].required_rods == ()


def test_mutation_loaders_missing_directory_behavior(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"
    assert load_mutations_optional(missing_dir) == []
    try:
        load_mutations(missing_dir)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("load_mutations should raise FileNotFoundError for missing directory.")


def test_cosmetics_state_roundtrip_and_order_characterization() -> None:
    state = create_default_cosmetics_state()
    assert DEFAULT_UI_COLOR_ID == UI_COLORS_ORDER[0]
    assert DEFAULT_UI_ICON_ID == UI_ICONS_ORDER[0]
    assert state.equipped_ui_color == DEFAULT_UI_COLOR_ID
    assert state.equipped_icon_color == DEFAULT_UI_COLOR_ID
    assert state.equipped_ui_icon == DEFAULT_UI_ICON_ID

    assert unlock_ui_color(state, UI_COLORS_ORDER[1])
    assert unlock_ui_icon(state, UI_ICONS_ORDER[1])
    assert equip_ui_color(state, UI_COLORS_ORDER[1])
    assert equip_icon_color(state, UI_COLORS_ORDER[1])
    assert equip_ui_icon(state, UI_ICONS_ORDER[1])
    assert not unlock_ui_color(state, "unknown_color")
    assert not unlock_ui_icon(state, "unknown_icon")

    serialized = serialize_cosmetics_state(state)
    restored = restore_cosmetics_state(serialized)

    assert restored.equipped_ui_color == UI_COLORS_ORDER[1]
    assert restored.equipped_icon_color == UI_COLORS_ORDER[1]
    assert restored.equipped_ui_icon == UI_ICONS_ORDER[1]
    assert UI_COLORS_ORDER[1] in restored.unlocked_ui_colors
    assert UI_ICONS_ORDER[1] in restored.unlocked_ui_icons

    unlocked_colors = list_unlocked_ui_colors(restored)
    unlocked_icons = list_unlocked_ui_icons(restored)
    assert [color.color_id for color in unlocked_colors] == [
        color_id for color_id in UI_COLORS_ORDER if color_id in restored.unlocked_ui_colors
    ]
    assert [icon.icon_id for icon in unlocked_icons] == [
        icon_id for icon_id in UI_ICONS_ORDER if icon_id in restored.unlocked_ui_icons
    ]
    assert UI_COLORS_ORDER[1] in UI_COLOR_DEFINITIONS
    assert UI_ICONS_ORDER[1] in UI_ICON_DEFINITIONS


def test_cosmetics_restore_migrates_missing_icon_color_to_ui_color() -> None:
    state = create_default_cosmetics_state()
    assert unlock_ui_color(state, UI_COLORS_ORDER[1])
    assert equip_ui_color(state, UI_COLORS_ORDER[1])

    serialized = serialize_cosmetics_state(state)
    serialized.pop("equipped_icon_color", None)

    restored = restore_cosmetics_state(serialized)
    assert restored.equipped_ui_color == UI_COLORS_ORDER[1]
    assert restored.equipped_icon_color == UI_COLORS_ORDER[1]


def test_equip_icon_color_requires_unlocked_color() -> None:
    state = create_default_cosmetics_state()
    assert not equip_icon_color(state, "unknown_color")

    target_color = UI_COLORS_ORDER[1]
    assert not equip_icon_color(state, target_color)
    assert unlock_ui_color(state, target_color)
    assert equip_icon_color(state, target_color)
    assert state.equipped_icon_color == target_color

