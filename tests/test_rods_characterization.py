from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.mutations import load_mutations
from utils.rod_presentation import format_rod_abilities
from utils.rods import load_rods


def _write_rod(base_dir: Path, file_name: str, payload: dict[str, object]) -> None:
    (base_dir / file_name).write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_load_rods_keeps_non_chance_slam_and_slash_values_as_full_numbers(
    tmp_path: Path,
) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod de Teste",
            "luck": 0.0,
            "kg_max": 100.0,
            "control": 0.0,
            "description": "desc",
            "price": 0,
            "can_slash": True,
            "slash_chance": "25%",
            "slash_power": "7%",
            "can_slam": True,
            "slam_chance": "40%",
            "slam_time_bonus": "12%",
            "can_recover": True,
            "recover_chance": "5%",
            "can_dupe": True,
            "dupe_chance": "10%",
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.slash_chance == 0.25
    assert rod.slam_chance == 0.4
    assert rod.recover_chance == 0.05
    assert rod.dupe_chance == 0.1
    assert rod.slash_power == 7
    assert rod.slam_time_bonus == 12.0


def test_load_rods_normalizes_only_chance_fields_when_values_are_over_one(
    tmp_path: Path,
) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod de Teste 2",
            "luck": 0.0,
            "kg_max": 100.0,
            "control": 0.0,
            "description": "desc",
            "price": 0,
            "can_slash": True,
            "slash_chance": 35,
            "slash_power": 35,
            "can_slam": True,
            "slam_chance": 15,
            "slam_time_bonus": 15,
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.slash_chance == 0.35
    assert rod.slam_chance == 0.15
    assert rod.slash_power == 35
    assert rod.slam_time_bonus == 15.0


def test_load_rods_parses_curse_fields_with_probability_normalization(
    tmp_path: Path,
) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod de Teste Curse",
            "luck": 0.0,
            "kg_max": 100.0,
            "control": 0.0,
            "description": "desc",
            "price": 0,
            "can_curse": True,
            "curse_chance": "20%",
            "curse_time_penalty": "15%",
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.can_curse is True
    assert rod.curse_chance == 0.2
    assert rod.curse_time_penalty == 15.0


def test_load_rods_curse_defaults_when_field_is_absent(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod Sem Curse",
            "luck": 0.0,
            "kg_max": 100.0,
            "control": 0.0,
            "description": "desc",
            "price": 0,
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.can_curse is False
    assert rod.curse_chance == 0.0
    assert rod.curse_time_penalty == 0.0


def test_load_rods_curse_defaults_when_field_is_invalid(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod Curse Invalida",
            "luck": 0.0,
            "kg_max": 100.0,
            "control": 0.0,
            "description": "desc",
            "price": 0,
            "can_curse": "talvez",
            "curse_chance": "abc",
            "curse_time_penalty": "abc",
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.can_curse is False
    assert rod.curse_chance == 0.0
    assert rod.curse_time_penalty == 0.0


def test_load_rods_keeps_curse_inactive_without_explicit_flag(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod Curse Implicita",
            "luck": 0.0,
            "kg_max": 100.0,
            "control": 0.0,
            "description": "desc",
            "price": 0,
            "curse_chance": 20,
            "curse_time_penalty": 0.15,
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.can_curse is False
    assert rod.curse_chance == 0.2
    assert rod.curse_time_penalty == 0.15
    assert format_rod_abilities(rod) == "-"


def test_real_repo_high_tier_rods_and_incinerado_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent

    rods = {rod.name: rod for rod in load_rods(repo_root / "rods")}
    mutations = {mutation.name: mutation for mutation in load_mutations(repo_root / "mutations")}

    assert {"Trinity", "Perforatio", "Frenesis", "Midas", "Magnasas"} <= set(rods)

    assert rods["Trinity"].luck == 0.15
    assert rods["Perforatio"].can_pierce is True
    assert rods["Perforatio"].pierce_chance == 0.30
    assert rods["Frenesis"].can_frenzy is True
    assert rods["Frenesis"].frenzy_chance == 0.25
    assert rods["Midas"].can_greed is True
    assert rods["Midas"].greed_chance == 0.12
    assert rods["Magnasas"].luck == 0.17

    incinerado = mutations["Incinerado"]
    assert incinerado.gold_multiplier == 1.4
    assert incinerado.chance == 0.20
    assert incinerado.required_rods == ("Magnasas",)


def test_shiny_override_absent_defaults_to_none(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Plain Rod", "luck": 0.0, "kg_max": 10.0, "control": 0.0, "description": "", "price": 0},
    )
    rod = load_rods(tmp_path)[0]
    assert rod.shiny_override is None


def test_shiny_override_integer_parsed_as_percent(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Shiny Rod", "luck": 0.0, "kg_max": 10.0, "control": 0.0, "description": "", "price": 0, "shiny_override": 5},
    )
    rod = load_rods(tmp_path)[0]
    assert rod.shiny_override == 0.05


def test_shiny_override_percent_string(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": "5%"},
    )
    assert load_rods(tmp_path)[0].shiny_override == 0.05


def test_shiny_override_decimal_fraction(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": 0.05},
    )
    assert load_rods(tmp_path)[0].shiny_override == 0.05


def test_shiny_override_zero_means_never(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": 0},
    )
    assert load_rods(tmp_path)[0].shiny_override == 0.0


def test_shiny_override_one_means_always(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {"name": "Rod", "luck": 0, "kg_max": 10, "control": 0, "description": "", "price": 0, "shiny_override": 1},
    )
    assert load_rods(tmp_path)[0].shiny_override == 1.0


def test_load_rods_parses_vfx_fields_with_safe_defaults_characterization(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod VFX",
            "luck": 0.0,
            "kg_max": 10.0,
            "control": 0.0,
            "description": "",
            "price": 0,
            "vfxseq": "bright_cyan",
            "vfxseqcount": 3,
            "vfxability": "red",
            "vfxabilitycount": 2,
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.vfxseq == "bright_cyan"
    assert rod.vfxseqcount == 3
    assert rod.vfxability == "red"
    assert rod.vfxabilitycount == 2


def test_load_rods_vfx_defaults_when_values_are_empty_or_invalid_characterization(
    tmp_path: Path,
) -> None:
    _write_rod(
        tmp_path,
        "rod.json",
        {
            "name": "Rod VFX Default",
            "luck": 0.0,
            "kg_max": 10.0,
            "control": 0.0,
            "description": "",
            "price": 0,
            "vfxseq": "   ",
            "vfxseqcount": 0,
            "vfxabilitycount": "abc",
        },
    )

    rod = load_rods(tmp_path)[0]

    assert rod.vfxseq is None
    assert rod.vfxseqcount == 1
    assert rod.vfxability is None
    assert rod.vfxabilitycount == 1


def test_ouro_fervente_rod_loads_alter_and_greed(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "ouro_fervente.json",
        {
            "name": "Ouro Fervente",
            "luck": 0.38,
            "kg_max": 500.0,
            "control": -0.10,
            "description": "A forja do deserto transforma os peixes em seu anzol no mais puro desejo dourado. Pode puxa-los?",
            "price": 0,
            "unlocked_default": False,
            "can_alter": True,
            "timecount": -25,
            "hardcount": 50,
            "can_greed": True,
            "greed_chance": 0.18,
        },
    )
    rod = load_rods(tmp_path)[0]
    assert rod.name == "Ouro Fervente"
    assert rod.can_alter is True
    assert rod.timecount == pytest.approx(-25.0)
    assert rod.hardcount == pytest.approx(50.0)
    assert rod.can_greed is True
    assert rod.greed_chance == pytest.approx(0.18)

    repo_rods = {rod.name: rod for rod in load_rods(Path(__file__).resolve().parent.parent / "rods")}
    assert "Ouro Fervente" in repo_rods
    assert repo_rods["Ouro Fervente"].timecount == pytest.approx(-25.0)
    assert repo_rods["Ouro Fervente"].hardcount == pytest.approx(50.0)
    assert repo_rods["Ouro Fervente"].greed_chance == pytest.approx(0.18)


def test_vara_tranquilizante_loads_alter_fields(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "vara_tranquilizante.json",
        {
            "name": "Vara Tranquilizante",
            "luck": 0.20,
            "kg_max": 130.0,
            "control": 0.35,
            "description": "A nascente acalma até os peixes mais agitados. E também quem a segura.",
            "price": 7500,
            "unlocked_default": False,
            "unlockswithpool": "A Fonte",
            "can_alter": True,
            "timecount": 60,
            "hardcount": 20,
        },
    )
    rod = load_rods(tmp_path)[0]
    assert rod.name == "Vara Tranquilizante"
    assert rod.can_alter is True
    assert rod.timecount == pytest.approx(60.0)
    assert rod.hardcount == pytest.approx(20.0)
    assert rod.unlocks_with_pool == "A Fonte"

    repo_rods = {rod.name: rod for rod in load_rods(Path(__file__).resolve().parent.parent / "rods")}
    assert "Vara Tranquilizante" in repo_rods
    assert repo_rods["Vara Tranquilizante"].timecount == pytest.approx(60.0)
    assert repo_rods["Vara Tranquilizante"].hardcount == pytest.approx(20.0)
    assert repo_rods["Vara Tranquilizante"].unlocks_with_pool == "A Fonte"


def test_retribuicao_loads_four_abilities(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "retribuicao.json",
        {
            "name": "Retribuição",
            "luck": 0.04,
            "kg_max": 250.0,
            "control": -0.1,
            "description": "Retribuição deve ser espalhada!",
            "price": 0,
            "unlocked_default": False,
            "unlockswithpool": "Cafeteria",
            "counts_for_bestiary_completion": False,
            "can_slash": True,
            "slash_chance": 0.22,
            "slash_power": 1,
            "can_dupe": True,
            "dupe_chance": 0.13,
            "can_greed": True,
            "greed_chance": 0.13,
            "can_pierce": True,
            "pierce_chance": 0.20,
        },
    )
    rod = load_rods(tmp_path)[0]
    assert rod.name == "Retribuição"
    assert rod.can_slash is True
    assert rod.slash_chance == pytest.approx(0.22)
    assert rod.can_dupe is True
    assert rod.dupe_chance == pytest.approx(0.13)
    assert rod.can_greed is True
    assert rod.greed_chance == pytest.approx(0.13)
    assert rod.can_pierce is True
    assert rod.pierce_chance == pytest.approx(0.20)
    assert rod.counts_for_bestiary_completion is False

    repo_rods = {rod.name: rod for rod in load_rods(Path(__file__).resolve().parent.parent / "rods")}
    assert "Retribuição" in repo_rods
    assert repo_rods["Retribuição"].slash_chance == pytest.approx(0.22)
    assert repo_rods["Retribuição"].dupe_chance == pytest.approx(0.13)
    assert repo_rods["Retribuição"].greed_chance == pytest.approx(0.13)
    assert repo_rods["Retribuição"].pierce_chance == pytest.approx(0.20)
    assert repo_rods["Retribuição"].counts_for_bestiary_completion is False
