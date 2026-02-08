import os
from typing import Callable
from typing import Iterable
from typing import Sequence
from typing import Tuple


MenuEntry = Tuple[str, str]


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_spaced_lines(lines: Iterable[str], gap_lines: int = 1):
    """Imprime linhas com espaçamento vertical para melhorar leitura em menus."""
    separator = "\n" * max(1, gap_lines)
    print(separator.join(lines))


def choose_menu_option_with_mouse(
    title_lines: Sequence[str],
    menu_entries: Sequence[MenuEntry],
    fallback_input: Callable[[], str],
) -> str:
    """
    Tenta permitir navegação por teclado/mouse em menus de terminal.

    Se o terminal não suportar `curses` (ou não for TTY), usa fallback de input.
    """
    if not menu_entries:
        return fallback_input()

    if os.name == "nt":
        # Em Windows sem implementação de curses robusta, cai para input padrão.
        return fallback_input()

    if not os.isatty(0) or not os.isatty(1):
        return fallback_input()

    try:
        import curses
    except Exception:
        return fallback_input()

    def _screen(stdscr):
        selected_idx = 0
        curses.curs_set(0)
        stdscr.keypad(True)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        curses.mouseinterval(0)

        first_option_row = len(title_lines)

        while True:
            stdscr.erase()
            for row, line in enumerate(title_lines):
                stdscr.addstr(row, 0, line)

            for idx, (value, label) in enumerate(menu_entries):
                row = first_option_row + idx
                marker = "➤ " if idx == selected_idx else "  "
                stdscr.addstr(row, 0, f"{marker}{value}. {label}")

            stdscr.addstr(
                first_option_row + len(menu_entries) + 1,
                0,
                "Enter: selecionar | Clique: selecionar",
            )
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("w"), ord("W")):
                selected_idx = (selected_idx - 1) % len(menu_entries)
                continue
            if key in (curses.KEY_DOWN, ord("s"), ord("S")):
                selected_idx = (selected_idx + 1) % len(menu_entries)
                continue
            if key in (10, 13, curses.KEY_ENTER):
                return menu_entries[selected_idx][0]

            if ord("0") <= key <= ord("9"):
                digit = chr(key)
                for value, _ in menu_entries:
                    if value == digit:
                        return value

            if key == curses.KEY_MOUSE:
                try:
                    _, _, my, _, state = curses.getmouse()
                except curses.error:
                    continue

                clicked = state & (
                    curses.BUTTON1_CLICKED
                    | curses.BUTTON1_RELEASED
                    | curses.BUTTON1_PRESSED
                    | curses.BUTTON1_DOUBLE_CLICKED
                    | curses.BUTTON1_TRIPLE_CLICKED
                )
                if not clicked:
                    continue

                option_idx = my - first_option_row
                if 0 <= option_idx < len(menu_entries):
                    selected_idx = option_idx
                    return menu_entries[selected_idx][0]

    try:
        return curses.wrapper(_screen)
    except Exception:
        return fallback_input()


def choose_numbered_index_with_mouse(
    title_lines: Sequence[str],
    options: Sequence[str],
    fallback_input: Callable[[], str],
) -> int | None:
    """Seleciona um item numerado (1..N) com suporte a mouse, retornando índice 0-based."""
    menu_entries = [(str(idx), label) for idx, label in enumerate(options, start=1)]
    choice = choose_menu_option_with_mouse(
        title_lines=title_lines,
        menu_entries=menu_entries,
        fallback_input=fallback_input,
    )
    if not choice.isdigit():
        return None

    selected = int(choice)
    if not (1 <= selected <= len(options)):
        return None
    return selected - 1
