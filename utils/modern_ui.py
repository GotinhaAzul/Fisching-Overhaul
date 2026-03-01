from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.style import Style as RichStyle
from rich.text import Text


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
_active_accent_color = "#87CEEB"
_active_icon_color = "#87CEEB"
_active_badge_lines: Sequence[str] = _DEFAULT_BADGE

console = Console(highlight=False)


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
        _active_accent_color = "#87CEEB"
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


def _render_badge_colored() -> List[str]:
    """Render badge lines with icon color applied, returned as pre-rendered ANSI strings."""
    badge = _ascii_badge()
    
    badge_text = Text()
    for i, line in enumerate(badge):
        badge_text.append(line, style=_active_icon_color)
        if i < len(badge) - 1:
            badge_text.append("\n")
            
    panel = Panel(
        badge_text,
        border_style=_active_icon_color,
        expand=False,
        padding=(0, 1),
    )
    
    with console.capture() as cap:
        console.print(panel)
    return cap.get().rstrip("\n").splitlines()


def _merge_badge(
    panel_lines: List[str],
    badge_lines_rendered: List[str],
    *,
    badge_left: bool,
) -> List[str]:
    badge_width = max(_visible_len(line) for line in badge_lines_rendered) if badge_lines_rendered else 0
    panel_width = max(_visible_len(line) for line in panel_lines) if panel_lines else 0
    max_lines = max(len(panel_lines), len(badge_lines_rendered))
    
    merged: List[str] = []
    for idx in range(max_lines):
        if idx < len(badge_lines_rendered):
            badge_line = badge_lines_rendered[idx]
        else:
            badge_line = " " * badge_width
            
        if idx < len(panel_lines):
            panel_line = panel_lines[idx]
        else:
            panel_line = " " * panel_width
            
        if badge_left:
            merged.append(f"{badge_line}  {panel_line}")
        else:
            merged.append(f"{panel_line}  {badge_line}")
    return merged


def use_modern_ui() -> bool:
    theme = os.getenv(UI_THEME_ENV_VAR, UI_THEME_MODERN).strip().lower()
    return theme != UI_THEME_LEGACY


def format_option_line(option: MenuOption, *, dim_hints: bool = True) -> str:
    line = f"\\[{option.key:<2}] {option.label}"
    if option.hint:
        hint = f" - {option.hint}"
        line = f"{line}[dim]{hint}[/dim]" if dim_hints else f"{line}{hint}"
    if option.status:
        line = f"{line} ({option.status})"
    if not option.enabled:
        line = f"[dim]{line}[/dim]"
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
    body_parts: List[str] = []

    if header_lines:
        body_parts.extend(header_lines)

    option_lines = [format_option_line(option) for option in (options or [])]
    if option_lines and show_divider:
        body_parts.append(f"[{_active_accent_color}]{'─' * (width - 4)}[/]")
    body_parts.extend(option_lines)

    if footer_lines:
        if body_parts and body_parts[-1] != "":
            body_parts.append("")
        body_parts.extend(footer_lines)

    if prompt:
        body_parts.append("")
        body_parts.append(f"[{_active_accent_color}]{prompt}[/]")

    body_text = "\n".join(body_parts)

    panel_title = f"[bold {_active_accent_color}]{title}[/]"
    if subtitle:
        panel_title = f"{panel_title}  [dim white]{subtitle}[/]"

    panel = Panel(
        body_text,
        title=panel_title,
        title_align="left",
        border_style=_active_accent_color,
        width=width,
        padding=(0, 1),
    )

    with console.capture() as capture:
        console.print(panel)
    rendered = capture.get().rstrip("\n")
    panel_lines = rendered.splitlines()

    if not show_badge:
        return panel_lines

    badge_rendered = _render_badge_colored()
    return _merge_badge(panel_lines, badge_rendered, badge_left=badge_left)


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
        bar_color = "green"
    elif ratio > 0.3:
        bar_color = "yellow"
    else:
        bar_color = "red"

    hud_text = Text()
    hud_text.append("HUD", style=f"bold {_active_accent_color}")
    hud_text.append(f" | Seq: {seq_str:<26} ")
    hud_text.append(f"| Time: [{bar}] {time_left:0.2f}s ", style=bar_color)
    hud_text.append(f"| Hits: {typed_count}/{len(seq)} ")
    hud_text.append("| ESC sai")

    with console.capture() as capture:
        console.print(hud_text, end="")
    return "\r" + capture.get()
