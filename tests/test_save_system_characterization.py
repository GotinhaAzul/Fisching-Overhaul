from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from utils.baits import BaitDefinition
from utils.inventory import InventoryEntry
from utils.rods import Rod
from utils.save_system import (
    SAVE_VERSION,
    load_game,
    restore_bait_inventory,
    restore_balance,
    restore_discovered_fish,
    restore_equipped_bait,
    restore_equipped_rod,
    restore_hunt_state,
    restore_inventory,
    restore_level,
    restore_owned_rods,
    restore_selected_pool,
    restore_unlocked_pools,
    restore_xp,
    save_game,
)


def _rod(name: str, *, price: float = 0.0, unlocked_default: bool = False) -> Rod:
    return Rod(
        name=name,
        luck=0.0,
        kg_max=100.0,
        control=0.0,
        description=f"{name} desc",
        price=price,
        unlocked_default=unlocked_default,
    )


def _pool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def test_save_load_roundtrip_with_restore_helpers(tmp_path: Path) -> None:
    save_path = tmp_path / "savegame.json"
    starter_rod = _rod("Vara Bambu", unlocked_default=True)
    premium_rod = _rod("Vara Carbono", price=120.0)
    selected_pool = _pool("Lagoa Tranquila")
    inventory = [
        InventoryEntry(
            name="Tilapia",
            rarity="Comum",
            kg=2.5,
            base_value=10.0,
            mutation_name="Albino",
            mutation_xp_multiplier=1.4,
            mutation_gold_multiplier=1.2,
        ),
        InventoryEntry(
            name="Pacu",
            rarity="Comum",
            kg=3.0,
            base_value=8.0,
        ),
    ]
    bait_defs = {
        "cheap/minhoca": BaitDefinition(
            bait_id="cheap/minhoca",
            crate_id="cheap",
            name="Minhoca",
            control=0.0,
            luck=0.0,
            kg_plus=0.0,
            rarity="Comum",
        )
    }

    save_game(
        save_path,
        balance=321.25,
        inventory=inventory,
        owned_rods=[starter_rod, premium_rod],
        equipped_rod=premium_rod,
        selected_pool=selected_pool,
        unlocked_pools=["Lagoa Tranquila", "Rio Correnteza"],
        unlocked_rods=["Vara Bambu", "Vara Carbono"],
        level=7,
        xp=55,
        discovered_fish=["Tilapia"],
        mission_state={"completed": ["m1"]},
        mission_progress={"fish_caught": 10},
        pool_market_orders={"Lagoa Tranquila": {"dummy": True}},
        hunt_state={"hunts": {"h1": {}}, "active_by_pool": {"Lagoa Tranquila": "h1"}},
        crafting_state={"crafted": ["r1"]},
        crafting_progress={"find_fish_counts_by_name": {"Tilapia": 2}},
        bait_inventory={"cheap/minhoca": 3, "invalid": 2, "zero": 0},
        equipped_bait="cheap/minhoca",
        bestiary_reward_state={"claimed": ["reward_1"]},
        cosmetics_state={"equipped_ui_color": "ocean_blue"},
    )

    raw = load_game(save_path)
    assert raw is not None
    assert raw["version"] == SAVE_VERSION
    assert raw["equipped_bait"] == "cheap/minhoca"
    assert raw["bait_inventory"] == {"cheap/minhoca": 3, "invalid": 2}

    restored_inventory = restore_inventory(raw["inventory"])
    assert len(restored_inventory) == 2
    assert restored_inventory[0].name == "Tilapia"
    assert restored_inventory[0].mutation_name == "Albino"

    available_rods = [starter_rod, premium_rod]
    restored_owned = restore_owned_rods(raw["owned_rods"], available_rods, starter_rod)
    assert [rod.name for rod in restored_owned] == ["Vara Bambu", "Vara Carbono"]

    pools = [selected_pool, _pool("Rio Correnteza")]
    restored_selected_pool = restore_selected_pool(raw["selected_pool"], pools, selected_pool)
    assert restored_selected_pool.name == "Lagoa Tranquila"

    restored_unlocked_pools = restore_unlocked_pools(raw["unlocked_pools"], pools, restored_selected_pool)
    assert "Lagoa Tranquila" in restored_unlocked_pools
    assert "Rio Correnteza" in restored_unlocked_pools

    restored_equipped_rod = restore_equipped_rod(raw["equipped_rod"], restored_owned, starter_rod)
    assert restored_equipped_rod.name == "Vara Carbono"

    restored_baits = restore_bait_inventory(raw["bait_inventory"], bait_defs)
    assert restored_baits == {"cheap/minhoca": 3}

    restored_equipped_bait = restore_equipped_bait(raw["equipped_bait"], restored_baits, bait_defs)
    assert restored_equipped_bait == "cheap/minhoca"

    restored_discovered = restore_discovered_fish(raw["discovered_fish"], restored_inventory)
    assert restored_discovered == {"Tilapia", "Pacu"}


def test_restore_helpers_legacy_and_invalid_payloads() -> None:
    starter_rod = _rod("Vara Bambu", unlocked_default=True)
    available_rods = [starter_rod]
    fallback_pool = _pool("Lagoa Tranquila")
    pools = [fallback_pool]

    restored_owned = restore_owned_rods(["Inexistente"], available_rods, starter_rod)
    assert [rod.name for rod in restored_owned] == ["Vara Bambu"]

    restored_pool = restore_selected_pool("Inexistente", pools, fallback_pool)
    assert restored_pool.name == "Lagoa Tranquila"

    restored_unlocked = restore_unlocked_pools(None, pools, fallback_pool)
    assert restored_unlocked == ["Lagoa Tranquila"]

    assert restore_balance("123.5", 0.0) == 123.5
    assert restore_balance("bad", 9.0) == 9.0
    assert restore_level("0", 5) == 1
    assert restore_level("bad", 5) == 5
    assert restore_xp("-7", 5) == 0
    assert restore_xp("bad", 5) == 5

    restored_hunt = restore_hunt_state({"hunts": [], "active_by_pool": "x"})
    assert restored_hunt == {"hunts": {}, "active_by_pool": {}}

