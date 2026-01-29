from __future__ import annotations

from typing import List

from fisching.models import CaughtFish
from fisching.utils import calculate_fish_value


class Inventory:
    def __init__(self, items: list[CaughtFish] | None = None) -> None:
        self._items = items if items is not None else []

    def add(self, catch: CaughtFish) -> None:
        self._items.append(catch)

    def remove(self, index: int) -> CaughtFish:
        return self._items.pop(index)

    def clear(self) -> None:
        self._items.clear()

    def list(self) -> list[CaughtFish]:
        return list(self._items)

    def total_value(self) -> float:
        return sum(
            calculate_fish_value(catch.base_value, catch.weight_kg) for catch in self._items
        )

    def to_lines(self) -> List[str]:
        if not self._items:
            return ["(vazio)"]
        lines = []
        for index, catch in enumerate(self._items, start=1):
            value = calculate_fish_value(catch.base_value, catch.weight_kg)
            lines.append(
                f"{index}) {catch.name} - {catch.weight_kg:.2f} kg - {value:.2f} moedas"
            )
        return lines
