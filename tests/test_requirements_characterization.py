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
from utils.missions import (
    MissionDefinition,
    MissionProgress,
    _build_mission_actions,
    _check_requirement,
    _format_requirement,
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
        fish_caught=5,
        fish_delivered=2,
        fish_sold=3,
        fish_caught_by_name={"Tilapia": 3},
        fish_delivered_by_name={"Tilapia": 1},
        fish_sold_by_name={"Tilapia": 2},
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
        fish_caught=1,
        fish_delivered=0,
        fish_sold=1,
        fish_caught_by_name={"tilapia": 1},
        fish_delivered_by_name={},
        fish_sold_by_name={"tilapia": 1},
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

