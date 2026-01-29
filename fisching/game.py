from __future__ import annotations

from typing import Callable

from fisching.fishing import FishingSystem
from fisching.inventory import Inventory
from fisching.models import Player
from fisching.utils import format_sequence, normalize_sequence


class Game:
    def __init__(self, input_func: Callable[[str], str] = input) -> None:
        self.input_func = input_func
        self.fishing_system = FishingSystem()

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
                self._handle_fishing(player, inventory)
            elif choice == "2":
                self._show_inventory(player, inventory)
            elif choice == "3":
                print("Até a próxima pesca!")
                break
            else:
                print("Opção inválida. Tente novamente.")

    def _handle_fishing(self, player: Player, inventory: Inventory) -> None:
        sequence = self.fishing_system.generate_sequence()
        print("\nPrepare-se! Digite a sequência abaixo:")
        print(format_sequence(sequence))
        user_sequence = self.input_func("Sequência: ")
        provided = normalize_sequence(user_sequence)
        result = self.fishing_system.resolve_attempt(sequence, provided)

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
