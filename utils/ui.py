import os
import re
from typing import Iterable, List

from utils.modern_ui import MenuOption, print_menu_panel, use_modern_ui


_OPTION_RE = re.compile(r"^(\d+)\.\s*(.+)$")


def _clean_menu_title(raw_title: str) -> str:
    title = raw_title.strip().strip("=")
    if not title:
        return "MENU"
    return title


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_spaced_lines(lines: Iterable[str], gap_lines: int = 1):
    """Imprime linhas com espacamento vertical para melhorar leitura em menus."""
    line_list = list(lines)
    if not line_list:
        return

    if use_modern_ui():
        headers: List[str] = []
        options: List[MenuOption] = []
        for line in line_list[1:]:
            match = _OPTION_RE.match(line.strip())
            if match:
                options.append(MenuOption(match.group(1), match.group(2)))
            else:
                headers.append(line)
        if options:
            print_menu_panel(
                _clean_menu_title(line_list[0]),
                header_lines=headers,
                options=options,
                prompt="",
                show_badge=False,
            )
            return

    separator = "\n" * max(1, gap_lines)
    print(separator.join(line_list))
