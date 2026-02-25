from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from utils.crafting import (
    CraftingProgress,
    CraftingState,
    serialize_crafting_progress,
    serialize_crafting_state,
)
from utils.cosmetics import PlayerCosmeticsState, serialize_cosmetics_state
from utils.inventory import InventoryEntry
from utils.market import serialize_pool_market_orders
from utils.missions import MissionProgress, serialize_mission_progress, serialize_mission_state
from utils.rods import Rod
from utils.save_system import save_game

if TYPE_CHECKING:
    from utils.bestiary_rewards import BestiaryRewardState
    from utils.hunts import HuntManager
    from utils.pesca import FishingPool


def autosave_state(
    save_path: Path,
    balance: float,
    inventory: List[InventoryEntry],
    bait_inventory: Dict[str, int],
    owned_rods: List[Rod],
    equipped_rod: Rod,
    equipped_bait_id: Optional[str],
    selected_pool: "FishingPool",
    unlocked_pools: set[str],
    unlocked_rods: set[str],
    level: int,
    xp: int,
    discovered_fish: set[str],
    mission_state,
    mission_progress: MissionProgress,
    crafting_state: CraftingState,
    crafting_progress: CraftingProgress,
    pool_market_orders,
    bestiary_reward_state: "BestiaryRewardState",
    cosmetics_state: PlayerCosmeticsState,
    hunt_manager: Optional["HuntManager"],
    serialize_bestiary_reward_state,
) -> None:
    save_game(
        save_path,
        balance=balance,
        inventory=inventory,
        owned_rods=owned_rods,
        equipped_rod=equipped_rod,
        selected_pool=selected_pool,
        unlocked_pools=sorted(unlocked_pools),
        unlocked_rods=sorted(unlocked_rods),
        level=level,
        xp=xp,
        discovered_fish=sorted(discovered_fish),
        mission_state=serialize_mission_state(mission_state),
        mission_progress=serialize_mission_progress(mission_progress),
        crafting_state=serialize_crafting_state(crafting_state),
        crafting_progress=serialize_crafting_progress(crafting_progress),
        pool_market_orders=serialize_pool_market_orders(pool_market_orders),
        hunt_state=hunt_manager.serialize_state() if hunt_manager else {},
        bait_inventory=bait_inventory,
        equipped_bait=equipped_bait_id,
        bestiary_reward_state=serialize_bestiary_reward_state(bestiary_reward_state),
        cosmetics_state=serialize_cosmetics_state(cosmetics_state),
    )
