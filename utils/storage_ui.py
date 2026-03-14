from __future__ import annotations

from typing import Optional, Sequence

from utils.inventory import InventoryEntry, calculate_entry_value, format_inventory_entry
from utils.market import format_currency
from utils.modern_ui import MenuOption, print_menu_panel
from utils.pagination import PAGE_NEXT_KEY, PAGE_PREV_KEY, PageSlice, get_page_slice
from utils.storage import get_storage_value


STORAGE_PAGE_SIZE = 10


def render_storage(
    storage: Sequence[InventoryEntry],
    *,
    page: int = 0,
    hunt_fish_names: Optional[set[str]] = None,
    shiny_multiplier: float = 1.55,
    shiny_label_text: str = "✦ Shiny",
    shiny_color: str = "#FFD700",
) -> PageSlice:
    page_slice = get_page_slice(len(storage), page, STORAGE_PAGE_SIZE)
    page_entries = storage[page_slice.start:page_slice.end]
    total_value = get_storage_value(list(storage), shiny_multiplier=shiny_multiplier)

    header_lines = [
        (
            f"Peixes guardados: {len(storage)} | "
            f"Valor estimado: ~{format_currency(total_value)}"
        ),
    ]
    if page_slice.total_pages > 1:
        header_lines.append(
            f"Pagina {page_slice.page + 1}/{page_slice.total_pages}"
        )
    header_lines.append("")

    if not page_entries:
        header_lines.append("[dim]Storage vazio.[/dim]")
    else:
        for display_index, entry in enumerate(page_entries, start=1):
            absolute_index = page_slice.start + display_index
            header_lines.append(
                f"{display_index}. "
                f"{format_inventory_entry(
                    absolute_index,
                    entry,
                    hunt_fish_names=hunt_fish_names,
                    shiny_label_text=shiny_label_text,
                    shiny_color=shiny_color,
                )}"
            )
            mutation_label = entry.mutation_name if entry.mutation_name else "Sem mutacao"
            header_lines.append(
                f"[dim]   {mutation_label} | "
                f"Val: ~{format_currency(calculate_entry_value(entry, shiny_multiplier=shiny_multiplier))}[/dim]"
            )

    options = [
        MenuOption("N", "Guardar do inventario", enabled=True),
        MenuOption("R", "Retirar para o inventario", enabled=bool(storage)),
    ]
    if page_slice.total_pages > 1:
        options.extend(
            [
                MenuOption(
                    PAGE_NEXT_KEY.upper(),
                    "Proxima pagina",
                    f"Storage {page_slice.page + 1}/{page_slice.total_pages}",
                    enabled=page_slice.has_next,
                ),
                MenuOption(
                    PAGE_PREV_KEY.upper(),
                    "Pagina anterior",
                    f"Storage {page_slice.page + 1}/{page_slice.total_pages}",
                    enabled=page_slice.has_prev,
                ),
            ]
        )
    options.append(MenuOption("0", "Voltar"))

    print_menu_panel(
        "STORAGE",
        subtitle="Peixes guardados",
        header_lines=header_lines,
        options=options,
        prompt="Escolha uma opcao:",
        show_badge=False,
        width=76,
    )
    return page_slice
