from __future__ import annotations

from typing import Callable, Dict, Mapping, Optional, Sequence, Set


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_str(value: object, *, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback


def fish_name_matches(actual_name: str, expected_name: str) -> bool:
    return actual_name.casefold() == expected_name.casefold()


def count_name_case_insensitive(counts: Mapping[str, int], name: str) -> int:
    normalized_name = name.casefold()
    return sum(
        count
        for key, count in counts.items()
        if key.casefold() == normalized_name
    )


def fish_mutation_key(fish_name: str, mutation_name: str) -> str:
    return f"{fish_name}::{mutation_name}"


def count_fish_mutation_pair(
    counts: Mapping[str, int],
    *,
    fish_name: Optional[str],
    mutation_name: Optional[str],
    mutation_case_insensitive: bool = False,
) -> int:
    normalized_fish_name = fish_name.casefold() if fish_name else None
    normalized_mutation_name = mutation_name.casefold() if mutation_case_insensitive and mutation_name else None
    total = 0
    for pair_key, count in counts.items():
        fish_part, separator, mutation_part = pair_key.partition("::")
        if separator != "::":
            continue
        if normalized_fish_name and fish_part.casefold() != normalized_fish_name:
            continue
        if mutation_name:
            if mutation_case_insensitive:
                if mutation_part.casefold() != normalized_mutation_name:
                    continue
            elif mutation_part != mutation_name:
                continue
        total += count
    return total


def seconds_from_requirement(
    requirement: Dict[str, object],
    *,
    clamp_non_negative: bool = False,
) -> float:
    if "seconds" in requirement:
        value = safe_float(requirement.get("seconds"))
    elif "minutes" in requirement:
        value = safe_float(requirement.get("minutes")) * 60
    elif "hours" in requirement:
        value = safe_float(requirement.get("hours")) * 3600
    else:
        value = safe_float(requirement.get("time_seconds"))
    return max(0.0, value) if clamp_non_negative else value


def pool_counts_for_bestiary_completion(pool: object) -> bool:
    return bool(getattr(pool, "counts_for_bestiary_completion", True))


def fish_counts_for_bestiary_completion(fish: object) -> bool:
    return bool(getattr(fish, "counts_for_bestiary_completion", True))


def collect_countable_fish_names(
    pools: Sequence[object],
    *,
    pool_filter: Optional[Callable[[object], bool]] = None,
) -> Set[str]:
    fish_names: Set[str] = set()
    for pool in pools:
        if pool_filter is not None and not pool_filter(pool):
            continue
        if not pool_counts_for_bestiary_completion(pool):
            continue
        for fish in getattr(pool, "fish_profiles", []):
            fish_name = safe_str(getattr(fish, "name", ""))
            if fish_name and fish_counts_for_bestiary_completion(fish):
                fish_names.add(fish_name)
    return fish_names


def completion_percent(
    fish_names: Set[str],
    discovered_fish: Set[str],
) -> float:
    if not fish_names:
        return 0.0
    discovered = sum(1 for fish_name in fish_names if fish_name in discovered_fish)
    return (discovered / len(fish_names)) * 100

