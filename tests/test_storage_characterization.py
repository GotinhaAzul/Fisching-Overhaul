from __future__ import annotations

import pytest

from utils.inventory import InventoryEntry, calculate_entry_value
from utils.storage import get_storage_value, move_to_inventory, move_to_storage


def test_move_to_storage_returns_updated_collections() -> None:
    inventory = [
        InventoryEntry(name="Tilapia", rarity="Comum", kg=2.0, base_value=10.0),
        InventoryEntry(name="Pacu", rarity="Raro", kg=3.5, base_value=18.0),
    ]
    storage = [
        InventoryEntry(name="Dourado", rarity="Epico", kg=5.0, base_value=40.0),
    ]

    new_inventory, new_storage = move_to_storage(inventory, storage, 1)

    assert [entry.name for entry in new_inventory] == ["Tilapia"]
    assert [entry.name for entry in new_storage] == ["Dourado", "Pacu"]
    assert [entry.name for entry in inventory] == ["Tilapia", "Pacu"]
    assert [entry.name for entry in storage] == ["Dourado"]


def test_move_to_inventory_returns_updated_collections() -> None:
    storage = [
        InventoryEntry(name="Dourado", rarity="Epico", kg=5.0, base_value=40.0),
        InventoryEntry(name="Pirarucu", rarity="Lendario", kg=20.0, base_value=150.0),
    ]
    inventory = [
        InventoryEntry(name="Tilapia", rarity="Comum", kg=2.0, base_value=10.0),
    ]

    new_storage, new_inventory = move_to_inventory(storage, inventory, 0)

    assert [entry.name for entry in new_storage] == ["Pirarucu"]
    assert [entry.name for entry in new_inventory] == ["Tilapia", "Dourado"]
    assert [entry.name for entry in storage] == ["Dourado", "Pirarucu"]
    assert [entry.name for entry in inventory] == ["Tilapia"]


def test_storage_operations_raise_for_invalid_index() -> None:
    inventory = [InventoryEntry(name="Tilapia", rarity="Comum", kg=2.0, base_value=10.0)]

    with pytest.raises(IndexError):
        move_to_storage(inventory, [], 5)

    with pytest.raises(IndexError):
        move_to_inventory([], inventory, 0)


def test_get_storage_value_sums_estimated_sale_value() -> None:
    entries = [
        InventoryEntry(name="Tilapia", rarity="Comum", kg=2.0, base_value=10.0),
        InventoryEntry(
            name="Pirarucu",
            rarity="Lendario",
            kg=20.0,
            base_value=150.0,
            mutation_name="Noir",
            mutation_gold_multiplier=1.3,
        ),
    ]

    expected = sum(calculate_entry_value(entry) for entry in entries)
    assert get_storage_value(entries) == expected
