from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class Fish:
    name: str
    rarity: str
    weight_kg_min: float
    weight_kg_max: float
    base_value: int
    resilience: int
    description: str


@dataclass(frozen=True)
class CaughtFish:
    name: str
    weight_kg: float
    base_value: int


@dataclass(frozen=True)
class Pool:
    name: str
    description: str
    fish: Dict[str, Fish]
    rarity_chances: Dict[str, float]


@dataclass
class Player:
    name: str
    inventory: list[CaughtFish] = field(default_factory=list)
    balance: float = 0.0

    def add_catch(self, catch: CaughtFish) -> None:
        self.inventory.append(catch)

    def add_money(self, amount: float) -> None:
        self.balance += amount
