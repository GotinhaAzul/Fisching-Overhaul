from __future__ import annotations

from typing import Sequence, Set, TYPE_CHECKING

from utils.rods import Rod

if TYPE_CHECKING:
    from utils.pesca import FishingPool


def select_starter_rod(available_rods: Sequence[Rod]) -> Rod:
    starter_rod = next(
        (
            rod
            for rod in available_rods
            if rod.name.strip().lower() in {"vara de bambu", "vara bambu"}
        ),
        None,
    )
    if starter_rod is not None:
        return starter_rod

    default_rods = [rod for rod in available_rods if rod.unlocked_default]
    return min(default_rods or available_rods, key=lambda rod: rod.price)


def select_default_pool(pools: Sequence["FishingPool"]) -> "FishingPool":
    return next(
        (pool for pool in pools if pool.folder.name.lower() == "lagoa"),
        pools[0],
    )


def build_default_unlocked_rods(
    available_rods: Sequence[Rod],
    starter_rod: Rod,
) -> Set[str]:
    return {
        rod.name for rod in available_rods if rod.unlocked_default
    } | {starter_rod.name}


def build_default_unlocked_pools(
    pools: Sequence["FishingPool"],
    selected_pool: "FishingPool",
) -> Set[str]:
    return {
        pool.name for pool in pools if pool.unlocked_default
    } | {selected_pool.name}
