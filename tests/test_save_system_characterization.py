from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from utils.baits import BaitDefinition
from utils.inventory import InventoryEntry
from utils.rods import Rod
from utils.rod_upgrades import restore_rod_upgrade_state
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
    restore_storage,
    restore_selected_pool,
    restore_unlocked_pools,
    restore_xp,
    save_game,
)
from utils.rod_upgrades import UpgradeRequirement


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


def _pool(name: str, *, major_area: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, major_area=major_area or name)


def test_restore_helpers_ignore_major_area_and_remain_name_based() -> None:
    fallback_pool = _pool("Lagoa Tranquila", major_area="Costa Norte")
    pools = [fallback_pool, _pool("Rio Correnteza", major_area="Costa Sul")]

    restored_pool = restore_selected_pool("Lagoa Tranquila", pools, fallback_pool)
    assert restored_pool is fallback_pool
    assert restored_pool.major_area == "Costa Norte"


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
            is_shiny=True,
            mutation_name="Albino",
            mutation_xp_multiplier=1.4,
            mutation_gold_multiplier=1.2,
            is_unsellable=True,
        ),
        InventoryEntry(
            name="Pacu",
            rarity="Comum",
            kg=3.0,
            base_value=8.0,
        ),
    ]
    storage = [
        InventoryEntry(
            name="Pirarucu",
            rarity="Lendario",
            kg=25.0,
            base_value=180.0,
            mutation_name="Noir",
            mutation_xp_multiplier=1.3,
            mutation_gold_multiplier=1.3,
        )
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

    rod_upgrade_state = restore_rod_upgrade_state(
        {"Vara Carbono": {"luck": 0.12, "kg_max": 0.08}}
    )
    rod_upgrade_state.set_recipe(
        "Vara Carbono",
        [UpgradeRequirement("Tilapia", "Comum", 3)],
        stat="luck",
    )

    save_game(
        save_path,
        balance=321.25,
        inventory=inventory,
        storage=storage,
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
        rod_upgrade_state=rod_upgrade_state,
    )

    raw = load_game(save_path)
    assert raw is not None
    assert raw["version"] == SAVE_VERSION
    assert raw["equipped_bait"] == "cheap/minhoca"
    assert raw["bait_inventory"] == {"cheap/minhoca": 3, "invalid": 2}
    assert raw["inventory"][0]["is_shiny"] is True
    assert raw["inventory"][1]["is_shiny"] is False
    assert raw["inventory"][0]["is_unsellable"] is True
    assert raw["inventory"][1]["is_unsellable"] is False
    assert raw["storage"][0]["name"] == "Pirarucu"
    assert raw["storage"][0]["mutation_name"] == "Noir"
    assert raw["rod_upgrades"] == {
        "bonuses": {"Vara Carbono": {"luck": 0.12, "kg_max": 0.08}},
        "recipes": {
            "Vara Carbono": {
                "luck": [
                    {"fish_name": "Tilapia", "rarity": "Comum", "count": 3},
                ]
            }
        },
    }

    restored_inventory = restore_inventory(raw["inventory"])
    assert len(restored_inventory) == 2
    assert restored_inventory[0].name == "Tilapia"
    assert restored_inventory[0].is_shiny is True
    assert restored_inventory[0].mutation_name == "Albino"
    assert restored_inventory[0].is_unsellable is True
    assert restored_inventory[1].is_shiny is False
    assert restored_inventory[1].is_unsellable is False

    restored_storage = restore_storage(raw["storage"], {"Tilapia", "Pacu", "Pirarucu"})
    assert len(restored_storage) == 1
    assert restored_storage[0].name == "Pirarucu"
    assert restored_storage[0].mutation_name == "Noir"

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

    restored_rod_upgrades = restore_rod_upgrade_state(raw["rod_upgrades"])
    assert restored_rod_upgrades.to_dict() == {"Vara Carbono": {"luck": 0.12, "kg_max": 0.08}}
    restored_recipe = restored_rod_upgrades.get_recipe("Vara Carbono", "luck")
    assert restored_recipe is not None
    assert restored_recipe.stat == "luck"
    assert restored_recipe.fish_requirements == [UpgradeRequirement("Tilapia", "Comum", 3)]


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

    restored_legacy_rod_upgrades = restore_rod_upgrade_state(
        {"Vara Bambu": {"luck": 0.12}}
    )
    assert restored_legacy_rod_upgrades.to_dict() == {"Vara Bambu": {"luck": 0.12}}
    assert restored_legacy_rod_upgrades.get_recipe("Vara Bambu") is None

    restored_legacy_recipe_upgrades = restore_rod_upgrade_state(
        {
            "bonuses": {},
            "recipes": {
                "Vara Carbono": [
                    {"fish_name": "Tilapia", "rarity": "Comum", "count": 2},
                ]
            },
        }
    )
    legacy_recipe = restored_legacy_recipe_upgrades.get_recipe("Vara Carbono", "luck")
    assert legacy_recipe is not None
    assert legacy_recipe.stat == ""
    assert legacy_recipe.fish_requirements == [UpgradeRequirement("Tilapia", "Comum", 2)]


def test_restore_inventory_defaults_unsellable_for_legacy_payload() -> None:
    restored = restore_inventory(
        [
            {"name": "Tilapia", "rarity": "Comum", "kg": 2.0, "base_value": 10.0},
            {
                "name": "Pacu",
                "rarity": "Comum",
                "kg": 3.0,
                "base_value": 8.0,
                "is_unsellable": "true",
            },
        ]
    )

    assert len(restored) == 2
    assert restored[0].is_shiny is False
    assert restored[0].is_unsellable is False
    assert restored[1].is_shiny is False
    assert restored[1].is_unsellable is False


def test_restore_storage_defaults_empty_and_skips_invalid_entries() -> None:
    restored_missing = restore_storage(None, {"Tilapia"})
    assert restored_missing == []

    restored = restore_storage(
        [
            {"name": "Tilapia", "rarity": "Comum", "kg": 2.0, "base_value": 10.0},
            {"name": "Inexistente", "rarity": "Comum", "kg": 1.0, "base_value": 5.0},
            {"name": "Tilapia", "rarity": "Comum", "kg": "bad", "base_value": 10.0},
            "corrompido",
        ],
        {"Tilapia"},
    )

    assert len(restored) == 1
    assert restored[0].name == "Tilapia"

