from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from utils.baits import BaitDefinition
from utils.cosmetics import (
    PlayerCosmeticsState,
    UI_COLOR_DEFINITIONS,
    UI_ICON_DEFINITIONS,
)


def sanitize_equipped_bait(
    equipped_bait_id: Optional[str],
    bait_inventory: Dict[str, int],
    bait_by_id: Dict[str, BaitDefinition],
) -> Optional[str]:
    if not equipped_bait_id:
        return None
    if equipped_bait_id not in bait_by_id:
        return None
    if bait_inventory.get(equipped_bait_id, 0) <= 0:
        return None
    return equipped_bait_id


def list_owned_baits(
    bait_inventory: Dict[str, int],
    bait_by_id: Dict[str, BaitDefinition],
) -> List[tuple[str, BaitDefinition, int]]:
    owned: List[tuple[str, BaitDefinition, int]] = []
    for bait_id, quantity in bait_inventory.items():
        if quantity <= 0:
            continue
        bait = bait_by_id.get(bait_id)
        if bait is None:
            continue
        owned.append((bait_id, bait, quantity))
    owned.sort(key=lambda item: item[1].name)
    return owned


def active_bait_summary(
    equipped_bait_id: Optional[str],
    bait_inventory: Dict[str, int],
    bait_by_id: Dict[str, BaitDefinition],
    format_bait_stats,
) -> tuple[str, str]:
    if not equipped_bait_id:
        return "Nenhuma", ""
    bait = bait_by_id.get(equipped_bait_id)
    quantity = bait_inventory.get(equipped_bait_id, 0)
    if bait is None or quantity <= 0:
        return "Nenhuma", ""
    return f"{bait.name} x{quantity}", format_bait_stats(bait)


def active_cosmetics_summary(
    cosmetics_state: PlayerCosmeticsState,
) -> tuple[str, str]:
    color_def = UI_COLOR_DEFINITIONS.get(cosmetics_state.equipped_ui_color)
    icon_def = UI_ICON_DEFINITIONS.get(cosmetics_state.equipped_ui_icon)
    color_label = color_def.name if color_def is not None else cosmetics_state.equipped_ui_color
    icon_label = icon_def.name if icon_def is not None else cosmetics_state.equipped_ui_icon
    return color_label, icon_label
