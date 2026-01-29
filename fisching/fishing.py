from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from fisching.models import Fish

SEQUENCE_KEYS = ("W", "A", "S", "D")


@dataclass(frozen=True)
class CatchResult:
    success: bool
    fish: Fish | None
    sequence: Sequence[str]


class FishingSystem:
    def __init__(self, sequence_length: int = 4) -> None:
        self.sequence_length = sequence_length
        self._fish_table: List[Fish] = [
            Fish("Tilápia", "comum"),
            Fish("Lambari", "comum"),
            Fish("Dourado", "raro"),
            Fish("Pintado", "raro"),
            Fish("Piracanjuba", "lendário"),
        ]
        self._rarity_weights = [0.4, 0.4, 0.15, 0.04, 0.01]

    def generate_sequence(self) -> List[str]:
        return [random.choice(SEQUENCE_KEYS) for _ in range(self.sequence_length)]

    def resolve_attempt(self, sequence: Sequence[str], provided: Iterable[str]) -> CatchResult:
        normalized_input = [value.strip().upper() for value in provided if value.strip()]
        success = normalized_input == list(sequence)
        fish = random.choices(self._fish_table, weights=self._rarity_weights, k=1)[0] if success else None
        return CatchResult(success=success, fish=fish, sequence=sequence)
