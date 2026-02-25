from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Set, TYPE_CHECKING

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
from utils.bestiary_rewards import (
    BestiaryRewardDefinition,
    BestiaryRewardState,
    FISH_TARGET_ALL,
    get_claimable_bestiary_rewards,
)

if TYPE_CHECKING:
    from utils.hunts import HuntDefinition
    from utils.pesca import FishProfile, FishingPool


REGIONLESS_SECTION_NAME = "Sem regiao"


def _read_choice(
    prompt: str,
    total_pages: int,
    *,
    extra_instant_keys: Optional[Set[str]] = None,
) -> str:
    instant_keys = set(extra_instant_keys or set())
    if total_pages > 1:
        instant_keys.update({PAGE_PREV_KEY, PAGE_NEXT_KEY})
    return read_menu_choice(
        prompt,
        instant_keys=instant_keys,
    ).lower()


def _slice_paged_items(
    items: Sequence[object],
    page: int,
    page_size: int,
) -> tuple[Sequence[object], int, int]:
    page_slice = get_page_slice(len(items), page, page_size)
    page_items = items[page_slice.start:page_slice.end]
    return page_items, page_slice.page, page_slice.total_pages


def _add_pagination_options(options: List[MenuOption], total_pages: int) -> None:
    if total_pages <= 1:
        return
    options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proxima pagina"))
    options.append(MenuOption(PAGE_PREV_KEY.upper(), "Pagina anterior"))


def _print_pagination_controls(total_pages: int) -> None:
    if total_pages <= 1:
        return
    print(
        f"\n{PAGE_PREV_KEY.upper()}. Pagina anterior | "
        f"{PAGE_NEXT_KEY.upper()}. Proxima pagina"
    )


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


def _fish_completion_snapshot(
    sections: Sequence[FishBestiarySection],
    unlocked_fish: Set[str],
) -> tuple[float, Dict[str, float]]:
    completion_fish_names = {
        fish_name
        for section in sections
        if section.counts_for_completion
        for fish_name in section.completion_fish_names
    }
    total_fish = len(completion_fish_names)
    unlocked_count = sum(
        1
        for fish_name in completion_fish_names
        if fish_name in unlocked_fish
    )
    global_percent = (unlocked_count / total_fish * 100) if total_fish else 0.0

    by_pool: Dict[str, float] = {}
    for section in sections:
        if not section.counts_for_completion:
            continue
        _, _, section_percent = _section_completion(section, unlocked_fish)
        by_pool[section.title] = section_percent
    return global_percent, by_pool


def _rods_completion_percent(rods: Sequence[Rod], unlocked_rods: Set[str]) -> float:
    countable_rods = [rod for rod in rods if _rod_counts_for_completion(rod)]
    total_rods = len(countable_rods)
    unlocked_count = sum(1 for rod in countable_rods if rod.name in unlocked_rods)
    return (unlocked_count / total_rods * 100) if total_rods else 0.0


def _pools_completion_percent(
    pools: Sequence["FishingPool"],
    unlocked_pools: Set[str],
) -> float:
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
    total_pools = len(countable_pools)
    unlocked_count = sum(1 for pool in countable_pools if pool.name in unlocked_pools)
    return (unlocked_count / total_pools * 100) if total_pools else 0.0


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


def _format_reward_status(count: int) -> str:
    if count > 0:
        return "(🎁 Recompensa disponivel)"
    return ""


def _print_claim_notes(notes: List[str]) -> None:
    if notes:
        print("\n".join(notes))
    else:
        print("Recompensa resgatada!")


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

        page_items, page, total_pages = _slice_paged_items(ordered_fish, page, page_size)
        if use_modern_ui():
            clear_screen()
            options = [
                MenuOption(str(idx), fish.name if fish.name in unlocked_fish else "???")
                for idx, fish in enumerate(page_items, start=1)
            ]
            _add_pagination_options(options, total_pages)
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

        _print_pagination_controls(total_pages)
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
    *,
    pending_pool_reward_count: Optional[Callable[[str], int]] = None,
    claim_pool_rewards: Optional[Callable[[str], List[str]]] = None,
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
        claimable_count = (
            pending_pool_reward_count(section.title)
            if pending_pool_reward_count is not None
            else 0
        )
        reward_status = _format_reward_status(claimable_count)
        if section.counts_for_completion:
            print(f"Complecao: {unlocked_count}/{total_fish} ({completion:.0f}%)")
        else:
            print("Esta pool nao conta para a complecao do bestiario.")
        if has_hunt_only_fish:
            print("Peixes [Hunt] nao contam para a complecao da pool.")
        if reward_status:
            print(reward_status)
        if not ordered_fish:
            print("Nenhum peixe cadastrado.")
            input("\nEnter para voltar.")
            return

        page_items, page, total_pages = _slice_paged_items(ordered_fish, page, page_size)
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
            if reward_status:
                header_lines.append(reward_status)
            options = [
                MenuOption(
                    str(idx),
                    _fish_label(fish, unlocked_fish, section.completion_fish_names),
                )
                for idx, fish in enumerate(page_items, start=1)
            ]
            _add_pagination_options(options, total_pages)
            if claimable_count > 0 and claim_pool_rewards is not None:
                options.append(
                    MenuOption(
                        "G",
                        f"Resgatar recompensa da pool ({claimable_count})",
                    )
                )
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "BESTIARIO",
                subtitle=section.title,
                header_lines=header_lines,
                options=options,
                prompt="Escolha um peixe:",
                show_badge=False,
            )
            choice = _read_choice(
                "> ",
                total_pages,
                extra_instant_keys={"g"}
                if claimable_count > 0 and claim_pool_rewards is not None
                else None,
            )
            if choice == "0":
                return
            if choice == "g" and claimable_count > 0 and claim_pool_rewards is not None:
                clear_screen()
                _print_claim_notes(claim_pool_rewards(section.title))
                input("\nEnter para voltar.")
                continue

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

        _print_pagination_controls(total_pages)
        if claimable_count > 0 and claim_pool_rewards is not None:
            print(f"G. Resgatar recompensa da pool ({claimable_count})")
        print("0. Voltar")
        choice = _read_choice(
            "Escolha um peixe: ",
            total_pages,
            extra_instant_keys={"g"}
            if claimable_count > 0 and claim_pool_rewards is not None
            else None,
        )
        if choice == "0":
            return
        if choice == "g" and claimable_count > 0 and claim_pool_rewards is not None:
            clear_screen()
            _print_claim_notes(claim_pool_rewards(section.title))
            input("\nEnter para voltar.")
            continue

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
    *,
    pending_global_reward_count: Optional[Callable[[], int]] = None,
    claim_global_rewards: Optional[Callable[[], List[str]]] = None,
    pending_pool_reward_count: Optional[Callable[[str], int]] = None,
    claim_pool_rewards: Optional[Callable[[str], List[str]]] = None,
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
        global_claimable_count = (
            pending_global_reward_count()
            if pending_global_reward_count is not None
            else 0
        )
        reward_status = _format_reward_status(global_claimable_count)
        if reward_status:
            print(reward_status)
        if not sections:
            print("Nenhuma secao cadastrada.")
            input("\nEnter para voltar.")
            return

        page_items, page, total_pages = _slice_paged_items(sections, page, page_size)
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
                pool_claimable_count = (
                    pending_pool_reward_count(section.title)
                    if pending_pool_reward_count is not None and not section.locked
                    else 0
                )
                if pool_claimable_count > 0:
                    label = f"{label} 🎁"
                options.append(MenuOption(str(idx), label))
            _add_pagination_options(options, total_pages)
            if global_claimable_count > 0 and claim_global_rewards is not None:
                options.append(
                    MenuOption(
                        "G",
                        f"Resgatar recompensa global ({global_claimable_count})",
                    )
                )
            options.append(MenuOption("0", "Voltar"))
            header_lines = [
                f"Conclusao: {unlocked_count}/{total_fish} ({completion:.0f}%)",
                f"Pagina {page + 1}/{total_pages}",
            ]
            if reward_status:
                header_lines.append(reward_status)
            print_menu_panel(
                "BESTIARIO",
                subtitle="Peixes por pool",
                header_lines=header_lines,
                options=options,
                prompt="Escolha uma pool/regiao:",
                show_badge=False,
            )
            choice = _read_choice(
                "> ",
                total_pages,
                extra_instant_keys={"g"}
                if global_claimable_count > 0 and claim_global_rewards is not None
                else None,
            )
            if choice == "0":
                return
            if (
                choice == "g"
                and global_claimable_count > 0
                and claim_global_rewards is not None
            ):
                clear_screen()
                _print_claim_notes(claim_global_rewards())
                input("\nEnter para voltar.")
                continue

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

            _show_fish_bestiary_section(
                section,
                unlocked_fish,
                pending_pool_reward_count=pending_pool_reward_count,
                claim_pool_rewards=claim_pool_rewards,
            )
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
            pool_claimable_count = (
                pending_pool_reward_count(section.title)
                if pending_pool_reward_count is not None and not section.locked
                else 0
            )
            if pool_claimable_count > 0:
                label = f"{label} 🎁"
            print(f"{idx}. {label}")

        _print_pagination_controls(total_pages)
        if global_claimable_count > 0 and claim_global_rewards is not None:
            print(f"G. Resgatar recompensa global ({global_claimable_count})")
        print("0. Voltar")
        choice = _read_choice(
            "Escolha uma pool/regiao: ",
            total_pages,
            extra_instant_keys={"g"}
            if global_claimable_count > 0 and claim_global_rewards is not None
            else None,
        )
        if choice == "0":
            return
        if (
            choice == "g"
            and global_claimable_count > 0
            and claim_global_rewards is not None
        ):
            clear_screen()
            _print_claim_notes(claim_global_rewards())
            input("\nEnter para voltar.")
            continue

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

        _show_fish_bestiary_section(
            section,
            unlocked_fish,
            pending_pool_reward_count=pending_pool_reward_count,
            claim_pool_rewards=claim_pool_rewards,
        )

def show_rods_bestiary(
    rods: List[Rod],
    unlocked_rods: Set[str],
    *,
    pending_reward_count: Optional[Callable[[str], int]] = None,
    claim_rewards: Optional[Callable[[str], List[str]]] = None,
):
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
        claimable_count = pending_reward_count("rods") if pending_reward_count else 0
        reward_status = _format_reward_status(claimable_count)
        if reward_status:
            print(reward_status)
        if not rods:
            print("Nenhuma vara cadastrada.")
            input("\nEnter para voltar.")
            return

        page_items, page, total_pages = _slice_paged_items(rods, page, page_size)
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
            _add_pagination_options(options, total_pages)
            if claimable_count > 0 and claim_rewards is not None:
                options.append(
                    MenuOption("G", f"Resgatar recompensas (🎁 {claimable_count})")
                )
            options.append(MenuOption("0", "Voltar"))
            header_lines = [
                f"Conclusao: {unlocked_count}/{total_rods} ({completion:.0f}%)",
                f"Pagina {page + 1}/{total_pages}",
            ]
            if reward_status:
                header_lines.append(reward_status)
            print_menu_panel(
                "BESTIARIO",
                subtitle="Varas adquiridas",
                header_lines=header_lines,
                options=options,
                prompt="Escolha uma vara:",
                show_badge=False,
            )
            choice = _read_choice(
                "> ",
                total_pages,
                extra_instant_keys={"g"} if claimable_count > 0 else None,
            )
            if choice == "0":
                return
            if choice == "g" and claimable_count > 0 and claim_rewards is not None:
                clear_screen()
                _print_claim_notes(claim_rewards("rods"))
                input("\nEnter para voltar.")
                continue

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

        _print_pagination_controls(total_pages)
        if claimable_count > 0 and claim_rewards is not None:
            print(f"G. Resgatar recompensas (🎁 {claimable_count})")
        print("0. Voltar")
        choice = _read_choice(
            "Escolha uma vara: ",
            total_pages,
            extra_instant_keys={"g"} if claimable_count > 0 else None,
        )
        if choice == "0":
            return
        if choice == "g" and claimable_count > 0 and claim_rewards is not None:
            clear_screen()
            _print_claim_notes(claim_rewards("rods"))
            input("\nEnter para voltar.")
            continue

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


def show_pools_bestiary(
    pools: List["FishingPool"],
    unlocked_pools: Set[str],
    *,
    pending_reward_count: Optional[Callable[[str], int]] = None,
    claim_rewards: Optional[Callable[[str], List[str]]] = None,
):
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
        claimable_count = pending_reward_count("pools") if pending_reward_count else 0
        reward_status = _format_reward_status(claimable_count)
        if reward_status:
            print(reward_status)
        if not visible_pools:
            print("Nenhuma pool cadastrada.")
            input("\nEnter para voltar.")
            return

        page_items, page, total_pages = _slice_paged_items(visible_pools, page, page_size)
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
            _add_pagination_options(options, total_pages)
            if claimable_count > 0 and claim_rewards is not None:
                options.append(
                    MenuOption("G", f"Resgatar recompensas (🎁 {claimable_count})")
                )
            options.append(MenuOption("0", "Voltar"))
            header_lines = [
                f"Conclusao: {unlocked_count}/{total_pools} ({completion:.0f}%)",
                f"Pagina {page + 1}/{total_pages}",
            ]
            if reward_status:
                header_lines.append(reward_status)
            print_menu_panel(
                "BESTIARIO",
                subtitle="Pools desbloqueadas",
                header_lines=header_lines,
                options=options,
                prompt="Escolha uma pool:",
                show_badge=False,
            )
            choice = _read_choice(
                "> ",
                total_pages,
                extra_instant_keys={"g"} if claimable_count > 0 else None,
            )
            if choice == "0":
                return
            if choice == "g" and claimable_count > 0 and claim_rewards is not None:
                clear_screen()
                _print_claim_notes(claim_rewards("pools"))
                input("\nEnter para voltar.")
                continue

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

        _print_pagination_controls(total_pages)
        if claimable_count > 0 and claim_rewards is not None:
            print(f"G. Resgatar recompensas (🎁 {claimable_count})")
        print("0. Voltar")
        choice = _read_choice(
            "Escolha uma pool: ",
            total_pages,
            extra_instant_keys={"g"} if claimable_count > 0 else None,
        )
        if choice == "0":
            return
        if choice == "g" and claimable_count > 0 and claim_rewards is not None:
            clear_screen()
            _print_claim_notes(claim_rewards("pools"))
            input("\nEnter para voltar.")
            continue

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
    bestiary_rewards: Optional[Sequence[BestiaryRewardDefinition]] = None,
    bestiary_reward_state: Optional[BestiaryRewardState] = None,
    on_claim_bestiary_reward: Optional[
        Callable[[BestiaryRewardDefinition], List[str]]
    ] = None,
):
    fish_sections = build_fish_bestiary_sections(
        pools,
        unlocked_pools,
        hunt_definitions=hunt_definitions,
        regionless_fish_profiles=regionless_fish_profiles,
    )
    sorted_rods = sorted(available_rods, key=lambda rod: rod.name)
    sorted_pools = sorted(pools, key=lambda pool: pool.name)

    def list_claimable_rewards(
        category: str,
        *,
        fish_target_pool: Optional[str] = None,
        fish_global_only: bool = False,
    ) -> List[BestiaryRewardDefinition]:
        if (
            not bestiary_rewards
            or bestiary_reward_state is None
            or on_claim_bestiary_reward is None
        ):
            return []

        unlocked_rod_names = {rod.name for rod in owned_rods}
        fish_global_percent, fish_by_pool = _fish_completion_snapshot(
            fish_sections,
            discovered_fish,
        )
        rods_percent = _rods_completion_percent(sorted_rods, unlocked_rod_names)
        pools_percent = _pools_completion_percent(sorted_pools, unlocked_pools)
        claimable = get_claimable_bestiary_rewards(
            bestiary_rewards,
            bestiary_reward_state,
            category=category,
            fish_global_percent=fish_global_percent,
            fish_percent_by_pool=fish_by_pool,
            rods_percent=rods_percent,
            pools_percent=pools_percent,
        )
        if category != "fish":
            return claimable
        if fish_global_only:
            return [
                reward
                for reward in claimable
                if reward.target_pool.casefold() == FISH_TARGET_ALL.casefold()
            ]
        if fish_target_pool is None:
            return claimable
        target_pool_key = fish_target_pool.casefold()
        return [
            reward
            for reward in claimable
            if reward.target_pool.casefold() == target_pool_key
        ]

    def pending_rewards_count(category: str) -> int:
        return len(list_claimable_rewards(category))

    def _claim_selected_rewards(
        selected_rewards: Sequence[BestiaryRewardDefinition],
    ) -> List[str]:
        if (
            not bestiary_rewards
            or bestiary_reward_state is None
            or on_claim_bestiary_reward is None
        ):
            return ["Sistema de recompensas indisponivel."]
        if not selected_rewards:
            return ["Nenhuma recompensa disponivel no momento."]

        notes: List[str] = []
        for reward in selected_rewards:
            claim_notes = on_claim_bestiary_reward(reward)
            bestiary_reward_state.claimed.add(reward.reward_id)
            notes.append(f"Recompensa: {reward.name}")
            if claim_notes:
                notes.extend(claim_notes)
            else:
                notes.append("Recompensa resgatada!")
        return notes

    def claim_rewards_for_category(category: str) -> List[str]:
        return _claim_selected_rewards(list_claimable_rewards(category))

    def pending_fish_pool_rewards(pool_name: str) -> int:
        return len(list_claimable_rewards("fish", fish_target_pool=pool_name))

    def claim_fish_pool_rewards(pool_name: str) -> List[str]:
        return _claim_selected_rewards(
            list_claimable_rewards("fish", fish_target_pool=pool_name)
        )

    def pending_fish_global_rewards() -> int:
        return len(list_claimable_rewards("fish", fish_global_only=True))

    def claim_fish_global_rewards() -> List[str]:
        return _claim_selected_rewards(
            list_claimable_rewards("fish", fish_global_only=True)
        )

    while True:
        clear_screen()
        fish_status = _format_reward_status(pending_rewards_count("fish"))
        rods_status = _format_reward_status(pending_rewards_count("rods"))
        pools_status = _format_reward_status(pending_rewards_count("pools"))
        print_spaced_lines([
            "=== Bestiário ===",
            f"1. Peixes pescados {fish_status}".rstrip(),
            f"2. Varas adquiridas {rods_status}".rstrip(),
            f"3. Pools desbloqueadas {pools_status}".rstrip(),
            "0. Voltar",
        ])

        choice = input("Escolha uma opção: ").strip()
        if choice == "0":
            return

        unlocked_rods = {rod.name for rod in owned_rods}

        if choice == "1":
            show_fish_bestiary(
                fish_sections,
                discovered_fish,
                pending_global_reward_count=pending_fish_global_rewards,
                claim_global_rewards=claim_fish_global_rewards,
                pending_pool_reward_count=pending_fish_pool_rewards,
                claim_pool_rewards=claim_fish_pool_rewards,
            )
            continue

        if choice == "2":
            show_rods_bestiary(
                sorted_rods,
                unlocked_rods,
                pending_reward_count=pending_rewards_count,
                claim_rewards=claim_rewards_for_category,
            )
            continue

        if choice == "3":
            show_pools_bestiary(
                sorted_pools,
                unlocked_pools,
                pending_reward_count=pending_rewards_count,
                claim_rewards=claim_rewards_for_category,
            )
            continue

        print("Opção inválida.")
        input("\nEnter para voltar.")
