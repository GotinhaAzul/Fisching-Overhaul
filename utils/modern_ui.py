from __future__ import annotations

import os
import re
import sys
import textwrap
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from colorama import Fore, Style


UI_THEME_ENV_VAR = "FISCHING_UI_THEME"
UI_THEME_MODERN = "modern"
UI_THEME_LEGACY = "legacy"
DEFAULT_PANEL_WIDTH = 64

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_DEFAULT_BADGE = (
    "  /\\_/\\  ",
    " ( o.o ) ",
    "  > ^ <  ",
)
_active_accent_color = Fore.CYAN
_active_icon_color = Fore.CYAN
_active_badge_lines: Sequence[str] = _DEFAULT_BADGE


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str
    hint: str = ""
    enabled: bool = True
    status: str = ""


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _visible_len(text: str) -> int:
    return len(_strip_ansi(text))


def _pad(text: str, width: int) -> str:
    visual_len = _visible_len(text)
    if visual_len > width:
        return _strip_ansi(text)[:width]
    return text + (" " * (width - visual_len))


def _wrap_line(text: str, width: int) -> List[str]:
    if width <= 0:
        return [""]
    if not text:
        return [""]

    plain_text = _strip_ansi(text)
    if len(plain_text) <= width:
        return [text]

    indent_match = re.match(r"^\s*", plain_text)
    indent = indent_match.group(0) if indent_match else ""
    subsequent_indent = indent if 0 < len(indent) < width else ""

    wrapped = textwrap.wrap(
        plain_text,
        width=width,
        subsequent_indent=subsequent_indent,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return wrapped or [""]


def _frame_block(lines: Iterable[str], width: int) -> List[str]:
    top = "+" + ("-" * width) + "+"
    bottom = "+" + ("-" * width) + "+"
    body: List[str] = []
    for line in lines:
        for wrapped_line in _wrap_line(line, width):
            body.append(f"|{_pad(wrapped_line, width)}|")
    return [top, *body, bottom]


def _ascii_badge() -> List[str]:
    return list(_active_badge_lines)


def set_ui_cosmetics(
    *,
    accent_color: Optional[str] = None,
    icon_color: Optional[str] = None,
    badge_lines: Optional[Sequence[str]] = None,
) -> None:
    global _active_accent_color, _active_icon_color, _active_badge_lines

    if isinstance(accent_color, str) and accent_color:
        _active_accent_color = accent_color
    else:
        _active_accent_color = Fore.CYAN
    if isinstance(icon_color, str) and icon_color:
        _active_icon_color = icon_color
    else:
        _active_icon_color = _active_accent_color

    normalized_badge: List[str] = []
    if badge_lines:
        for line in badge_lines:
            if isinstance(line, str):
                normalized_badge.append(line[:40])
    _active_badge_lines = tuple(normalized_badge) if normalized_badge else _DEFAULT_BADGE


def _merge_badge(
    menu_block: Sequence[str],
    badge_block: Sequence[str],
    *,
    badge_left: bool,
) -> List[str]:
    merged: List[str] = []
    badge_width = _visible_len(badge_block[0]) if badge_block else 0
    for idx, line in enumerate(menu_block):
        badge_line = badge_block[idx] if idx < len(badge_block) else (" " * badge_width)
        if badge_left:
            merged.append(f"{badge_line}  {line}")
        else:
            merged.append(f"{line}  {badge_line}")
    return merged


def use_modern_ui() -> bool:
    theme = os.getenv(UI_THEME_ENV_VAR, UI_THEME_MODERN).strip().lower()
    return theme != UI_THEME_LEGACY


def format_option_line(option: MenuOption, *, dim_hints: bool = True) -> str:
    line = f"[{option.key:<2}] {option.label}"
    if option.hint:
        hint = f" - {option.hint}"
        line = f"{line}{Style.DIM}{hint}{Style.RESET_ALL}" if dim_hints else f"{line}{hint}"
    if option.status:
        line = f"{line} ({option.status})"
    if not option.enabled:
        line = f"{Style.DIM}{line}{Style.RESET_ALL}"
    return line


def render_menu_panel(
    title: str,
    *,
    subtitle: str = "",
    header_lines: Optional[Sequence[str]] = None,
    options: Optional[Sequence[MenuOption]] = None,
    footer_lines: Optional[Sequence[str]] = None,
    prompt: str = "Escolha uma opcao:",
    width: int = DEFAULT_PANEL_WIDTH,
    show_badge: bool = True,
    badge_left: bool = True,
    show_divider: bool = True,
) -> List[str]:
    lines: List[str] = []
    title_line = f"{Style.BRIGHT}{_active_accent_color}{title}{Style.RESET_ALL}"
    if subtitle:
        title_line = (
            f"{title_line}  "
            f"{Style.DIM}{Fore.WHITE}{subtitle}{Style.RESET_ALL}"
        )
    lines.append(title_line)

    if header_lines:
        lines.extend(header_lines)

    option_lines = [format_option_line(option) for option in (options or [])]
    if option_lines and show_divider:
        lines.append("-" * width)
    lines.extend(option_lines)

    if footer_lines:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(footer_lines)

    if prompt:
        lines.append("")
        lines.append(f"{_active_accent_color}{prompt}{Style.RESET_ALL}")

    panel_block = _frame_block(lines, width)
    if not show_badge:
        return panel_block

    badge_block = _frame_block(_ascii_badge(), 9)
    badge_block = [
        f"{_active_icon_color}{line}{Style.RESET_ALL}"
        for line in badge_block
    ]
    return _merge_badge(panel_block, badge_block, badge_left=badge_left)


def print_menu_panel(*args, **kwargs) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    for line in render_menu_panel(*args, **kwargs):
        safe_line = line.encode(encoding, errors="replace").decode(encoding)
        print(safe_line)


def render_fishing_hud_line(
    attempt,
    typed: Sequence[str],
    time_left: float,
    *,
    total_time_s: Optional[float] = None,
) -> str:
    seq = attempt.sequence
    typed_count = len(typed)
    remaining = seq[typed_count:]

    seq_str = " ".join(k.upper() for k in remaining) if remaining else "OK"
    seq_limit = 26
    if len(seq_str) > seq_limit:
        seq_str = f"{seq_str[:seq_limit - 3]}..."

    total_time = max(
        0.001,
        float(total_time_s if total_time_s is not None else attempt.time_limit_s),
    )
    ratio = max(0.0, min(1.0, time_left / total_time))
    bar_len = 20
    filled = int(bar_len * ratio)
    bar = ("=" * filled) + ("." * (bar_len - filled))
    if ratio > 0.6:
        bar_color = Fore.GREEN
    elif ratio > 0.3:
        bar_color = Fore.YELLOW
    else:
        bar_color = Fore.RED

    return (
        "\r"
        f"{Style.BRIGHT}{_active_accent_color}HUD{Style.RESET_ALL} "
        f"| Seq: {seq_str:<26} "
        f"| Time: {bar_color}[{bar}]{Style.RESET_ALL} {time_left:0.2f}s "
        f"| Hits: {typed_count}/{len(seq)} "
        "| ESC sai"
    )
