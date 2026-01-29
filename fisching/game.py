from __future__ import annotations

from typing import Callable

from fisching.fishing import FishingSystem
from fisching.inventory import Inventory
from fisching.models import CaughtFish, Player, Pool
from fisching.pools import load_pools
from fisching.utils import (
    calculate_fish_value,
    clear_screen,
    format_sequence,
    normalize_sequence,
)


class Game:
    def __init__(self, input_func: Callable[[str], str] = input) -> None:
        self.input_func = input_func
        self.fishing_system = FishingSystem()
        self.pools = load_pools()

    def start(self) -> None:
        print("Bem-vindo ao Fisching RPG!\n")
        player = Player(name="Pescador")
        inventory = Inventory(player.inventory)

        while True:
            clear_screen()
            print("\nO que você quer fazer?")
            print("1) Pescar")
            print("2) Ver inventário")
            print("3) Mercado")
            print("4) Sair")
            choice = self.input_func("> ").strip()

            if choice == "1":
                pool = self._choose_pool()
                if pool:
                    self._handle_fishing(player, inventory, pool)
            elif choice == "2":
                self._show_inventory(player, inventory)
            elif choice == "3":
                self._visit_market(player, inventory)
            elif choice == "4":
                print("Até a próxima pesca!")
                break
            else:
                print("Opção inválida. Tente novamente.")

    def _choose_pool(self) -> Pool | None:
        if not self.pools:
            print("Nenhuma pool disponível no momento.")
            return None

        pools = list(self.pools.values())
        while True:
            clear_screen()
            print("\nEscolha uma pool para pescar:")
            for index, pool in enumerate(pools, start=1):
                print(f"{index}) {pool.name} - {pool.description}")
            print("0) Voltar")
            choice = self.input_func("> ").strip()

            if choice == "0":
                return None
            if choice.isdigit():
                index = int(choice)
                if 1 <= index <= len(pools):
                    return pools[index - 1]
            print("Opção inválida. Tente novamente.")

    def _handle_fishing(self, player: Player, inventory: Inventory, pool: Pool) -> None:
        fish = self.fishing_system.choose_fish(pool)
        sequence_length = self.fishing_system.sequence_length_for_fish(fish)
        sequence = self.fishing_system.generate_sequence(sequence_length)
        print("\nPrepare-se! Digite a sequência abaixo:")
        print(format_sequence(sequence))
        user_sequence = self.input_func("Sequência: ")
        provided = normalize_sequence(user_sequence)
        result = self.fishing_system.resolve_attempt(sequence, provided, fish)

        if result.success and result.fish:
            weight = self.fishing_system.roll_weight(result.fish)
            catch = CaughtFish(
                name=result.fish.name,
                weight_kg=weight,
                base_value=result.fish.base_value,
            )
            inventory.add(catch)
            print(
                f"Sucesso! Você pescou {result.fish.name} "
                f"(raridade: {result.fish.rarity}, {weight:.2f} kg)."
            )
        else:
            print("O peixe escapou! Tente novamente.")

    def _show_inventory(self, player: Player, inventory: Inventory) -> None:
        print(f"\nInventário de {player.name}:")
        for line in inventory.to_lines():
            print(line)
        print(f"Saldo atual: {player.balance:.2f} moedas")

    def _visit_market(self, player: Player, inventory: Inventory) -> None:
        while True:
            clear_screen()
            print("\nMercado")
            print("1) Vender peixe individual")
            print("2) Vender inventário todo")
            print("0) Voltar")
            choice = self.input_func("> ").strip()

            if choice == "0":
                return
            if choice == "1":
                self._sell_individual(player, inventory)
            elif choice == "2":
                self._sell_all(player, inventory)
            else:
                print("Opção inválida. Tente novamente.")

    def _sell_individual(self, player: Player, inventory: Inventory) -> None:
        catches = inventory.list()
        if not catches:
            print("Você não tem peixes para vender.")
            return

        clear_screen()
        print("\nEscolha um peixe para vender:")
        for line in inventory.to_lines():
            print(line)
        choice = self.input_func("> ").strip()
        if not choice.isdigit():
            print("Opção inválida. Tente novamente.")
            return

        index = int(choice) - 1
        if index < 0 or index >= len(catches):
            print("Opção inválida. Tente novamente.")
            return

        catch = inventory.remove(index)
        value = calculate_fish_value(catch.base_value, catch.weight_kg)
        player.add_money(value)
        print(
            f"Você vendeu {catch.name} ({catch.weight_kg:.2f} kg) "
            f"por {value:.2f} moedas."
        )

    def _sell_all(self, player: Player, inventory: Inventory) -> None:
        catches = inventory.list()
        if not catches:
            print("Você não tem peixes para vender.")
            return

        total_value = inventory.total_value()
        total_count = len(catches)
        inventory.clear()
        player.add_money(total_value)
        print(
            f"Você vendeu {total_count} peixe(s) "
            f"por {total_value:.2f} moedas."
        )
