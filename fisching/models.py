from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class Fish:
    name: str
    rarity: str


@dataclass
class Player:
    name: str
    inventory: Dict[str, int] = field(default_factory=dict)

    def add_item(self, item_name: str, amount: int = 1) -> None:
        self.inventory[item_name] = self.inventory.get(item_name, 0) + amount
