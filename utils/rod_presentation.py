from __future__ import annotations

from utils.rods import Rod


def format_rod_abilities(rod: Rod) -> str:
    parts: list[str] = []

    if rod.can_slash and rod.slash_chance > 0 and rod.slash_power > 0:
        parts.append(f"Slash {rod.slash_chance:.0%} x{rod.slash_power}")
    if rod.can_slam and rod.slam_chance > 0 and rod.slam_time_bonus > 0:
        parts.append(f"Slam {rod.slam_chance:.0%} +{rod.slam_time_bonus:0.2f}s")
    if rod.can_curse and rod.curse_chance > 0 and rod.curse_time_penalty > 0:
        parts.append(f"Curse {rod.curse_chance:.0%} -{rod.curse_time_penalty:0.2f}s")
    if rod.can_recover and rod.recover_chance > 0:
        parts.append(f"Recover {rod.recover_chance:.0%}")
    if rod.can_pierce and rod.pierce_chance > 0:
        parts.append(f"Pierce {rod.pierce_chance:.0%}")
    if rod.can_dupe and rod.dupe_chance > 0:
        parts.append(f"Dupe {rod.dupe_chance:.0%}")
    if rod.can_frenzy and rod.frenzy_chance > 0:
        parts.append(f"Frenzy {rod.frenzy_chance:.0%}")
    if rod.can_greed and rod.greed_chance > 0:
        parts.append(f"Greed {rod.greed_chance:.0%}")
    if rod.can_alter and (rod.timecount != 0 or rod.hardcount != 0):
        alter_parts: list[str] = []
        if rod.timecount != 0:
            alter_parts.append(f"Time {rod.timecount:+.0f}%")
        if rod.hardcount != 0:
            alter_parts.append(f"Keys {rod.hardcount:+.0f}%")
        parts.append(f"Alter {' '.join(alter_parts)}")

    return " | ".join(parts) if parts else "-"
