from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, TYPE_CHECKING

from colorama import Fore, Style

from utils.menu_input import read_menu_choice
from utils.modern_ui import MenuOption, print_menu_panel, use_modern_ui
from utils.pagination import (
    PAGE_NEXT_KEY,
    PAGE_PREV_KEY,
    apply_page_hotkey,
    get_page_slice,
)
from utils.rods import Rod
from utils.ui import clear_screen, print_spaced_lines

if TYPE_CHECKING:
    from utils.hunts import HuntDefinition
    from utils.pesca import FishProfile, FishingPool


REGIONLESS_SECTION_NAME = "Sem regiao"


def _read_choice(prompt: str, total_pages: int) -> str:
    return read_menu_choice(
        prompt,
        instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if total_pages > 1 else set(),
    ).lower()


@dataclass(frozen=True)
class FishBestiarySection:
    title: str
    fish_profiles: List["FishProfile"]
    completion_fish_names: Set[str]
    locked: bool = False
    counts_for_completion: bool = True


def _pool_counts_for_completion(pool: "FishingPool") -> bool:
    return bool(getattr(pool, "counts_for_bestiary_completion", True))


def _pool_hidden_until_unlocked(pool: "FishingPool") -> bool:
    return bool(getattr(pool, "hidden_from_bestiary_until_unlocked", False))


def _fish_counts_for_completion(fish: "FishProfile") -> bool:
    return bool(getattr(fish, "counts_for_bestiary_completion", True))


def build_fish_bestiary_sections(
    pools: Sequence["FishingPool"],
    unlocked_pools: Set[str],
    hunt_definitions: Optional[Sequence["HuntDefinition"]] = None,
    regionless_fish_profiles: Optional[Sequence["FishProfile"]] = None,
) -> List[FishBestiarySection]:
    hunt_fish_by_pool: Dict[str, Dict[str, FishProfile]] = {}
    for hunt in hunt_definitions or []:
        by_name = hunt_fish_by_pool.setdefault(hunt.pool_name, {})
        for fish in hunt.fish_profiles:
            by_name.setdefault(fish.name, fish)

    sections: List[FishBestiarySection] = []
    for pool in sorted(pools, key=lambda pool: pool.name):
        pool_locked = pool.name not in unlocked_pools
        if _pool_hidden_until_unlocked(pool) and pool_locked:
            continue

        fish_by_name: Dict[str, FishProfile] = {}
        completion_fish_names: Set[str] = set()
        for fish in pool.fish_profiles:
            fish_by_name.setdefault(fish.name, fish)
            if _pool_counts_for_completion(pool) and _fish_counts_for_completion(fish):
                completion_fish_names.add(fish.name)
        for fish_name, fish in sorted(hunt_fish_by_pool.get(pool.name, {}).items()):
            fish_by_name.setdefault(fish_name, fish)

        sections.append(
            FishBestiarySection(
                title=pool.name,
                fish_profiles=[fish_by_name[name] for name in sorted(fish_by_name)],
                completion_fish_names=completion_fish_names,
                locked=pool_locked,
                counts_for_completion=_pool_counts_for_completion(pool),
            )
        )

    regionless_by_name: Dict[str, FishProfile] = {}
    for fish in regionless_fish_profiles or []:
        regionless_by_name.setdefault(fish.name, fish)
    if regionless_by_name:
        sections.append(
            FishBestiarySection(
                title=REGIONLESS_SECTION_NAME,
                fish_profiles=[
                    regionless_by_name[name]
                    for name in sorted(regionless_by_name)
                ],
                completion_fish_names=set(regionless_by_name),
            )
        )

    return sections


def _section_completion(
    section: FishBestiarySection,
    unlocked_fish: Set[str],
) -> tuple[int, int, float]:
    if not section.counts_for_completion:
        return 0, 0, 0.0
    total = len(section.completion_fish_names)
    unlocked_count = sum(
        1
        for fish_name in section.completion_fish_names
        if fish_name in unlocked_fish
    )
    completion = (unlocked_count / total * 100) if total else 0
    return unlocked_count, total, completion


def _fish_label(
    fish: "FishProfile",
    unlocked_fish: Set[str],
    completion_fish_names: Set[str],
) -> str:
    if fish.name not in unlocked_fish:
        return "???"
    if fish.name not in completion_fish_names:
        return f"{fish.name} {Fore.RED}(Hunt){Style.RESET_ALL}"
    return fish.name


def show_locked_entry():
    clear_screen()
    if use_modern_ui():
        print_menu_panel(
            "BESTIARIO",
            subtitle="Entrada bloqueada",
            header_lines=["Informacoes ainda nao desbloqueadas."],
            options=[MenuOption("0", "Voltar")],
            prompt="Pressione 0 ou Enter para voltar:",
            show_badge=False,
        )
        input("> ")
        return
    print("???")
    print("\nInformações ainda não desbloqueadas.")
    input("\nEnter para voltar.")


def _rod_counts_for_completion(rod: Rod) -> bool:
    return bool(getattr(rod, "counts_for_bestiary_completion", True))


def _show_fish_bestiary_flat(
    fish_profiles: List["FishProfile"],
    unlocked_fish: Set[str],
):
    ordered_fish = sorted(
        fish_profiles,
        key=lambda fish: (fish.name not in unlocked_fish, fish.name),
    )
    page = 0
    page_size = 10
    while True:
        clear_screen()
        print("=== Bestiario: Peixes pescados ===")
        total_fish = len(fish_profiles)
        unlocked_count = sum(1 for fish in fish_profiles if fish.name in unlocked_fish)
        completion = (unlocked_count / total_fish * 100) if total_fish else 0
        print(f"Complecao: {unlocked_count}/{total_fish} ({completion:.0f}%)")
        if not ordered_fish:
            print("Nenhum peixe cadastrado.")
            input("\nEnter para voltar.")
            return

        page_slice = get_page_slice(len(ordered_fish), page, page_size)
        page = page_slice.page
        total_pages = page_slice.total_pages
        start = page_slice.start
        end = page_slice.end
        page_items = ordered_fish[start:end]
        if use_modern_ui():
            clear_screen()
            options = [
                MenuOption(str(idx), fish.name if fish.name in unlocked_fish else "???")
                for idx, fish in enumerate(page_items, start=1)
            ]
            if total_pages > 1:
                options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina"))
                options.append(MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior"))
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "BESTIARIO",
                subtitle="Peixes pescados",
                header_lines=[
                    f"Conclusao: {unlocked_count}/{total_fish} ({completion:.0f}%)",
                    f"Pagina {page + 1}/{total_pages}",
                ],
                options=options,
                prompt="Escolha um peixe:",
                show_badge=False,
            )
            choice = _read_choice("> ", total_pages)
            if choice == "0":
                return

            page, moved = apply_page_hotkey(choice, page, total_pages)
            if moved:
                continue

            if not choice.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(choice)
            if not (1 <= idx <= len(page_items)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            fish = page_items[idx - 1]
            if fish.name not in unlocked_fish:
                show_locked_entry()
                continue

            clear_screen()
            print_menu_panel(
                "PEIXE",
                subtitle=fish.name,
                header_lines=[
                    f"Raridade: {fish.rarity}",
                    f"Descricao: {fish.description or '-'}",
                    f"KG (min-max): {fish.kg_min:g} - {fish.kg_max:g}",
                ],
                options=[MenuOption("0", "Voltar")],
                prompt="Pressione Enter para voltar:",
                show_badge=False,
            )
            input("> ")
            continue

        print(f"Pagina {page + 1}/{total_pages}\n")

        for idx, fish in enumerate(page_items, start=1):
            label = fish.name if fish.name in unlocked_fish else "???"
            print(f"{idx}. {label}")

        if total_pages > 1:
            print(
                f"\n{PAGE_PREV_KEY.upper()}. Pagina anterior | "
                f"{PAGE_NEXT_KEY.upper()}. Proxima pagina"
            )
        print("0. Voltar")
        choice = _read_choice("Escolha um peixe: ", total_pages)
        if choice == "0":
            return

        page, moved = apply_page_hotkey(choice, page, total_pages)
        if moved:
            continue

        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        fish = page_items[idx - 1]
        if fish.name not in unlocked_fish:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {fish.name} ===")
        print(f"Raridade: {fish.rarity}")
        print(f"Descricao: {fish.description or '-'}")
        print(f"KG (min-max): {fish.kg_min:g} - {fish.kg_max:g}")
        input("\nEnter para voltar.")


def _show_fish_bestiary_section(
    section: FishBestiarySection,
    unlocked_fish: Set[str],
) -> None:
    ordered_fish = sorted(
        section.fish_profiles,
        key=lambda fish: (fish.name not in unlocked_fish, fish.name),
    )
    page = 0
    page_size = 10
    has_hunt_only_fish = any(
        fish.name not in section.completion_fish_names
        for fish in section.fish_profiles
    )
    while True:
        clear_screen()
        print(f"=== Bestiario: {section.title} ===")
        unlocked_count, total_fish, completion = _section_completion(
            section,
            unlocked_fish,
        )
        if section.counts_for_completion:
            print(f"Complecao: {unlocked_count}/{total_fish} ({completion:.0f}%)")
        else:
            print("Esta pool nao conta para a complecao do bestiario.")
        if has_hunt_only_fish:
            print("Peixes [Hunt] nao contam para a complecao da pool.")
        if not ordered_fish:
            print("Nenhum peixe cadastrado.")
            input("\nEnter para voltar.")
            return

        page_slice = get_page_slice(len(ordered_fish), page, page_size)
        page = page_slice.page
        total_pages = page_slice.total_pages
        start = page_slice.start
        end = page_slice.end
        page_items = ordered_fish[start:end]
        if use_modern_ui():
            clear_screen()
            if section.counts_for_completion:
                header_lines = [
                    f"Conclusao: {unlocked_count}/{total_fish} ({completion:.0f}%)",
                    f"Pagina {page + 1}/{total_pages}",
                ]
            else:
                header_lines = [
                    "Esta pool nao conta para a complecao do bestiario.",
                    f"Pagina {page + 1}/{total_pages}",
                ]
            if has_hunt_only_fish:
                header_lines.append("Peixes [Hunt] nao contam para a complecao.")
            options = [
                MenuOption(
                    str(idx),
                    _fish_label(fish, unlocked_fish, section.completion_fish_names),
                )
                for idx, fish in enumerate(page_items, start=1)
            ]
            if total_pages > 1:
                options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina"))
                options.append(MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior"))
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "BESTIARIO",
                subtitle=section.title,
                header_lines=header_lines,
                options=options,
                prompt="Escolha um peixe:",
                show_badge=False,
            )
            choice = _read_choice("> ", total_pages)
            if choice == "0":
                return

            page, moved = apply_page_hotkey(choice, page, total_pages)
            if moved:
                continue

            if not choice.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(choice)
            if not (1 <= idx <= len(page_items)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            fish = page_items[idx - 1]
            if fish.name not in unlocked_fish:
                show_locked_entry()
                continue

            detail_lines = [
                f"Raridade: {fish.rarity}",
                f"Descricao: {fish.description or '-'}",
                f"KG (min-max): {fish.kg_min:g} - {fish.kg_max:g}",
            ]
            if fish.name not in section.completion_fish_names:
                detail_lines.append("Origem: Hunt (nao conta para complecao)")

            clear_screen()
            print_menu_panel(
                "PEIXE",
                subtitle=fish.name,
                header_lines=detail_lines,
                options=[MenuOption("0", "Voltar")],
                prompt="Pressione Enter para voltar:",
                show_badge=False,
            )
            input("> ")
            continue

        print(f"Pagina {page + 1}/{total_pages}\n")

        for idx, fish in enumerate(page_items, start=1):
            print(
                f"{idx}. {_fish_label(fish, unlocked_fish, section.completion_fish_names)}"
            )

        if total_pages > 1:
            print(
                f"\n{PAGE_PREV_KEY.upper()}. Pagina anterior | "
                f"{PAGE_NEXT_KEY.upper()}. Proxima pagina"
            )
        print("0. Voltar")
        choice = _read_choice("Escolha um peixe: ", total_pages)
        if choice == "0":
            return

        page, moved = apply_page_hotkey(choice, page, total_pages)
        if moved:
            continue

        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        fish = page_items[idx - 1]
        if fish.name not in unlocked_fish:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {fish.name} ===")
        print(f"Raridade: {fish.rarity}")
        print(f"Descricao: {fish.description or '-'}")
        print(f"KG (min-max): {fish.kg_min:g} - {fish.kg_max:g}")
        if fish.name not in section.completion_fish_names:
            print("Origem: Hunt (nao conta para complecao)")
        input("\nEnter para voltar.")


def show_fish_bestiary(
    sections: List[FishBestiarySection],
    unlocked_fish: Set[str],
):
    page = 0
    page_size = 10
    completion_fish_names = {
        fish_name
        for section in sections
        if section.counts_for_completion
        for fish_name in section.completion_fish_names
    }
    while True:
        clear_screen()
        print("=== Bestiario: Peixes por pool ===")
        total_fish = len(completion_fish_names)
        unlocked_count = sum(
            1
            for fish_name in completion_fish_names
            if fish_name in unlocked_fish
        )
        completion = (unlocked_count / total_fish * 100) if total_fish else 0
        print(f"Complecao: {unlocked_count}/{total_fish} ({completion:.0f}%)")
        if not sections:
            print("Nenhuma secao cadastrada.")
            input("\nEnter para voltar.")
            return

        page_slice = get_page_slice(len(sections), page, page_size)
        page = page_slice.page
        total_pages = page_slice.total_pages
        start = page_slice.start
        end = page_slice.end
        page_items = sections[start:end]
        if use_modern_ui():
            clear_screen()
            options: List[MenuOption] = []
            for idx, section in enumerate(page_items, start=1):
                if section.locked:
                    label = "???"
                elif not section.counts_for_completion:
                    label = f"{section.title} (nao conta na complecao)"
                else:
                    section_unlocked, section_total, _ = _section_completion(
                        section,
                        unlocked_fish,
                    )
                    label = f"{section.title} ({section_unlocked}/{section_total})"
                options.append(MenuOption(str(idx), label))
            if total_pages > 1:
                options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina"))
                options.append(MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior"))
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "BESTIARIO",
                subtitle="Peixes por pool",
                header_lines=[
                    f"Conclusao: {unlocked_count}/{total_fish} ({completion:.0f}%)",
                    f"Pagina {page + 1}/{total_pages}",
                ],
                options=options,
                prompt="Escolha uma pool/regiao:",
                show_badge=False,
            )
            choice = _read_choice("> ", total_pages)
            if choice == "0":
                return

            page, moved = apply_page_hotkey(choice, page, total_pages)
            if moved:
                continue

            if not choice.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(choice)
            if not (1 <= idx <= len(page_items)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            section = page_items[idx - 1]
            if section.locked:
                show_locked_entry()
                continue

            _show_fish_bestiary_section(section, unlocked_fish)
            continue

        print(f"Pagina {page + 1}/{total_pages}\n")

        for idx, section in enumerate(page_items, start=1):
            if section.locked:
                label = "???"
            elif not section.counts_for_completion:
                label = f"{section.title} (nao conta na complecao)"
            else:
                section_unlocked, section_total, _ = _section_completion(
                    section,
                    unlocked_fish,
                )
                label = f"{section.title} ({section_unlocked}/{section_total})"
            print(f"{idx}. {label}")

        if total_pages > 1:
            print(
                f"\n{PAGE_PREV_KEY.upper()}. Pagina anterior | "
                f"{PAGE_NEXT_KEY.upper()}. Proxima pagina"
            )
        print("0. Voltar")
        choice = _read_choice("Escolha uma pool/regiao: ", total_pages)
        if choice == "0":
            return

        page, moved = apply_page_hotkey(choice, page, total_pages)
        if moved:
            continue

        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        section = page_items[idx - 1]
        if section.locked:
            show_locked_entry()
            continue

        _show_fish_bestiary_section(section, unlocked_fish)


def show_rods_bestiary(rods: List[Rod], unlocked_rods: Set[str]):
    countable_rods = [
        rod
        for rod in rods
        if _rod_counts_for_completion(rod)
    ]
    page = 0
    page_size = 10
    while True:
        clear_screen()
        print("=== Bestiario: Varas adquiridas ===")
        total_rods = len(countable_rods)
        unlocked_count = sum(1 for rod in countable_rods if rod.name in unlocked_rods)
        completion = (unlocked_count / total_rods * 100) if total_rods else 0
        print(f"Complecao: {unlocked_count}/{total_rods} ({completion:.0f}%)")
        if not rods:
            print("Nenhuma vara cadastrada.")
            input("\nEnter para voltar.")
            return

        page_slice = get_page_slice(len(rods), page, page_size)
        page = page_slice.page
        total_pages = page_slice.total_pages
        start = page_slice.start
        end = page_slice.end
        page_items = rods[start:end]
        if use_modern_ui():
            clear_screen()
            options = []
            for idx, rod in enumerate(page_items, start=1):
                if rod.name not in unlocked_rods:
                    label = "???"
                elif not _rod_counts_for_completion(rod):
                    label = f"{rod.name} (nao conta na complecao)"
                else:
                    label = rod.name
                options.append(MenuOption(str(idx), label))
            if total_pages > 1:
                options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina"))
                options.append(MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior"))
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "BESTIARIO",
                subtitle="Varas adquiridas",
                header_lines=[
                    f"Conclusao: {unlocked_count}/{total_rods} ({completion:.0f}%)",
                    f"Pagina {page + 1}/{total_pages}",
                ],
                options=options,
                prompt="Escolha uma vara:",
                show_badge=False,
            )
            choice = _read_choice("> ", total_pages)
            if choice == "0":
                return

            page, moved = apply_page_hotkey(choice, page, total_pages)
            if moved:
                continue

            if not choice.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(choice)
            if not (1 <= idx <= len(page_items)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            rod = page_items[idx - 1]
            if rod.name not in unlocked_rods:
                show_locked_entry()
                continue

            clear_screen()
            detail_lines = [f"Descricao: {rod.description or '-'}"]
            if not _rod_counts_for_completion(rod):
                detail_lines.append("Esta vara nao conta para a complecao do bestiario.")
            print_menu_panel(
                "VARA",
                subtitle=rod.name,
                header_lines=detail_lines,
                options=[MenuOption("0", "Voltar")],
                prompt="Pressione Enter para voltar:",
                show_badge=False,
            )
            input("> ")
            continue

        print(f"Pagina {page + 1}/{total_pages}\n")

        for idx, rod in enumerate(page_items, start=1):
            if rod.name not in unlocked_rods:
                label = "???"
            elif not _rod_counts_for_completion(rod):
                label = f"{rod.name} (nao conta na complecao)"
            else:
                label = rod.name
            print(f"{idx}. {label}")

        if total_pages > 1:
            print(
                f"\n{PAGE_PREV_KEY.upper()}. Pagina anterior | "
                f"{PAGE_NEXT_KEY.upper()}. Proxima pagina"
            )
        print("0. Voltar")
        choice = _read_choice("Escolha uma vara: ", total_pages)
        if choice == "0":
            return

        page, moved = apply_page_hotkey(choice, page, total_pages)
        if moved:
            continue

        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        rod = page_items[idx - 1]
        if rod.name not in unlocked_rods:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {rod.name} ===")
        print(f"Descricao: {rod.description or '-'}")
        if not _rod_counts_for_completion(rod):
            print("Esta vara nao conta para a complecao do bestiario.")
        input("\nEnter para voltar.")


def show_pools_bestiary(pools: List["FishingPool"], unlocked_pools: Set[str]):
    visible_pools = [
        pool
        for pool in pools
        if not (_pool_hidden_until_unlocked(pool) and pool.name not in unlocked_pools)
    ]
    countable_pools = [
        pool
        for pool in visible_pools
        if _pool_counts_for_completion(pool)
    ]
    page = 0
    page_size = 10
    while True:
        clear_screen()
        print("=== Bestiario: Pools desbloqueadas ===")
        total_pools = len(countable_pools)
        unlocked_count = sum(1 for pool in countable_pools if pool.name in unlocked_pools)
        completion = (unlocked_count / total_pools * 100) if total_pools else 0
        print(f"Complecao: {unlocked_count}/{total_pools} ({completion:.0f}%)")
        if not visible_pools:
            print("Nenhuma pool cadastrada.")
            input("\nEnter para voltar.")
            return

        page_slice = get_page_slice(len(visible_pools), page, page_size)
        page = page_slice.page
        total_pages = page_slice.total_pages
        start = page_slice.start
        end = page_slice.end
        page_items = visible_pools[start:end]
        if use_modern_ui():
            clear_screen()
            options = []
            for idx, pool in enumerate(page_items, start=1):
                if pool.name not in unlocked_pools:
                    label = "???"
                elif not _pool_counts_for_completion(pool):
                    label = f"{pool.name} (nao conta na complecao)"
                else:
                    label = pool.name
                options.append(MenuOption(str(idx), label))
            if total_pages > 1:
                options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina"))
                options.append(MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior"))
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "BESTIARIO",
                subtitle="Pools desbloqueadas",
                header_lines=[
                    f"Conclusao: {unlocked_count}/{total_pools} ({completion:.0f}%)",
                    f"Pagina {page + 1}/{total_pages}",
                ],
                options=options,
                prompt="Escolha uma pool:",
                show_badge=False,
            )
            choice = _read_choice("> ", total_pages)
            if choice == "0":
                return

            page, moved = apply_page_hotkey(choice, page, total_pages)
            if moved:
                continue

            if not choice.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(choice)
            if not (1 <= idx <= len(page_items)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            pool = page_items[idx - 1]
            if pool.name not in unlocked_pools:
                show_locked_entry()
                continue

            clear_screen()
            detail_lines = [f"Descricao: {pool.description or '-'}"]
            if not _pool_counts_for_completion(pool):
                detail_lines.append("Esta pool nao conta para a complecao do bestiario.")
            print_menu_panel(
                "POOL",
                subtitle=pool.name,
                header_lines=detail_lines,
                options=[MenuOption("0", "Voltar")],
                prompt="Pressione Enter para voltar:",
                show_badge=False,
            )
            input("> ")
            continue

        print(f"Pagina {page + 1}/{total_pages}\n")

        for idx, pool in enumerate(page_items, start=1):
            if pool.name not in unlocked_pools:
                label = "???"
            elif not _pool_counts_for_completion(pool):
                label = f"{pool.name} (nao conta na complecao)"
            else:
                label = pool.name
            print(f"{idx}. {label}")

        if total_pages > 1:
            print(
                f"\n{PAGE_PREV_KEY.upper()}. Pagina anterior | "
                f"{PAGE_NEXT_KEY.upper()}. Proxima pagina"
            )
        print("0. Voltar")
        choice = _read_choice("Escolha uma pool: ", total_pages)
        if choice == "0":
            return

        page, moved = apply_page_hotkey(choice, page, total_pages)
        if moved:
            continue

        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        pool = page_items[idx - 1]
        if pool.name not in unlocked_pools:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {pool.name} ===")
        print(f"Descricao: {pool.description or '-'}")
        if not _pool_counts_for_completion(pool):
            print("Esta pool nao conta para a complecao do bestiario.")
        input("\nEnter para voltar.")


def show_bestiary(
    pools: List["FishingPool"],
    available_rods: List[Rod],
    owned_rods: List[Rod],
    unlocked_pools: Set[str],
    discovered_fish: Set[str],
    hunt_definitions: Optional[Sequence["HuntDefinition"]] = None,
    regionless_fish_profiles: Optional[Sequence["FishProfile"]] = None,
):
    fish_sections = build_fish_bestiary_sections(
        pools,
        unlocked_pools,
        hunt_definitions=hunt_definitions,
        regionless_fish_profiles=regionless_fish_profiles,
    )
    sorted_rods = sorted(available_rods, key=lambda rod: rod.name)
    sorted_pools = sorted(pools, key=lambda pool: pool.name)

    while True:
        clear_screen()
        print_spaced_lines([
            "=== Bestiário ===",
            "1. Peixes pescados",
            "2. Varas adquiridas",
            "3. Pools desbloqueadas",
            "0. Voltar",
        ])

        choice = input("Escolha uma opção: ").strip()
        if choice == "0":
            return

        unlocked_rods = {rod.name for rod in owned_rods}

        if choice == "1":
            show_fish_bestiary(fish_sections, discovered_fish)
            continue

        if choice == "2":
            show_rods_bestiary(sorted_rods, unlocked_rods)
            continue

        if choice == "3":
            show_pools_bestiary(sorted_pools, unlocked_pools)
            continue

        print("Opção inválida.")
        input("\nEnter para voltar.")
