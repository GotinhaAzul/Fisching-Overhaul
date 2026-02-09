from __future__ import annotations

from typing import Dict, Tuple


BASE_XP_REQUIREMENT = 100
XP_GROWTH_RATE = 1.35

RARITY_XP: Dict[str, int] = {
    "Comum": 10,
    "Incomum": 20,
    "Raro": 35,
    "Epico": 60,
    "Lendario": 100,
}


def xp_required_for_level(level: int) -> int:
    if level <= 1:
        return BASE_XP_REQUIREMENT
    return int(BASE_XP_REQUIREMENT * (XP_GROWTH_RATE ** (level - 1)))


def xp_for_rarity(rarity: str) -> int:
    return RARITY_XP.get(rarity, RARITY_XP["Comum"])


def apply_xp_gain(level: int, xp: int, gained_xp: int) -> Tuple[int, int, int]:
    if gained_xp <= 0:
        return level, xp, 0

    remaining_xp = xp + gained_xp
    level_ups = 0

    while remaining_xp >= xp_required_for_level(level):
        remaining_xp -= xp_required_for_level(level)
        level += 1
        level_ups += 1

    return level, remaining_xp, level_ups
