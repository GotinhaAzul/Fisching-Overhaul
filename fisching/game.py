from __future__ import annotations

from typing import Callable

from fisching.fishing import FishingSystem
from fisching.inventory import Inventory
from fisching.models import Player, Pool
from fisching.pools import load_pools
from fisching.utils import format_sequence, normalize_sequence


class Game:
    def __init__(self, input_func: Callable[[str], str] = input) -> None:
        self.input_func = input_func
        self.fishing_system = FishingSystem()
        self.pools = load_pools()

    def start(self) -> None:
        print("Bem-vindo ao Fisching RPG!\n")
        name = self.input_func("Qual é o seu nome? ").strip() or "Pescador"
        player = Player(name=name)
        inventory = Inventory(player.inventory)

        while True:
            print("\nO que você quer fazer?")
            print("1) Pescar")
            print("2) Ver inventário")
            print("3) Sair")
            choice = self.input_func("> ").strip()

            if choice == "1":
                pool = self._choose_pool()
                if pool:
                    self._handle_fishing(player, inventory, pool)
            elif choice == "2":
                self._show_inventory(player, inventory)
            elif choice == "3":
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
            inventory.add(result.fish.name)
            player.add_item(result.fish.name)
            print(
                f"Sucesso! Você pescou {result.fish.name} "
                f"(raridade: {result.fish.rarity})."
            )
        else:
            print("O peixe escapou! Tente novamente.")

    def _show_inventory(self, player: Player, inventory: Inventory) -> None:
        print(f"\nInventário de {player.name}:")
        for line in inventory.to_lines():
            print(line)
