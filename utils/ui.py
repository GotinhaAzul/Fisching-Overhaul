import os
from typing import Iterable


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_spaced_lines(lines: Iterable[str], gap_lines: int = 1):
    """Imprime linhas com espaçamento vertical para melhorar leitura em menus."""
    separator = "\n" * max(1, gap_lines)
    print(separator.join(lines))
