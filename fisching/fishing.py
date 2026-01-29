from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from fisching.models import Fish, Pool

SEQUENCE_KEYS = ("W", "A", "S", "D")


@dataclass(frozen=True)
class CatchResult:
    success: bool
    fish: Fish | None
    sequence: Sequence[str]


class FishingSystem:
    def __init__(self, sequence_length: int = 6, min_sequence_length: int = 2) -> None:
        self.sequence_length = sequence_length
        self.min_sequence_length = min_sequence_length

    def choose_fish(self, pool: Pool) -> Fish:
        if not pool.fish:
            raise ValueError("Pool sem peixes disponíveis.")

        rarity_groups: dict[str, list[Fish]] = {}
        for fish in pool.fish.values():
            rarity_groups.setdefault(fish.rarity.lower(), []).append(fish)

        rarities = list(pool.rarity_chances.keys())
        rarity_weights = [pool.rarity_chances[rarity] for rarity in rarities]

        while True:
            chosen_rarity = random.choices(rarities, weights=rarity_weights, k=1)[0]
            candidates = rarity_groups.get(chosen_rarity.lower())
            if candidates:
                return random.choice(candidates)

    def sequence_length_for_fish(self, fish: Fish) -> int:
        return max(self.min_sequence_length, self.sequence_length - fish.resilience)

    def generate_sequence(self, length: int) -> List[str]:
        return [random.choice(SEQUENCE_KEYS) for _ in range(length)]

    def resolve_attempt(self, sequence: Sequence[str], provided: Iterable[str], fish: Fish) -> CatchResult:
        normalized_input = [value.strip().upper() for value in provided if value.strip()]
        success = normalized_input == list(sequence)
        caught = fish if success else None
        return CatchResult(success=success, fish=caught, sequence=sequence)
