from __future__ import annotations

from typing import Dict, List


class Inventory:
    def __init__(self, items: Dict[str, int] | None = None) -> None:
        self._items: Dict[str, int] = dict(items or {})

    def add(self, item_name: str, amount: int = 1) -> None:
        self._items[item_name] = self._items.get(item_name, 0) + amount

    def to_lines(self) -> List[str]:
        if not self._items:
            return ["(vazio)"]
        return [f"- {name}: {count}" for name, count in sorted(self._items.items())]

    def as_dict(self) -> Dict[str, int]:
        return dict(self._items)
