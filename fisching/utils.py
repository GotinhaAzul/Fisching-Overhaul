from __future__ import annotations

from typing import Iterable, List


def normalize_sequence(user_input: str) -> List[str]:
    cleaned = user_input.replace(" ", "").strip().upper()
    return [char for char in cleaned]


def format_sequence(sequence: Iterable[str]) -> str:
    return " ".join(sequence)
