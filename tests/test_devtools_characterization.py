from __future__ import annotations

from pathlib import Path

from utils.events import EventManager
from utils.hunts import HuntManager
from utils.missions import MissionProgress, MissionState
from utils.pesca import FishProfile, FishingPool, show_dev_save_editor
from utils.rods import Rod


def _make_rod(name: str) -> Rod:
    return Rod(
        name=name,
        luck=0.0,
        kg_max=100.0,
        control=0.0,
        description="",
        price=0.0,
    )


def _make_pool(fish: FishProfile) -> FishingPool:
    return FishingPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa_tranquila"),
        description="",
        rarity_weights={"Comum": 1},
    )


def test_devtools_add_fish_can_spawn_shiny_characterization(monkeypatch) -> None:
    fish = FishProfile(
        name="Tilapia",
        rarity="Comum",
        description="",
        kg_min=1.0,
        kg_max=2.0,
        base_value=10.0,
    )
    pool = _make_pool(fish)
    rod = _make_rod("Vara Bambu")
    inventory = []
    discovered_fish: set[str] = set()
    inputs = iter(["12", "tila", "", "", "s", "0"])

    monkeypatch.setattr("utils.pesca.use_modern_ui", lambda: False)
    monkeypatch.setattr("utils.pesca.clear_screen", lambda: None)
    monkeypatch.setattr("utils.pesca.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    show_dev_save_editor(
        balance=0.0,
        level=1,
        xp=0,
        selected_pool=pool,
        equipped_rod=rod,
        pools=[pool],
        available_rods=[rod],
        owned_rods=[rod],
        unlocked_pools={pool.name},
        unlocked_rods={rod.name},
        discovered_fish=discovered_fish,
        inventory=inventory,
        bait_by_id={},
        bait_inventory={},
        equipped_bait_id=None,
        fish_by_name={fish.name: fish},
        available_mutations=[],
        missions=[],
        mission_state=MissionState(),
        mission_progress=MissionProgress(),
        event_manager=EventManager([], dev_tools_enabled=True),
        hunt_manager=HuntManager([], dev_tools_enabled=True),
    )

    assert len(inventory) == 1
    assert inventory[0].name == "Tilapia"
    assert inventory[0].is_shiny is True
    assert discovered_fish == {"Tilapia"}
