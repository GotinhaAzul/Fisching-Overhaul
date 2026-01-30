import os
from typing import List

from inventory import InventoryEntry, calculate_entry_value


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def format_currency(value: float) -> str:
    return f"R$ {value:0.2f}"


def show_market(inventory: List[InventoryEntry], balance: float) -> float:
    while True:
        clear_screen()
        print("=== Mercado ===")
        print(f"Dinheiro: {format_currency(balance)}")
        print("1. Vender peixe individual")
        print("2. Vender inventário inteiro")
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
                print(
                    f"{idx}. {entry.name} "
                    f"({entry.kg:0.2f}kg) - {format_currency(value)}"
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
            print(
                f"Vendeu {entry.name} ({entry.kg:0.2f}kg) "
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

        print("Opção inválida.")
        input("\nEnter para voltar.")
