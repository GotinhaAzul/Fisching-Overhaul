from dataclasses import dataclass
from typing import Dict, List, Optional

from colorama import Fore, Style


RARITY_COLORS: Dict[str, str] = {
    "Comum": Fore.LIGHTGREEN_EX,
    "Incomum": Fore.GREEN,
    "Raro": Fore.LIGHTBLUE_EX,
    "Epico": Fore.MAGENTA,
    "Lendario": Fore.YELLOW,
    "Secreto": Fore.LIGHTBLACK_EX,
    "Apex": Fore.LIGHTRED_EX,
}


@dataclass
class InventoryEntry:
    name: str
    rarity: str
    kg: float
    base_value: float
    mutation_name: Optional[str] = None
    mutation_xp_multiplier: float = 1.0
    mutation_gold_multiplier: float = 1.0


def calculate_entry_value(entry: InventoryEntry) -> float:
    base_total = entry.base_value * (entry.kg / 100 + 1)
    return base_total * entry.mutation_gold_multiplier


def format_inventory_entry(index: int, entry: InventoryEntry) -> str:
    color = RARITY_COLORS.get(entry.rarity, Fore.WHITE)
    mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
    return (
        f"{index}. {color}[{entry.rarity}] {entry.name} "
        f"({entry.kg:0.2f}kg){mutation_label}{Style.RESET_ALL}"
    )


def render_inventory(inventory: List[InventoryEntry], show_title: bool = True):
    if show_title:
        print("\nInventário:")
    if not inventory:
        print("- vazio -")
        return
    for idx, entry in enumerate(inventory, start=1):
        print(format_inventory_entry(idx, entry))
