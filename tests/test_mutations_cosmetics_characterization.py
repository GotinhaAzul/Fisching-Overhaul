from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from utils.mutations import (
    filter_mutations_for_appraisal,
    filter_mutations_for_rod,
    load_mutations,
    load_mutations_optional,
)


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


def test_arenoso_mutation_loads_with_correct_fields(tmp_path: Path) -> None:
    mutations_dir = tmp_path / "mutations"
    mutations_dir.mkdir()
    _write_json(
        mutations_dir / "arenoso.json",
        {
            "name": "Arenoso",
            "description": "Graos de areia se incrustaram entre as escamas ao longo de geracoes, criando uma textura aspera e dourada unica.",
            "xp_multiplier": 1.1,
            "gold_multiplier": 1.15,
            "chance_percent": 0.22,
        },
    )
    mutations = load_mutations(mutations_dir)
    assert len(mutations) == 1
    assert mutations[0].name == "Arenoso"
    assert mutations[0].chance == pytest.approx(0.0022)
    assert mutations[0].xp_multiplier == pytest.approx(1.1)
    assert mutations[0].gold_multiplier == pytest.approx(1.15)
    assert mutations[0].required_rods == ()

    repo_mutations = {
        mutation.name: mutation
        for mutation in load_mutations(Path(__file__).resolve().parent.parent / "mutations")
    }
    assert "Arenoso" in repo_mutations
    assert repo_mutations["Arenoso"].chance == pytest.approx(0.0022)


def test_mutation_filter_uses_rod_chance_overrides_without_entering_global_pool(
    tmp_path: Path,
) -> None:
    mutations_dir = tmp_path / "mutations"
    mutations_dir.mkdir()

    _write_json(
        mutations_dir / "prometido.json",
        {
            "name": "Prometido",
            "description": "",
            "xp_multiplier": 1.4,
            "gold_multiplier": 1.6,
            "chance_percent": 10,
            "required_rods": ["Promessa Luminescente", "Ruina Prometida"],
            "rod_chance_overrides": {"Ruina Prometida": 15},
        },
    )

    mutations = load_mutations(mutations_dir)

    global_pool = filter_mutations_for_rod(mutations, "Vara Bambu")
    promessa_pool = filter_mutations_for_rod(mutations, "Promessa Luminescente")
    ruina_pool = filter_mutations_for_rod(mutations, "Ruina Prometida")

    assert global_pool == []
    assert len(promessa_pool) == 1
    assert promessa_pool[0].name == "Prometido"
    assert promessa_pool[0].chance == 0.10
    assert len(ruina_pool) == 1
    assert ruina_pool[0].name == "Prometido"
    assert ruina_pool[0].chance == 0.15


def test_mutation_filter_keeps_base_chance_and_single_rod_override_exclusive(
    tmp_path: Path,
) -> None:
    mutations_dir = tmp_path / "mutations"
    mutations_dir.mkdir()

    _write_json(
        mutations_dir / "sereno.json",
        {
            "name": "Sereno",
            "description": "",
            "xp_multiplier": 1.4,
            "gold_multiplier": 1.6,
            "chance_percent": 3,
            "required_rods": ["Hollow Dusk", "Serenidade"],
            "rod_chance_overrides": {
                "Serenidade": 30,
            },
        },
    )

    mutations = load_mutations(mutations_dir)

    global_pool = filter_mutations_for_rod(mutations, "Vara Bambu")
    hollow_pool = filter_mutations_for_rod(mutations, "Hollow Dusk")
    serenidade_pool = filter_mutations_for_rod(mutations, "Serenidade")

    assert global_pool == []
    assert len(hollow_pool) == 1
    assert hollow_pool[0].name == "Sereno"
    assert hollow_pool[0].chance == 0.03
    assert len(serenidade_pool) == 1
    assert serenidade_pool[0].name == "Sereno"
    assert serenidade_pool[0].chance == 0.30


def test_mutation_filter_for_appraisal_excludes_rod_exclusive_mutations(tmp_path: Path) -> None:
    mutations_dir = tmp_path / "mutations"
    mutations_dir.mkdir()

    _write_json(
        mutations_dir / "albino.json",
        {
            "name": "Albino",
            "description": "",
            "xp_multiplier": 1.2,
            "gold_multiplier": 1.1,
            "chance_percent": 25,
            "rod_chance_overrides": {"Trinity": 15},
        },
    )
    _write_json(
        mutations_dir / "prometido.json",
        {
            "name": "Prometido",
            "description": "",
            "xp_multiplier": 1.4,
            "gold_multiplier": 1.6,
            "chance_percent": 10,
            "required_rods": ["Promessa Luminescente"],
        },
    )

    mutations = load_mutations(mutations_dir)
    appraisal_pool = filter_mutations_for_appraisal(mutations)

    assert [mutation.name for mutation in appraisal_pool] == ["Albino"]
    assert appraisal_pool[0].chance == 0.25


def test_azul_lamina_mutations_use_accented_rod_name_characterization() -> None:
    mutations_dir = Path(__file__).resolve().parent.parent / "mutations"
    mutations = load_mutations(mutations_dir)

    azul_pool = {
        mutation.name: mutation
        for mutation in filter_mutations_for_rod(mutations, "Azul Lâmina")
        if mutation.name in {"Prometido", "Nuvem", "Solar"}
    }

    assert set(azul_pool) == {"Prometido", "Nuvem", "Solar"}
    assert azul_pool["Prometido"].chance == 0.05
    assert azul_pool["Nuvem"].chance == 0.04
    assert azul_pool["Solar"].chance == 0.03


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
