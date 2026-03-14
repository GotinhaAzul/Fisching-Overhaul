from __future__ import annotations

from typing import List

from utils.inventory import InventoryEntry, calculate_entry_value


def move_to_storage(
    inventory: List[InventoryEntry],
    storage: List[InventoryEntry],
    index: int,
) -> tuple[List[InventoryEntry], List[InventoryEntry]]:
    if index < 0 or index >= len(inventory):
        raise IndexError(
            f"Indice {index} invalido para inventario de tamanho {len(inventory)}"
        )

    fish = inventory[index]
    new_inventory = [entry for i, entry in enumerate(inventory) if i != index]
    new_storage = storage + [fish]
    return new_inventory, new_storage


def move_to_inventory(
    storage: List[InventoryEntry],
    inventory: List[InventoryEntry],
    index: int,
) -> tuple[List[InventoryEntry], List[InventoryEntry]]:
    if index < 0 or index >= len(storage):
        raise IndexError(
            f"Indice {index} invalido para storage de tamanho {len(storage)}"
        )

    fish = storage[index]
    new_storage = [entry for i, entry in enumerate(storage) if i != index]
    new_inventory = inventory + [fish]
    return new_storage, new_inventory


def get_storage_value(
    storage: List[InventoryEntry],
    *,
    shiny_multiplier: float = 1.55,
) -> float:
    return sum(
        calculate_entry_value(entry, shiny_multiplier=shiny_multiplier)
        for entry in storage
    )
