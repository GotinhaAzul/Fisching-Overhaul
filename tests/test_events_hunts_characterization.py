from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.pesca import FishProfile, load_hunts, load_pools
from utils.events import EventDefinition, EventManager
from utils.hunts import HuntDefinition, HuntManager
from utils.pesca_round_helpers import combine_fish_profiles


def _event(
    name: str,
    *,
    description: str = "Descricao",
    duration_s: float = 30.0,
) -> EventDefinition:
    return EventDefinition(
        name=name,
        description=description,
        chance=0.0,
        interval_s=30.0,
        duration_s=duration_s,
        luck_multiplier=1.0,
        xp_multiplier=1.0,
        fish_profiles=[],
        rarity_weights={},
        mutations=[],
    )


def _hunt(
    hunt_id: str,
    *,
    name: str = "Hunt",
    pool_name: str = "Rio",
    duration_s: float = 40.0,
    fish_profiles: list[FishProfile] | None = None,
) -> HuntDefinition:
    return HuntDefinition(
        hunt_id=hunt_id,
        name=name,
        description="Descricao",
        pool_name=pool_name,
        duration_s=duration_s,
        check_interval_s=30.0,
        disturbance_per_catch=2.0,
        disturbance_max=10.0,
        rarity_weights={},
        fish_profiles=list(fish_profiles or []),
        cooldown_s=20.0,
        disturbance_decay_per_check=0.0,
    )


def _fish(
    name: str,
    *,
    rarity: str = "Raro",
    kg_min: float = 1.0,
    kg_max: float = 5.0,
) -> FishProfile:
    return FishProfile(
        name=name,
        rarity=rarity,
        description="Descricao",
        kg_min=kg_min,
        kg_max=kg_max,
        base_value=10.0,
        sequence_len=4,
        reaction_time_s=2.0,
    )


def test_event_manager_force_event_notification_queue_characterization(monkeypatch) -> None:
    now = {"value": 100.0}
    monkeypatch.setattr("utils.events.time.monotonic", lambda: now["value"])

    manager = EventManager([_event("Tempestade", description="Ventos fortes")], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    selected = manager.force_event("tempestade")
    assert selected is not None
    assert selected.name == "Tempestade"

    active = manager.get_active_event()
    assert active is not None
    assert active.definition.name == "Tempestade"
    assert active.started_at == 100.0
    assert active.ends_at == 130.0
    assert manager.pop_notifications() == [
        "Evento iniciado: Tempestade! Ventos fortes"
    ]


def test_event_manager_force_event_replacement_notifications_characterization(monkeypatch) -> None:
    monkeypatch.setattr("utils.events.time.monotonic", lambda: 250.0)

    manager = EventManager([_event("Nublado"), _event("Tempestade")], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.force_event("nublado")
    assert manager.pop_notifications() == ["Evento iniciado: Nublado! Descricao"]

    manager.force_event("tempestade")
    assert manager.pop_notifications() == [
        "O evento 'Nublado' foi encerrado (forcado).",
        "Evento iniciado: Tempestade! Descricao",
    ]


def test_event_manager_force_event_disabled_characterization() -> None:
    manager = EventManager([_event("Tempestade")], dev_tools_enabled=False)
    assert manager.force_event("tempestade") is None
    assert manager.get_active_event() is None
    assert manager.pop_notifications() == []


def test_hunt_manager_force_hunt_notification_queue_characterization(monkeypatch) -> None:
    now = {"value": 80.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt("h1", name="Caos", fish_profiles=[_fish("Lula Gigante")])
    manager = HuntManager([hunt], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.record_catch("Rio")
    before_state = manager.serialize_state()
    before_disturbance = before_state["hunts"]["h1"]["disturbance"]
    assert isinstance(before_disturbance, float)
    assert before_disturbance > 0.0

    selected = manager.force_hunt("h1")
    assert selected is not None
    assert selected.hunt_id == "h1"

    active = manager.get_active_hunt_for_pool("Rio")
    assert active is not None
    assert active.definition.hunt_id == "h1"
    assert active.started_at == 80.0
    assert active.ends_at == 120.0
    assert active.remaining_fish_names == ["Lula Gigante"]
    assert manager.pop_notifications() == ["Hunt iniciada em Rio: Caos"]

    after_state = manager.serialize_state()
    assert after_state["hunts"]["h1"]["disturbance"] == 0.0


def test_hunt_manager_serialize_restore_roundtrip_characterization(monkeypatch) -> None:
    now = {"value": 500.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunts = [
        _hunt("h1", name="Caos", fish_profiles=[_fish("Lula Gigante"), _fish("Kraken Jovem")]),
        _hunt("h2", name="Marola", pool_name="Lagoa", fish_profiles=[_fish("Pirarucu Ancestral")]),
    ]
    manager = HuntManager(hunts, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.record_catch("Rio")
    manager.force_hunt("h1")
    ended = manager.consume_hunt_fish(
        "Rio",
        "Lula Gigante",
        catchable_fish_names={"Kraken Jovem"},
    )
    assert ended is False
    raw_state = manager.serialize_state()

    restored = HuntManager(hunts, dev_tools_enabled=True)
    restored.restore_state(raw_state)
    restored_state = restored.serialize_state()

    assert set(restored_state["hunts"].keys()) == {"h1", "h2"}
    assert restored_state["hunts"]["h1"]["disturbance"] == 0.0
    assert restored_state["hunts"]["h2"]["disturbance"] == 0.0

    active_by_pool: Any = restored_state["active_by_pool"]
    assert isinstance(active_by_pool, dict)
    assert "Rio" in active_by_pool
    assert active_by_pool["Rio"]["hunt_id"] == "h1"
    assert active_by_pool["Rio"]["remaining_s"] > 0.0
    assert active_by_pool["Rio"]["remaining_fish_names"] == ["Kraken Jovem"]
    assert [fish.name for fish in restored.get_available_fish_for_pool("Rio")] == ["Kraken Jovem"]


def test_hunt_manager_consumes_only_current_hunt_instance_and_ends_when_exhausted(
    monkeypatch,
) -> None:
    now = {"value": 900.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt(
        "h1",
        name="Ataque",
        fish_profiles=[_fish("Mossjaw"), _fish("Awakened Mossjaw")],
    )
    manager = HuntManager([hunt], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.force_hunt("h1")
    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Mossjaw",
        "Awakened Mossjaw",
    ]

    ended = manager.consume_hunt_fish(
        "Rio",
        "Mossjaw",
        catchable_fish_names={"Awakened Mossjaw"},
    )
    assert ended is False
    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Awakened Mossjaw",
    ]
    assert manager.get_active_hunt_for_pool("Rio") is not None

    ended = manager.consume_hunt_fish(
        "Rio",
        "Awakened Mossjaw",
        catchable_fish_names=set(),
    )
    assert ended is True
    assert manager.get_active_hunt_for_pool("Rio") is None
    assert manager.get_available_fish_for_pool("Rio") == []
    assert manager.pop_notifications() == [
        "Hunt iniciada em Rio: Ataque",
        "A hunt 'Ataque' terminou.",
    ]

    now["value"] = 930.0
    manager.force_hunt("h1")
    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Mossjaw",
        "Awakened Mossjaw",
    ]


def test_combine_fish_profiles_uses_runtime_hunt_fish_list_characterization() -> None:
    class _Pool:
        def __init__(self) -> None:
            self.fish_profiles = [_fish("Tilapia")]

    combined = combine_fish_profiles(
        _Pool(),
        None,
        [_fish("Awakened Mossjaw")],
    )

    assert [fish.name for fish in combined] == ["Tilapia", "Awakened Mossjaw"]


def test_hunt_manager_restores_legacy_active_hunt_with_full_fish_list(monkeypatch) -> None:
    now = {"value": 1200.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt(
        "h1",
        name="Guardiao",
        fish_profiles=[_fish("Mossjaw"), _fish("Awakened Mossjaw")],
    )
    manager = HuntManager([hunt], dev_tools_enabled=True)

    manager.restore_state(
        {
            "hunts": {
                "h1": {
                    "disturbance": 0.0,
                    "cooldown_remaining_s": 0.0,
                    "next_check_in_s": 0.0,
                }
            },
            "active_by_pool": {"Rio": {"hunt_id": "h1", "remaining_s": 15.0}},
        }
    )

    assert [fish.name for fish in manager.get_available_fish_for_pool("Rio")] == [
        "Mossjaw",
        "Awakened Mossjaw",
    ]


def test_real_repo_forbidden_forest_pool_and_hunt_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    pools = load_pools(repo_root / "pools")
    hunts = load_hunts(repo_root / "hunts", {pool.name for pool in pools})

    pool_by_name = {pool.name: pool for pool in pools}
    hunt_by_id = {hunt.hunt_id: hunt for hunt in hunts}

    forbidden_pool = pool_by_name["Templo de Micelio"]
    assert forbidden_pool.hidden_from_bestiary_until_unlocked is True
    assert len(forbidden_pool.fish_profiles) == 9
    assert {fish.name for fish in forbidden_pool.fish_profiles} >= {
        "Raia-Micelial",
        "Coroa do Santuario",
    }

    guardiao = hunt_by_id["o_guardiao"]
    assert guardiao.name == "O Guardiao"
    assert guardiao.pool_name == "Templo de Micelio"
    assert guardiao.disturbance_max == 3200.0
    assert {fish.name for fish in guardiao.fish_profiles} == {
        "Mossjaw",
        "Awakened Mossjaw",
    }


def test_real_repo_major_area_assignments_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    pools = load_pools(repo_root / "pools")
    pools_by_name = {pool.name: pool for pool in pools}

    expected_major_areas = {
        "A Fonte": "Terras Aridas",
        "Aguas Calmas": "Fossa das Marianas",
        "As profundezas": "Redemoinho",
        "Baia do Sol": "Arquipelago Solar",
        "Caverna Carmesim": "Fundo do Mar",
        "Caverna Luminosa": "Fundo do Mar",
        "Deserto Taara": "Terras Aridas",
        "Profundezas Desoladas": "Fundo do Mar",
        "Lagoa Tranquila": "Ilha Moosewood",
        "O Jardim": "Aguas Pantanosas",
        "Pantano Mushgrove": "Aguas Pantanosas",
        "Ponto Zero": "Fossa das Marianas",
        "Piscina de Salmoura": "Fundo do Mar",
        "Rachadura Vulcanica": "Fossa das Marianas",
        "Rio Correnteza": "Ilha Moosewood",
        "Templo de Micelio": "Aguas Pantanosas",
        "Vertigo": "Redemoinho",
        "Vulcao do Sol": "Arquipelago Solar",
        "Zenite Abissal": "Fossa das Marianas",
        "Zona Glacial": "Fossa das Marianas",
        "Angra Cristal": "Redemoinho",
    }

    assert len(expected_major_areas) == 21

    covered_pools = [pool for pool in pools if pool.name in expected_major_areas]
    assert len(covered_pools) == len(expected_major_areas)

    for pool_name, major_area in expected_major_areas.items():
        assert pool_name in pools_by_name
        assert pools_by_name[pool_name].major_area == major_area

    for pool_name, pool in pools_by_name.items():
        if pool_name not in expected_major_areas:
            assert pool.major_area is None

    assert pools_by_name["Farseas"].hidden_from_pool_selection is True
    assert pools_by_name["Farseas"].hidden_from_bestiary_until_unlocked is True
    assert pools_by_name["Cafeteria"].hidden_from_pool_selection is True
    assert pools_by_name["Cafeteria"].hidden_from_bestiary_until_unlocked is True
    assert pools_by_name["Templo de Micelio"].hidden_from_bestiary_until_unlocked is True


def test_load_pools_reads_explicit_major_area_characterization(tmp_path: Path) -> None:
    import json as _json

    pool_dir = tmp_path / "tempestade_mar"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()
    pool_data = {
        "name": "  Baia Tempestuosa  ",
        "major_area": "  Grande Oceano  ",
        "description": "Area exposta a mares revoltos.",
        "rarity_chances": {"Comum": 100},
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")
    fish_data = {
        "name": "Espadinha",
        "rarity": "Comum",
        "description": "",
        "kg_min": 1.0,
        "kg_max": 2.0,
        "base_value": 10,
        "sequence_len": 4,
        "reaction_time_s": 2.0,
    }
    (fish_dir / "espadinha.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    pool = next(p for p in pools if p.name == "Baia Tempestuosa")

    assert pool.major_area == "Grande Oceano"


def test_load_pools_keeps_major_area_none_when_missing_characterization(
    tmp_path: Path,
) -> None:
    import json as _json

    pool_dir = tmp_path / "rio_mistico"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()
    pool_data = {
        "name": "Rio Místico",
        "description": "Um trecho isolado de agua.",
        "rarity_chances": {"Comum": 100},
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")
    fish_data = {
        "name": "Pescadinha",
        "rarity": "Comum",
        "description": "",
        "kg_min": 1.0,
        "kg_max": 2.0,
        "base_value": 10,
        "sequence_len": 4,
        "reaction_time_s": 2.0,
    }
    (fish_dir / "pescadinha.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    pool = next(p for p in pools if p.name == "Rio Místico")

    assert pool.major_area is None


def test_load_pools_keeps_major_area_none_for_invalid_major_area_characterization(
    tmp_path: Path,
) -> None:
    import json as _json

    cases = [
        ("blank_major_area", "   "),
        ("empty_major_area", ""),
        ("numeric_major_area", 42),
    ]

    for folder_name, raw_major_area in cases:
        pool_dir = tmp_path / folder_name
        pool_dir.mkdir()
        fish_dir = pool_dir / "fish"
        fish_dir.mkdir()
        pool_data = {
            "name": f"Pool {folder_name}",
            "major_area": raw_major_area,
            "description": "Area de teste.",
            "rarity_chances": {"Comum": 100},
        }
        (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")
        fish_data = {
            "name": "Pescadinha",
            "rarity": "Comum",
            "description": "",
            "kg_min": 1.0,
            "kg_max": 2.0,
            "base_value": 10,
            "sequence_len": 4,
            "reaction_time_s": 2.0,
        }
        (fish_dir / "pescadinha.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    pools_by_name = {pool.name: pool for pool in pools}

    assert pools_by_name["Pool blank_major_area"].major_area is None
    assert pools_by_name["Pool empty_major_area"].major_area is None
    assert pools_by_name["Pool numeric_major_area"].major_area is None


def test_load_pools_falls_back_to_folder_name_when_pool_name_invalid_characterization(
    tmp_path: Path,
) -> None:
    import json as _json

    pool_dir = tmp_path / "fallback_pool_dir"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()
    pool_data = {
        "name": "   ",
        "major_area": "  ",
        "description": "Area de teste.",
        "rarity_chances": {"Comum": 100},
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")
    fish_data = {
        "name": "Pescadinha",
        "rarity": "Comum",
        "description": "",
        "kg_min": 1.0,
        "kg_max": 2.0,
        "base_value": 10,
        "sequence_len": 4,
        "reaction_time_s": 2.0,
    }
    (fish_dir / "pescadinha.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    pool = next(p for p in pools if p.name == "fallback_pool_dir")

    assert pool.major_area is None


def test_deserto_taara_pool_loads_correct_fish_count(tmp_path: Path) -> None:
    import json as _json

    pool_dir = tmp_path / "deserto_taara"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()

    pool_data = {
        "name": "Deserto Taara",
        "description": "Um leito de mar antigo que secou ha milenios. A areia guarda criaturas que se recusam a desaparecer.",
        "unlocked_default": False,
        "rarity_chances": {
            "Comum": 55,
            "Incomum": 23,
            "Raro": 14,
            "Epico": 7,
            "Lendario": 1,
        },
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")

    rarities = [
        ("areia", "Comum"),
        ("piramboia_taara", "Comum"),
        ("bagre_sedimentar", "Incomum"),
        ("aruana_sepultado", "Incomum"),
        ("fossil_errante", "Raro"),
        ("saurio_das_dunas", "Raro"),
        ("serpente_dunaria", "Raro"),
        ("escorpiao_de_ambar", "Epico"),
        ("anciao_de_areia", "Epico"),
        ("xeique_de_taara", "Lendario"),
    ]
    for slug, rarity in rarities:
        fish_data = {
            "name": slug,
            "rarity": rarity,
            "description": "",
            "kg_min": 1.0,
            "kg_max": 2.0,
            "base_value": 10,
            "sequence_len": 4,
            "reaction_time_s": 2.0,
        }
        (fish_dir / f"{slug}.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    taara = next(p for p in pools if p.name == "Deserto Taara")
    assert len(taara.fish_profiles) == 10
    rarities_found = {f.rarity for f in taara.fish_profiles}
    assert "Lendario" in rarities_found
    assert "Epico" in rarities_found

    repo_pools = {
        pool.name: pool for pool in load_pools(Path(__file__).resolve().parent.parent / "pools")
    }
    assert "Deserto Taara" in repo_pools
    assert len(repo_pools["Deserto Taara"].fish_profiles) == 10


def test_a_fonte_pool_loads_correct_fish_count(tmp_path: Path) -> None:
    import json as _json

    pool_dir = tmp_path / "a_fonte"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()

    pool_data = {
        "name": "A Fonte",
        "description": "Escondida sob o Deserto Taara, uma nascente subterranea preserva um ecossistema que o mundo acima desconhece.",
        "unlocked_default": False,
        "rarity_chances": {
            "Comum": 50,
            "Incomum": 25,
            "Raro": 16,
            "Epico": 8,
            "Lendario": 1,
        },
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")

    rarities = [
        ("grilo_dagua", "Comum"),
        ("peixe_de_copo", "Comum"),
        ("camarao_aurora", "Incomum"),
        ("borboleta_aquatica", "Incomum"),
        ("lanterna_das_cavernas", "Raro"),
        ("cego_da_fonte", "Raro"),
        ("sereia_subterranea", "Raro"),
        ("anjo_da_fonte", "Epico"),
        ("guardiao_da_fonte", "Epico"),
        ("espirito_de_taara", "Lendario"),
    ]
    for slug, rarity in rarities:
        fish_data = {
            "name": slug,
            "rarity": rarity,
            "description": "",
            "kg_min": 1.0,
            "kg_max": 2.0,
            "base_value": 10,
            "sequence_len": 4,
            "reaction_time_s": 2.0,
        }
        (fish_dir / f"{slug}.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    fonte = next(p for p in pools if p.name == "A Fonte")
    assert len(fonte.fish_profiles) == 10
    rarities_found = {f.rarity for f in fonte.fish_profiles}
    assert "Lendario" in rarities_found
    assert "Epico" in rarities_found

    repo_pools = {
        pool.name: pool for pool in load_pools(Path(__file__).resolve().parent.parent / "pools")
    }
    assert "A Fonte" in repo_pools
    assert len(repo_pools["A Fonte"].fish_profiles) == 10


def test_coroa_de_espinhos_hunt_loads_for_grandreef(tmp_path: Path) -> None:
    import json as _json

    hunt_dir = tmp_path / "coroa_de_espinhos"
    hunt_dir.mkdir()
    fish_dir = hunt_dir / "fish"
    fish_dir.mkdir()
    payload = {
        "name": "Coroa de Espinhos",
        "description": "Uma forma estrelada de proporções absurdas avança pelo recife. Cada coral que toca desaparece. O recife está em silêncio.",
        "pool_name": "Grande Recife",
        "duration_minutes": 6,
        "check_interval_seconds": 60,
        "disturbance_per_catch": 2,
        "disturbance_max": 1800,
        "rarity_chances": {"Epico": 6, "Lendario": 4},
        "cooldown_minutes": 10,
        "disturbance_decay_per_check": 3,
    }
    (hunt_dir / "hunt.json").write_text(_json.dumps(payload), encoding="utf-8")
    fish_payload = {
        "name": "Coroa de Espinhos",
        "rarity": "Lendario",
        "description": "Uma estrela-do-mar colossal que devora o recife em seu caminho.",
        "kg_min": 18.0,
        "kg_max": 52.0,
        "base_value": 145,
        "sequence_len": 8,
        "reaction_time_s": 1.0,
    }
    (fish_dir / "coroa_de_espinhos.json").write_text(_json.dumps(fish_payload), encoding="utf-8")
    hunts = load_hunts(tmp_path)
    hunt = next(x for x in hunts if x.name == "Coroa de Espinhos")
    assert hunt.pool_name == "Grande Recife"
    assert hunt.rarity_weights.get("Lendario", 0) > 0

    repo_hunts = {
        hunt.hunt_id: hunt for hunt in load_hunts(Path(__file__).resolve().parent.parent / "hunts")
    }
    assert "coroa_de_espinhos" in repo_hunts
    assert repo_hunts["coroa_de_espinhos"].pool_name == "Grande Recife"
    assert repo_hunts["coroa_de_espinhos"].rarity_weights.get("Lendario", 0) > 0
