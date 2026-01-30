from __future__ import annotations

from typing import Dict, List, Set, TYPE_CHECKING

from utils.inventory import InventoryEntry
from utils.rods import Rod
from utils.ui import clear_screen

if TYPE_CHECKING:
    from utils.pesca import FishProfile, FishingPool


def collect_bestiary_fish(pools: List["FishingPool"]) -> List["FishProfile"]:
    fish_by_name: Dict[str, FishProfile] = {}
    for pool in pools:
        for fish in pool.fish_profiles:
            fish_by_name.setdefault(fish.name, fish)
    return [fish_by_name[name] for name in sorted(fish_by_name)]


def show_locked_entry():
    clear_screen()
    print("???")
    print("\nInformações ainda não desbloqueadas.")
    input("\nEnter para voltar.")


def show_fish_bestiary(
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
        print("=== Bestiário: Peixes pescados ===")
        if not ordered_fish:
            print("Nenhum peixe cadastrado.")
            input("\nEnter para voltar.")
            return

        total_pages = max(1, (len(ordered_fish) + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        end = start + page_size
        page_items = ordered_fish[start:end]

        print(f"Página {page + 1}/{total_pages}\n")

        for idx, fish in enumerate(page_items, start=1):
            label = fish.name if fish.name in unlocked_fish else "???"
            print(f"{idx}. {label}")

        if total_pages > 1:
            print("\nN. Próxima página | P. Página anterior")
        print("0. Voltar")
        choice = input("Escolha um peixe: ").strip()
        if choice == "0":
            return

        lowered = choice.lower()
        if lowered == "n" and total_pages > 1:
            page += 1
            continue
        if lowered == "p" and total_pages > 1:
            page -= 1
            continue

        if not choice.isdigit():
            print("Entrada inválida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Número fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        fish = page_items[idx - 1]
        if fish.name not in unlocked_fish:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {fish.name} ===")
        print(f"Raridade: {fish.rarity}")
        print(f"Descrição: {fish.description or '-'}")
        print(f"KG (min-max): {fish.kg_min:g} - {fish.kg_max:g}")
        input("\nEnter para voltar.")


def show_rods_bestiary(rods: List[Rod], unlocked_rods: Set[str]):
    page = 0
    page_size = 10
    while True:
        clear_screen()
        print("=== Bestiário: Varas adquiridas ===")
        if not rods:
            print("Nenhuma vara cadastrada.")
            input("\nEnter para voltar.")
            return

        total_pages = max(1, (len(rods) + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        end = start + page_size
        page_items = rods[start:end]

        print(f"Página {page + 1}/{total_pages}\n")

        for idx, rod in enumerate(page_items, start=1):
            label = rod.name if rod.name in unlocked_rods else "???"
            print(f"{idx}. {label}")

        if total_pages > 1:
            print("\nN. Próxima página | P. Página anterior")
        print("0. Voltar")
        choice = input("Escolha uma vara: ").strip()
        if choice == "0":
            return

        lowered = choice.lower()
        if lowered == "n" and total_pages > 1:
            page += 1
            continue
        if lowered == "p" and total_pages > 1:
            page -= 1
            continue

        if not choice.isdigit():
            print("Entrada inválida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Número fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        rod = page_items[idx - 1]
        if rod.name not in unlocked_rods:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {rod.name} ===")
        print(f"Descrição: {rod.description or '-'}")
        input("\nEnter para voltar.")


def show_pools_bestiary(pools: List["FishingPool"], unlocked_pools: Set[str]):
    page = 0
    page_size = 10
    while True:
        clear_screen()
        print("=== Bestiário: Pools desbloqueadas ===")
        if not pools:
            print("Nenhuma pool cadastrada.")
            input("\nEnter para voltar.")
            return

        total_pages = max(1, (len(pools) + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        end = start + page_size
        page_items = pools[start:end]

        print(f"Página {page + 1}/{total_pages}\n")

        for idx, pool in enumerate(page_items, start=1):
            label = pool.name if pool.name in unlocked_pools else "???"
            print(f"{idx}. {label}")

        if total_pages > 1:
            print("\nN. Próxima página | P. Página anterior")
        print("0. Voltar")
        choice = input("Escolha uma pool: ").strip()
        if choice == "0":
            return

        lowered = choice.lower()
        if lowered == "n" and total_pages > 1:
            page += 1
            continue
        if lowered == "p" and total_pages > 1:
            page -= 1
            continue

        if not choice.isdigit():
            print("Entrada inválida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(page_items)):
            print("Número fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        pool = page_items[idx - 1]
        if pool.name not in unlocked_pools:
            show_locked_entry()
            continue

        clear_screen()
        print(f"=== {pool.name} ===")
        print(f"Descrição: {pool.description or '-'}")
        input("\nEnter para voltar.")


def show_bestiary(
    pools: List["FishingPool"],
    available_rods: List[Rod],
    inventory: List[InventoryEntry],
    owned_rods: List[Rod],
    unlocked_pools: Set[str],
):
    fish_profiles = collect_bestiary_fish(pools)
    sorted_rods = sorted(available_rods, key=lambda rod: rod.name)
    sorted_pools = sorted(pools, key=lambda pool: pool.name)

    while True:
        clear_screen()
        print("=== Bestiário ===")
        print("1. Peixes pescados")
        print("2. Varas adquiridas")
        print("3. Pools desbloqueadas")
        print("0. Voltar")

        choice = input("Escolha uma opção: ").strip()
        if choice == "0":
            return

        unlocked_fish = {entry.name for entry in inventory}
        unlocked_rods = {rod.name for rod in owned_rods}

        if choice == "1":
            show_fish_bestiary(fish_profiles, unlocked_fish)
            continue

        if choice == "2":
            show_rods_bestiary(sorted_rods, unlocked_rods)
            continue

        if choice == "3":
            show_pools_bestiary(sorted_pools, unlocked_pools)
            continue

        print("Opção inválida.")
        input("\nEnter para voltar.")
