from typing import List

from utils.dialogue import get_market_line
from utils.inventory import InventoryEntry, calculate_entry_value
from utils.rods import Rod
from utils.ui import clear_screen


def format_currency(value: float) -> str:
    return f"R$ {value:0.2f}"


def format_rod_entry(index: int, rod: Rod) -> str:
    return (
        f"{index}. {rod.name} "
        f"(Sorte: {rod.luck:.0%} | KGMax: {rod.kg_max:g} | "
        f"Controle: {rod.control:+.1f}s) - {format_currency(rod.price)}"
    )


def show_market(
    inventory: List[InventoryEntry],
    balance: float,
    available_rods: List[Rod],
    owned_rods: List[Rod],
) -> float:
    while True:
        clear_screen()
        print("🛒 === Mercado ===")
        print(get_market_line())
        print(f"Dinheiro: {format_currency(balance)}")
        print("1. Vender peixe individual")
        print("2. Vender inventário inteiro")
        print("3. Comprar vara")
        print("0. Voltar")

        choice = input("Escolha uma opção: ").strip()
        if choice == "0":
            return balance

        if choice == "1":
            clear_screen()
            if not inventory:
                print("Inventário vazio.")
                input("\nEnter para voltar.")
                continue

            print("Escolha o peixe para vender:")
            for idx, entry in enumerate(inventory, start=1):
                value = calculate_entry_value(entry)
                mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
                print(
                    f"{idx}. {entry.name} "
                    f"({entry.kg:0.2f}kg){mutation_label} - {format_currency(value)}"
                )

            selection = input("Digite o número do peixe: ").strip()
            if not selection.isdigit():
                print("Entrada inválida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(inventory)):
                print("Número fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            entry = inventory.pop(idx - 1)
            value = calculate_entry_value(entry)
            balance += value
            mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
            print(
                f"Vendeu {entry.name} ({entry.kg:0.2f}kg){mutation_label} "
                f"por {format_currency(value)}."
            )
            input("\nEnter para voltar.")
            continue

        if choice == "2":
            clear_screen()
            if not inventory:
                print("Inventário vazio.")
                input("\nEnter para voltar.")
                continue

            total = sum(calculate_entry_value(entry) for entry in inventory)
            inventory.clear()
            balance += total
            print(f"Inventário vendido por {format_currency(total)}.")
            input("\nEnter para voltar.")
            continue

        if choice == "3":
            clear_screen()
            rods_for_sale = [
                rod for rod in available_rods if rod.name not in {r.name for r in owned_rods}
            ]
            if not rods_for_sale:
                print("Nenhuma vara disponível para compra.")
                input("\nEnter para voltar.")
                continue

            print("Varas disponíveis:")
            for idx, rod in enumerate(rods_for_sale, start=1):
                print(format_rod_entry(idx, rod))
                print(f"   {rod.description}")

            selection = input("Digite o número da vara: ").strip()
            if not selection.isdigit():
                print("Entrada inválida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(rods_for_sale)):
                print("Número fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            rod = rods_for_sale[idx - 1]
            if balance < rod.price:
                print("Saldo insuficiente.")
                input("\nEnter para voltar.")
                continue

            balance -= rod.price
            owned_rods.append(rod)
            print(f"Comprou {rod.name} por {format_currency(rod.price)}.")
            input("\nEnter para voltar.")
            continue

        print("Opção inválida.")
        input("\nEnter para voltar.")
