from dataclasses import dataclass
from typing import Dict, List, Optional

from rich.text import Text

from utils.modern_ui import console


RARITY_COLORS: Dict[str, str] = {
    "Comum": "#98FB98",
    "Incomum": "#66CDAA",
    "Raro": "#6CA6CD",
    "Epico": "#B4A7D6",
    "Lendario": "#F4D58D",
    "Mitico": "#B56CFF",
    "Secreto": "#A8A8A8",
    "Apex": "#F08080",
}


@dataclass
class InventoryEntry:
    name: str
    rarity: str
    kg: float
    base_value: float
    is_shiny: bool = False
    mutation_name: Optional[str] = None
    mutation_xp_multiplier: float = 1.0
    mutation_gold_multiplier: float = 1.0
    is_hunt: bool = False
    is_unsellable: bool = False


def calculate_entry_value(entry: InventoryEntry, *, shiny_multiplier: float = 1.55) -> float:
    base_total = entry.base_value * (entry.kg / 100 + 1)
    multiplier = entry.mutation_gold_multiplier
    if entry.is_shiny:
        multiplier *= shiny_multiplier
    return base_total * multiplier


def format_inventory_entry(
    index: int,
    entry: InventoryEntry,
    hunt_fish_names: Optional[set[str]] = None,
) -> str:
    color = RARITY_COLORS.get(entry.rarity, "#F0F0F0")
    is_hunt_entry = entry.is_hunt or (
        bool(hunt_fish_names) and entry.name in hunt_fish_names
    )
    fish_name_color = "#FF6666" if is_hunt_entry else color
    shiny_label = " ✦ Shiny" if entry.is_shiny else ""
    mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
    unsellable_label = " [bold red][Unsellable][/bold red]" if entry.is_unsellable else ""
    return (
        f"[{color}]\\[{entry.rarity}] "
        f"[{fish_name_color}]{entry.name}[/] "
        f"[{color}]({entry.kg:0.2f}kg){shiny_label}{mutation_label}[/]"
        f"{unsellable_label}"
    )


def render_inventory(
    inventory: List[InventoryEntry],
    show_title: bool = True,
    hunt_fish_names: Optional[set[str]] = None,
    start_index: int = 1,
):
    if show_title:
        console.print("\n[bold]Inventário:[/bold]")
    if not inventory:
        console.print("[dim]- vazio -[/dim]")
        return
    for idx, entry in enumerate(inventory, start=start_index):
        console.print(f"{idx}. {format_inventory_entry(idx, entry, hunt_fish_names=hunt_fish_names)}")
