from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from utils.crafting import (
    CraftingDefinition,
    CraftingProgress,
    CraftingState,
    deliver_inventory_entry_for_craft,
    format_crafting_requirement,
    has_any_pool_bestiary_full_completion,
    is_craft_unlocked,
    pay_craft_requirement,
    required_money_for_craft,
)
from utils.inventory import InventoryEntry
from utils.market import _show_crafting_recipe_detail
from utils.shiny import ShinyConfig, ShinyDisplayConfig
from utils.missions import (
    MissionDefinition,
    MissionProgress,
    MissionState,
    _deliver_fish_for_mission,
    _entry_matches_delivery_requirements,
    load_missions,
    _build_mission_actions,
    _check_requirement,
    _format_requirement,
    restore_mission_progress,
    update_mission_completions,
)


@dataclass
class _DummyFish:
    name: str
    counts_for_bestiary_completion: bool = True


@dataclass
class _DummyPool:
    name: str
    fish_profiles: list[_DummyFish]
    folder: Path
    counts_for_bestiary_completion: bool = True


def _mission_context() -> tuple[MissionProgress, MissionProgress, list[_DummyPool], set[str]]:
    progress = MissionProgress(
        total_money_earned=200.0,
        total_money_spent=120.0,
        total_mission_money_paid=35.0,
        fish_caught=5,
        fish_delivered=2,
        fish_sold=3,
        shiny_fish_caught=2,
        shiny_fish_delivered=1,
        fish_caught_by_name={"Tilapia": 3},
        fish_delivered_by_name={"Tilapia": 1},
        fish_sold_by_name={"Tilapia": 2},
        shiny_fish_caught_by_name={"Tilapia": 1, "Pacu": 1},
        shiny_fish_delivered_by_name={"Tilapia": 1},
        fish_caught_with_mutation_by_name={"Tilapia": 2},
        fish_delivered_with_mutation_by_name={"Tilapia": 2},
        fish_delivered_with_mutation_pair_counts={"Tilapia::Albino": 2},
        mutations_caught_by_name={"Albino": 2},
        mutations_delivered_by_name={"Albino": 1},
        play_time_seconds=400.0,
    )
    baseline = MissionProgress(
        total_money_earned=50.0,
        total_money_spent=20.0,
        total_mission_money_paid=5.0,
        fish_caught=1,
        fish_delivered=0,
        fish_sold=1,
        shiny_fish_caught=1,
        shiny_fish_delivered=0,
        fish_caught_by_name={"tilapia": 1},
        fish_delivered_by_name={},
        fish_sold_by_name={"tilapia": 1},
        shiny_fish_caught_by_name={"tilapia": 1},
        shiny_fish_delivered_by_name={},
        fish_caught_with_mutation_by_name={"tilapia": 1},
        fish_delivered_with_mutation_by_name={"tilapia": 1},
        fish_delivered_with_mutation_pair_counts={"Tilapia::Albino": 1},
        mutations_caught_by_name={"Albino": 1},
        mutations_delivered_by_name={},
        play_time_seconds=100.0,
    )
    pools = [
        _DummyPool(
            name="Lagoa Tranquila",
            fish_profiles=[
                _DummyFish("Tilapia", counts_for_bestiary_completion=True),
                _DummyFish("Segredo", counts_for_bestiary_completion=False),
            ],
            folder=Path("lagoa"),
            counts_for_bestiary_completion=True,
        ),
        _DummyPool(
            name="Debug Pool",
            fish_profiles=[_DummyFish("DebugFish", counts_for_bestiary_completion=True)],
            folder=Path("debug"),
            counts_for_bestiary_completion=False,
        ),
    ]
    discovered = {"Tilapia"}
    return progress, baseline, pools, discovered


def test_mission_requirement_formatting_characterization() -> None:
    progress, baseline, pools, discovered = _mission_context()
    completed_missions = {"m_base"}

    req_catch = {"type": "catch_fish", "count": 2, "fish_name": "TILAPIA"}
    _, current, target, done = _format_requirement(
        req_catch,
        progress,
        completed_missions,
        "m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=7,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (current, target, done) == (2, 2, True)

    req_pair = {
        "type": "deliver_fish_with_mutation",
        "count": 2,
        "fish_name": "Tilapia",
        "mutation_name": "Albino",
    }
    _, current, target, done = _format_requirement(
        req_pair,
        progress,
        completed_missions,
        "m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=7,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (current, target, done) == (1, 2, False)

    req_bestiary = {"type": "bestiary_percent", "percent": 100}
    _, current, target, done = _format_requirement(
        req_bestiary,
        progress,
        completed_missions,
        "m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=7,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (current, target, done) == (100, 100, True)

    req_spend = {"type": "spend_money", "amount": 25}
    _, current, target, done = _format_requirement(
        req_spend,
        progress,
        completed_missions,
        "m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=7,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (current, target, done) == (30, 25, True)

    assert _check_requirement(
        req_bestiary,
        progress,
        completed_missions,
        "m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=7,
        pools=pools,
        discovered_fish=discovered,
    )


def test_spend_money_ignores_generic_spending_characterization() -> None:
    progress = MissionProgress(total_money_spent=400.0, total_mission_money_paid=0.0)
    baseline = MissionProgress(total_money_spent=10.0, total_mission_money_paid=0.0)
    pools = [_DummyPool(name="Lagoa Tranquila", fish_profiles=[_DummyFish("Tilapia")], folder=Path("lagoa"))]

    _, current, target, done = _format_requirement(
        {"type": "spend_money", "amount": 50},
        progress,
        completed_missions=set(),
        current_mission_id="m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=1,
        pools=pools,
        discovered_fish=set(),
    )
    assert (current, target, done) == (0, 50, False)

    progress.record_mission_money_paid(60.0)
    _, current, target, done = _format_requirement(
        {"type": "spend_money", "amount": 50},
        progress,
        completed_missions=set(),
        current_mission_id="m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=1,
        pools=pools,
        discovered_fish=set(),
    )
    assert (current, target, done) == (60, 50, True)


def test_shiny_filtered_catch_and_delivery_requirements_characterization() -> None:
    progress, baseline, pools, discovered = _mission_context()

    label, current, target, done = _format_requirement(
        {"type": "catch_fish", "count": 1, "fish_name": "Tilapia", "is_shiny": False},
        progress,
        completed_missions=set(),
        current_mission_id="m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=1,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (label, current, target, done) == ("Capturar Tilapia não-shiny", 2, 1, True)

    label, current, target, done = _format_requirement(
        {"type": "catch_fish", "count": 2, "is_shiny": True},
        progress,
        completed_missions=set(),
        current_mission_id="m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=1,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (label, current, target, done) == ("Capturar peixes shiny", 1, 2, False)

    label, current, target, done = _format_requirement(
        {"type": "deliver_fish", "count": 1, "fish_name": "Tilapia", "is_shiny": True},
        progress,
        completed_missions=set(),
        current_mission_id="m_current",
        baseline_progress=baseline,
        completed_baseline=0,
        level=1,
        pools=pools,
        discovered_fish=discovered,
    )
    assert (label, current, target, done) == ("Entregar Tilapia shiny", 1, 1, True)


def test_delivery_requirement_shiny_filter_matching_characterization() -> None:
    shiny_entry = InventoryEntry(
        name="Tilapia",
        rarity="Comum",
        kg=2.5,
        base_value=10.0,
        is_shiny=True,
    )
    plain_entry = InventoryEntry(
        name="Tilapia",
        rarity="Comum",
        kg=2.0,
        base_value=10.0,
        is_shiny=False,
    )
    requirement = {"type": "deliver_fish", "count": 1, "fish_name": "Tilapia", "is_shiny": True}

    assert _entry_matches_delivery_requirements(shiny_entry, [requirement])
    assert not _entry_matches_delivery_requirements(plain_entry, [requirement])


def test_restore_mission_progress_legacy_mission_payment_fallback_characterization() -> None:
    legacy = restore_mission_progress({"total_money_spent": 123.0})
    assert legacy.total_mission_money_paid == 123.0

    explicit = restore_mission_progress(
        {"total_money_spent": 123.0, "total_mission_money_paid": 9.0}
    )
    assert explicit.total_mission_money_paid == 9.0


def test_build_mission_actions_characterization() -> None:
    progress, baseline, pools, discovered = _mission_context()
    mission = MissionDefinition(
        mission_id="m_deliver",
        name="Entrega",
        description="",
        requirements=[
            {"type": "deliver_fish", "count": 2, "fish_name": "Tilapia"},
            {"type": "spend_money", "amount": 150},
        ],
        rewards=[],
    )
    actions = _build_mission_actions(
        mission,
        progress,
        {"m_other"},
        baseline_progress=baseline,
        completed_baseline=0,
        level=7,
        pools=pools,
        discovered_fish=discovered,
    )
    assert set(actions) == {"deliver_fish", "spend_money"}


def test_bulk_mission_delivery_caps_overlapping_requirements_characterization(
    monkeypatch,
) -> None:
    inventory = [
        InventoryEntry(
            name="Tilapia",
            rarity="Comum",
            kg=2.5,
            base_value=10.0,
            mutation_name="Albino",
        ),
        InventoryEntry(
            name="Tilapia",
            rarity="Comum",
            kg=2.1,
            base_value=10.0,
            mutation_name="Albino",
        ),
    ]
    progress = MissionProgress()
    requirements = [
        {"type": "deliver_mutation", "count": 1, "mutation_name": "Albino"},
        {
            "type": "deliver_fish_with_mutation",
            "count": 1,
            "fish_name": "Tilapia",
            "mutation_name": "Albino",
        },
    ]

    monkeypatch.setattr("builtins.input", lambda _: "t")

    delivered_count = _deliver_fish_for_mission(
        requirements,
        inventory,
        progress,
        max_deliveries=2,
        remaining_requirement_counts=[1, 1],
    )

    assert delivered_count == 1
    assert len(inventory) == 1
    assert progress.mutated_fish_delivered == 1
    assert progress.mutations_delivered_by_name == {"Albino": 1}
    assert progress.fish_delivered_with_mutation_pair_counts == {"Tilapia::Albino": 1}


def test_claimed_unlock_rewards_retroactively_unlock_new_missions_characterization() -> None:
    pools = [_DummyPool(name="Lagoa Tranquila", fish_profiles=[_DummyFish("Tilapia")], folder=Path("lagoa"))]
    missions = [
        MissionDefinition(
            mission_id="m_old",
            name="Missao Antiga",
            description="",
            requirements=[],
            rewards=[{"type": "unlock_missions", "mission_ids": ["m_new"]}],
            starts_unlocked=True,
        ),
        MissionDefinition(
            mission_id="m_new",
            name="Missao Nova",
            description="",
            requirements=[{"type": "catch_fish", "count": 1}],
            rewards=[],
        ),
    ]
    state = MissionState(unlocked={"m_old"}, completed={"m_old"}, claimed={"m_old"})
    progress = MissionProgress(total_money_earned=321.0, fish_caught=0)

    newly_completed = update_mission_completions(
        missions,
        state,
        progress,
        level=1,
        pools=pools,
        discovered_fish=set(),
    )

    assert "m_new" in state.unlocked
    assert "m_new" not in newly_completed
    assert restore_mission_progress(
        state.unlocked_progress_baselines["m_new"]
    ).total_money_earned == 321.0
    assert state.unlocked_completed_counts["m_new"] == 1


def test_bestiary_percent_counts_regionless_event_fish_characterization() -> None:
    pools = [_DummyPool(name="Lagoa Tranquila", fish_profiles=[_DummyFish("Tilapia")], folder=Path("lagoa"))]
    missions = [
        MissionDefinition(
            mission_id="m_event_bestiary",
            name="Catalogar tudo",
            description="",
            requirements=[{"type": "bestiary_percent", "percent": 100}],
            rewards=[],
            starts_unlocked=True,
        )
    ]
    progress = MissionProgress()

    state_without_event_fish = MissionState(unlocked={"m_event_bestiary"})
    newly_completed_without_event_fish = update_mission_completions(
        missions,
        state_without_event_fish,
        progress,
        level=1,
        pools=pools,
        discovered_fish={"Tilapia"},
        regionless_fish_profiles=[_DummyFish("Peixe Aurora")],
    )

    assert newly_completed_without_event_fish == set()
    assert "m_event_bestiary" not in state_without_event_fish.completed

    state_with_event_fish = MissionState(unlocked={"m_event_bestiary"})
    newly_completed_with_event_fish = update_mission_completions(
        missions,
        state_with_event_fish,
        progress,
        level=1,
        pools=pools,
        discovered_fish={"Tilapia", "Peixe Aurora"},
        regionless_fish_profiles=[_DummyFish("Peixe Aurora")],
    )

    assert newly_completed_with_event_fish == {"m_event_bestiary"}
    assert "m_event_bestiary" in state_with_event_fish.completed


def test_crafting_unlock_and_delivery_characterization() -> None:
    definition = CraftingDefinition(
        craft_id="c1",
        rod_name="Vara Carbono",
        name="Receita",
        description="",
        unlock_mode="all",
        unlock_requirements=[
            {"type": "level", "level": 8},
            {"type": "unlock_pool", "pool_name": "Lagoa Tranquila"},
        ],
        craft_requirements=[
            {"type": "fish_with_mutation", "count": 1, "fish_name": "Tilapia", "mutation_name": "Albino"},
            {"type": "money", "amount": 50},
        ],
    )
    state = CraftingState()
    progress = CraftingProgress()
    pools = [
        _DummyPool(
            name="Lagoa Tranquila",
            fish_profiles=[_DummyFish("Tilapia")],
            folder=Path("lagoa"),
        )
    ]

    assert not is_craft_unlocked(
        definition,
        state,
        progress,
        level=7,
        pools=pools,
        discovered_fish={"Tilapia"},
        unlocked_pools={"lagoa tranquila"},
        mission_state={},
        unlocked_rods=set(),
        play_time_seconds=0.0,
    )
    assert is_craft_unlocked(
        definition,
        state,
        progress,
        level=8,
        pools=pools,
        discovered_fish={"Tilapia"},
        unlocked_pools={"Lagoa Tranquila"},
        mission_state={},
        unlocked_rods=set(),
        play_time_seconds=0.0,
    )

    inventory = [
        InventoryEntry(
            name="Tilapia",
            rarity="Comum",
            kg=2.0,
            base_value=10.0,
            mutation_name="Albino",
        ),
        InventoryEntry(
            name="Pacu",
            rarity="Comum",
            kg=3.0,
            base_value=8.0,
        ),
    ]

    delivered = deliver_inventory_entry_for_craft(definition, progress, inventory, 1)
    assert delivered is not None
    assert len(inventory) == 1

    _, current, target, done = format_crafting_requirement(
        definition.craft_requirements[0],
        definition.craft_id,
        progress,
        level=8,
    )
    assert (current, target, done) == (1, 1, True)

    assert required_money_for_craft(definition, progress) == 50.0
    assert pay_craft_requirement(definition, progress, 20.0) == 20.0
    assert required_money_for_craft(definition, progress) == 30.0


def test_crafting_recipe_detail_lists_shiny_delivery_value_characterization(
    monkeypatch,
    capsys,
) -> None:
    definition = CraftingDefinition(
        craft_id="c1",
        rod_name="Vara Carbono",
        name="Receita",
        description="",
        unlock_mode="all",
        unlock_requirements=[],
        craft_requirements=[
            {"type": "fish", "count": 1, "fish_name": "Tilapia"},
        ],
    )
    inventory = [
        InventoryEntry(
            name="Tilapia",
            rarity="Comum",
            kg=2.0,
            base_value=10.0,
            is_shiny=True,
        )
    ]
    shiny_config = ShinyConfig(
        catch_chance_percent=1.0,
        appraise_chance_percent=1.0,
        value_multiplier=2.0,
        display=ShinyDisplayConfig(
            label="Shiny",
            color="#FFD700",
            catch_message="Shiny!",
        ),
    )
    responses = iter(["1", "0", "", "0"])

    monkeypatch.setattr("utils.market.clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    returned_balance = _show_crafting_recipe_detail(
        definition,
        inventory,
        balance=100.0,
        level=1,
        available_rods=[],
        owned_rods=[],
        unlocked_rods=set(),
        crafting_state=CraftingState(),
        crafting_progress=CraftingProgress(),
        on_money_spent=lambda _amount: None,
        shiny_config=shiny_config,
    )

    assert returned_balance == 100.0
    assert "R$ 20.40" in capsys.readouterr().out


def test_market_shiny_helpers_expose_single_shiny_config_parameter_characterization() -> None:
    import inspect

    import utils.market as market

    recipe_detail_signature = inspect.signature(market._show_crafting_recipe_detail)
    recipe_helper_signature = inspect.signature(market._show_crafting_menu)
    value_helper_signature = inspect.signature(market._calculate_market_entry_value)

    assert list(recipe_detail_signature.parameters).count("shiny_config") == 1
    assert list(recipe_helper_signature.parameters).count("shiny_config") == 1
    assert list(value_helper_signature.parameters).count("shiny_config") == 1


def test_has_any_pool_bestiary_full_completion_characterization() -> None:
    pools = [
        _DummyPool(
            name="Lagoa Tranquila",
            fish_profiles=[_DummyFish("Tilapia"), _DummyFish("Pacu")],
            folder=Path("lagoa"),
        ),
        _DummyPool(
            name="Debug",
            fish_profiles=[_DummyFish("DebugFish")],
            folder=Path("debug"),
            counts_for_bestiary_completion=False,
        ),
    ]
    assert has_any_pool_bestiary_full_completion(pools, {"Tilapia", "Pacu"})
    assert not has_any_pool_bestiary_full_completion(pools, {"Tilapia"})


def test_real_repo_forbidden_forest_mission_chain_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    missions = {
        mission.mission_id: mission
        for mission in load_missions(repo_root / "missions")
    }

    assert "densa_mata_prologo" in missions
    assert "densa_mata_parte_1" in missions
    assert "densa_mata_parte_2" in missions
    assert "densa_mata_parte_3" in missions

    unlock_ojardim_rewards = missions["unlock_ojardim"].rewards
    assert {
        "type": "unlock_missions",
        "mission_ids": ["densa_mata_prologo"],
    } in unlock_ojardim_rewards

    prologo_requirements = missions["densa_mata_prologo"].requirements
    assert {
        "type": "bestiary_pool_percent",
        "pool_name": "Pantano Mushgrove",
        "percent": 50,
    } in prologo_requirements
    assert {
        "type": "bestiary_pool_percent",
        "pool_name": "O Jardim",
        "percent": 50,
    } in prologo_requirements

    parte_1_requirements = missions["densa_mata_parte_1"].requirements
    assert {
        "type": "deliver_mutation",
        "count": 4,
        "mutation_name": "Envenenado",
    } in parte_1_requirements
    assert {
        "type": "deliver_fish_with_mutation",
        "count": 1,
        "fish_name": "Vieira-Lama",
        "mutation_name": "Envenenado",
    } in parte_1_requirements

    assert {
        "type": "play_time",
        "minutes": 45,
    } in missions["densa_mata_parte_2"].requirements
    assert {
        "type": "deliver_mutation",
        "count": 3,
        "mutation_name": "Arcana",
    } in missions["densa_mata_parte_3"].requirements
    assert {
        "type": "unlock_pools",
        "pool_names": ["Templo de Micelio"],
    } in missions["densa_mata_parte_3"].rewards


def test_real_repo_desolate_deep_unlocks_luminous_cave_mission_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    missions = {
        mission.mission_id: mission
        for mission in load_missions(repo_root / "missions")
    }

    assert "desolate_unlock" in missions
    assert "unlock_caverna_luminosa" in missions

    assert {
        "type": "unlock_missions",
        "mission_ids": ["brinepool_unlock", "trident_unlock", "unlock_caverna_luminosa"],
    } in missions["desolate_unlock"].rewards

    luminous_requirements = missions["unlock_caverna_luminosa"].requirements
    assert {
        "type": "bestiary_pool_percent",
        "pool_name": "Profundezas Desoladas",
        "percent": 70,
    } in luminous_requirements
    assert {
        "type": "deliver_fish_with_mutation",
        "count": 1,
        "fish_name": "Surubim",
        "mutation_name": "Brilhante",
    } in luminous_requirements


def test_real_repo_celestia_unlock_reward_uses_pool_names_characterization() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    missions = {
        mission.mission_id: mission
        for mission in load_missions(repo_root / "missions")
    }

    assert "unlock_celestia" in missions
    assert {
        "type": "unlock_pools",
        "pool_names": ["Celestia"],
    } in missions["unlock_celestia"].rewards


def test_unlock_deserto_taara_mission_loads(tmp_path: Path) -> None:
    import json as _json

    mission_dir = tmp_path / "unlock_deserto_taara"
    mission_dir.mkdir()
    payload = {
        "id": "unlock_deserto_taara",
        "name": "Marcas de Areia",
        "description": "Areia voa no ar... de um deserto distante, talvez? Um leito de mar seco que guarda criaturas de outro tempo. Mas o deserto so se abre para quem se entrega a areia.",
        "starts_unlocked": True,
        "requirements": [
            {"type": "level", "level": 9},
            {"type": "deliver_mutation", "count": 1, "mutation_name": "Arenoso"},
        ],
        "rewards": [
            {"type": "unlock_pools", "pool_names": ["Deserto Taara"]},
            {
                "type": "unlock_missions",
                "mission_ids": ["unlock_a_fonte", "unlock_ouro_fervente_rod"],
            },
            {"type": "xp", "amount": 400},
        ],
    }
    (mission_dir / "mission.json").write_text(_json.dumps(payload), encoding="utf-8")
    missions = load_missions(tmp_path)
    mission = next(x for x in missions if x.mission_id == "unlock_deserto_taara")
    assert mission.starts_unlocked is True
    assert any(reward.get("type") == "unlock_pools" for reward in mission.rewards)

    repo_missions = {
        mission.mission_id: mission
        for mission in load_missions(Path(__file__).resolve().parent.parent / "missions")
    }
    assert "unlock_deserto_taara" in repo_missions
    assert any(
        reward.get("type") == "unlock_pools"
        for reward in repo_missions["unlock_deserto_taara"].rewards
    )


def test_unlock_a_fonte_mission_loads(tmp_path: Path) -> None:
    import json as _json

    mission_dir = tmp_path / "unlock_a_fonte"
    mission_dir.mkdir()
    payload = {
        "id": "unlock_a_fonte",
        "name": "Abaixo da Areia",
        "description": "O Deserto Taara esconde algo abaixo dele. Quem conhece bem o deserto consegue ouvir a agua.",
        "starts_unlocked": False,
        "requirements": [
            {"type": "bestiary_pool_percent", "pool_name": "Deserto Taara", "percent": 70},
            {"type": "deliver_mutation", "count": 2, "mutation_name": "Arenoso"},
        ],
        "rewards": [
            {"type": "unlock_pools", "pool_names": ["A Fonte"]},
            {"type": "xp", "amount": 500},
        ],
    }
    (mission_dir / "mission.json").write_text(_json.dumps(payload), encoding="utf-8")
    missions = load_missions(tmp_path)
    mission = next(x for x in missions if x.mission_id == "unlock_a_fonte")
    assert mission.starts_unlocked is False
    assert any(reward.get("type") == "unlock_pools" for reward in mission.rewards)

    repo_missions = {
        mission.mission_id: mission
        for mission in load_missions(Path(__file__).resolve().parent.parent / "missions")
    }
    assert "unlock_a_fonte" in repo_missions
    assert any(
        reward.get("type") == "unlock_pools"
        for reward in repo_missions["unlock_a_fonte"].rewards
    )


def test_unlock_ouro_fervente_rod_mission_loads(tmp_path: Path) -> None:
    import json as _json

    mission_dir = tmp_path / "unlock_ouro_fervente_rod"
    mission_dir.mkdir()
    payload = {
        "id": "unlock_ouro_fervente_rod",
        "name": "Calor que Forja",
        "description": "No centro do deserto, uma poca de fogo se mantem. Um cetro em seu centro que canaliza a mais pura ganancia por ouro.",
        "starts_unlocked": False,
        "requirements": [
            {"type": "deliver_fish", "count": 1, "fish_name": "Xeique de Taara"},
            {
                "type": "deliver_fish_with_mutation",
                "count": 1,
                "fish_name": "Serpente Dunária",
                "mutation_name": "Incinerado",
            },
            {"type": "earn_money", "amount": 5000},
        ],
        "rewards": [
            {"type": "unlock_rods", "rod_names": ["Ouro Fervente"]},
            {"type": "xp", "amount": 800},
        ],
    }
    (mission_dir / "mission.json").write_text(_json.dumps(payload), encoding="utf-8")
    missions = load_missions(tmp_path)
    mission = next(x for x in missions if x.mission_id == "unlock_ouro_fervente_rod")
    assert mission.starts_unlocked is False
    assert any(reward.get("type") == "unlock_rods" for reward in mission.rewards)

    repo_missions = {
        mission.mission_id: mission
        for mission in load_missions(Path(__file__).resolve().parent.parent / "missions")
    }
    assert "unlock_ouro_fervente_rod" in repo_missions
    assert any(
        reward.get("type") == "unlock_rods"
        for reward in repo_missions["unlock_ouro_fervente_rod"].rewards
    )


def test_retribuicao_crafting_recipe_loads_correctly(tmp_path: Path) -> None:
    import json as _json

    from utils.crafting import load_crafting_definitions

    craft_dir = tmp_path / "receita_retribuicao"
    craft_dir.mkdir()
    (craft_dir / "receita_retribuicao.json").write_text(
        _json.dumps(
            {
                "id": "retribuicao_craft",
                "rod_name": "Retribuição",
                "name": "As Quatro Formas",
                "description": "Cada fragmento carrega uma punição diferente. Reúna-os e espalhe a retribuição.",
                "unlock": {
                    "mode": "all",
                    "requirements": [
                        {"type": "unlock_pool", "pool_name": "Cafeteria"},
                    ],
                },
                "craft": {
                    "requirements": [
                        {
                            "type": "fish_with_mutation",
                            "fish_name": "Gladio Escaldante",
                            "mutation_name": "Carmesim",
                            "count": 1,
                        },
                        {
                            "type": "fish_with_mutation",
                            "fish_name": "Peixe Tres-Olhos",
                            "mutation_name": "Espiral",
                            "count": 1,
                        },
                        {
                            "type": "fish_with_mutation",
                            "fish_name": "Lagosta Cristal",
                            "mutation_name": "Cristalizado",
                            "count": 1,
                        },
                        {
                            "type": "fish_with_mutation",
                            "fish_name": "Enguia Ancia",
                            "mutation_name": "Profundo",
                            "count": 1,
                        },
                        {
                            "type": "fish",
                            "fish_name": "Cafe",
                            "count": 1,
                        },
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    definitions = load_crafting_definitions(tmp_path)
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.rod_name == "Retribuição"
    assert definition.craft_id == "retribuicao_craft"
    fish_names = {requirement["fish_name"] for requirement in definition.craft_requirements if "fish_name" in requirement}
    assert "Cafe" in fish_names
    assert len(definition.craft_requirements) == 5

    repo_definitions = {
        definition.craft_id: definition
        for definition in load_crafting_definitions(Path(__file__).resolve().parent.parent / "crafting")
    }
    assert "retribuicao_craft" in repo_definitions
    assert repo_definitions["retribuicao_craft"].rod_name == "Retribuição"
    assert len(repo_definitions["retribuicao_craft"].craft_requirements) == 5
