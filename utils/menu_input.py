from __future__ import annotations

import os
import sys
from typing import Iterable, Set


def read_menu_choice(
    prompt: str = "> ",
    *,
    instant_keys: Iterable[str] = (),
) -> str:
    keys: Set[str] = {key.lower() for key in instant_keys if key}
    if not keys:
        return input(prompt).strip()

    if os.name != "nt":
        return input(prompt).strip()

    try:
        import msvcrt  # type: ignore
    except ImportError:
        return input(prompt).strip()

    sys.stdout.write(prompt)
    sys.stdout.flush()

    buffer: list[str] = []
    while True:
        char = msvcrt.getwch()

        if char in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue

        if char == "\x03":
            raise KeyboardInterrupt

        if char in ("\r", "\n"):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(buffer).strip()

        if char in ("\b", "\x08"):
            if buffer:
                buffer.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue

        lowered = char.lower()
        if not buffer and lowered in keys:
            sys.stdout.write(char + "\n")
            sys.stdout.flush()
            return lowered

        buffer.append(char)
        sys.stdout.write(char)
        sys.stdout.flush()
