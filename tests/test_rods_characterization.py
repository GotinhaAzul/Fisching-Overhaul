from __future__ import annotations

import json
from pathlib import Path

from utils.mutations import load_mutations
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
