from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from utils.baits import BaitDefinition

if TYPE_CHECKING:
    from utils.events import EventDefinition
    from utils.hunts import HuntDefinition
    from utils.pesca import FishProfile, FishingPool
    from utils.rods import Rod


def resolve_active_bait(
    bait_inventory: Dict[str, int],
    bait_by_id: Dict[str, BaitDefinition],
    equipped_bait_id: Optional[str],
) -> tuple[Optional[str], Optional[BaitDefinition], int]:
    if equipped_bait_id and (
        equipped_bait_id not in bait_by_id
        or bait_inventory.get(equipped_bait_id, 0) <= 0
    ):
        bait_inventory.pop(equipped_bait_id, None)
        equipped_bait_id = None
    active_bait = bait_by_id.get(equipped_bait_id) if equipped_bait_id else None
    active_bait_quantity = bait_inventory.get(equipped_bait_id, 0) if equipped_bait_id else 0
    return equipped_bait_id, active_bait, active_bait_quantity


def calculate_effective_rod_stats(
    equipped_rod: "Rod",
    active_bait: Optional[BaitDefinition],
) -> tuple[float, float, float]:
    bait_control = active_bait.control if active_bait else 0.0
    bait_luck = active_bait.luck if active_bait else 0.0
    bait_kg_plus = active_bait.kg_plus if active_bait else 0.0
    effective_control = equipped_rod.control + bait_control
    effective_luck = equipped_rod.luck + bait_luck
    effective_kg_max = max(0.01, equipped_rod.kg_max + bait_kg_plus)
    return effective_control, effective_luck, effective_kg_max


def combine_fish_profiles(
    selected_pool: "FishingPool",
    event_def: Optional["EventDefinition"],
    hunt_def: Optional["HuntDefinition"],
) -> List["FishProfile"]:
    event_fish = event_def.fish_profiles if event_def else []
    hunt_fish = hunt_def.fish_profiles if hunt_def else []
    return (
        list(selected_pool.fish_profiles)
        + list(event_fish)
        + list(hunt_fish)
    )


def filter_eligible_fish(
    fish_profiles: Sequence["FishProfile"],
    *,
    kg_max: float,
) -> List["FishProfile"]:
    return [
        fish for fish in fish_profiles if fish.kg_min <= kg_max
    ]
