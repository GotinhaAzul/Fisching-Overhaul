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
    is_hunt: bool = False


def calculate_entry_value(entry: InventoryEntry) -> float:
    base_total = entry.base_value * (entry.kg / 100 + 1)
    return base_total * entry.mutation_gold_multiplier


def format_inventory_entry(
    index: int,
    entry: InventoryEntry,
    hunt_fish_names: Optional[set[str]] = None,
) -> str:
    color = RARITY_COLORS.get(entry.rarity, Fore.WHITE)
    is_hunt_entry = entry.is_hunt or (
        bool(hunt_fish_names) and entry.name in hunt_fish_names
    )
    fish_name_color = Fore.RED if is_hunt_entry else color
    mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
    return (
        f"{index}. {color}[{entry.rarity}] "
        f"{fish_name_color}{entry.name}{color} "
        f"({entry.kg:0.2f}kg){mutation_label}{Style.RESET_ALL}"
    )


def render_inventory(
    inventory: List[InventoryEntry],
    show_title: bool = True,
    hunt_fish_names: Optional[set[str]] = None,
    start_index: int = 1,
):
    if show_title:
        print("\nInventário:")
    if not inventory:
        print("- vazio -")
        return
    for idx, entry in enumerate(inventory, start=start_index):
        print(format_inventory_entry(idx, entry, hunt_fish_names=hunt_fish_names))
