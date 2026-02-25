from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from utils.baits import BaitDefinition


def sorted_baits_for_dev_menu(
    bait_by_id: Dict[str, BaitDefinition],
    bait_inventory: Dict[str, int],
    equipped_bait_id: Optional[str],
) -> List[tuple[BaitDefinition, int, bool]]:
    available_baits = sorted(bait_by_id.values(), key=lambda bait: bait.name)
    rows: List[tuple[BaitDefinition, int, bool]] = []
    for bait in available_baits:
        rows.append(
            (
                bait,
                bait_inventory.get(bait.bait_id, 0),
                bait.bait_id == equipped_bait_id,
            )
        )
    return rows
