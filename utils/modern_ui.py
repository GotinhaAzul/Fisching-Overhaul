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
from utils.perfect_catch import clamp, resolve_hud_color


UI_THEME_ENV_VAR = "FISCHING_UI_THEME"
UI_THEME_MODERN = "modern"
UI_THEME_LEGACY = "legacy"
UI_UNICODE_ENV_VAR = "FISCHING_USE_UNICODE"
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

_UNICODE_UI_SYMBOLS = {
    "PROGRESS_FULL": "■",
    "PROGRESS_EMPTY": "□",
    "REQ_DONE": "●",
    "REQ_TODO": "○",
    "LUCK": "Luck",
}
_ASCII_UI_SYMBOLS = {
    "PROGRESS_FULL": "#",
    "PROGRESS_EMPTY": "-",
    "REQ_DONE": "*",
    "REQ_TODO": "o",
    "LUCK": "Luck",
}


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str
    hint: str = ""
    enabled: bool = True
    status: str = ""


def _read_bool_env(var_name: str, *, default: bool) -> bool:
    raw_value = os.getenv(var_name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _stdout_supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        for symbol in _UNICODE_UI_SYMBOLS.values():
            symbol.encode(encoding)
        return True
    except UnicodeEncodeError:
        return False
    except LookupError:
        return False


USE_UNICODE = _read_bool_env(UI_UNICODE_ENV_VAR, default=_stdout_supports_unicode())
_UNICODE_OVERRIDE: Optional[bool] = None


def is_unicode_enabled() -> bool:
    if _UNICODE_OVERRIDE is not None:
        return _UNICODE_OVERRIDE
    return USE_UNICODE


def set_unicode_enabled(enabled: bool) -> None:
    global _UNICODE_OVERRIDE
    _UNICODE_OVERRIDE = bool(enabled)
    os.environ[UI_UNICODE_ENV_VAR] = "1" if _UNICODE_OVERRIDE else "0"


def get_ui_symbol(key: str) -> str:
    normalized = key.strip().upper()
    symbol_map = _UNICODE_UI_SYMBOLS if is_unicode_enabled() else _ASCII_UI_SYMBOLS
    return symbol_map.get(normalized, normalized)


def render_progress_bar(current: int, total: int, width: int = 10) -> str:
    safe_width = max(1, int(width))
    safe_current = max(0, int(current))
    safe_total = max(0, int(total))

    if safe_total <= 0:
        fill_ratio = 1.0 if safe_current > 0 else 0.0
    else:
        fill_ratio = min(1.0, safe_current / safe_total)

    filled = int(fill_ratio * safe_width)
    full_symbol = get_ui_symbol("PROGRESS_FULL")
    empty_symbol = get_ui_symbol("PROGRESS_EMPTY")
    return f"[{full_symbol * filled}{empty_symbol * (safe_width - filled)}]"


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
    breadcrumb: str = "",
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

    if breadcrumb:
        body_parts.append(f"[dim]{breadcrumb}[/dim]")
        if header_lines:
            body_parts.append("")

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


def _terminal_line_width(default: int = 120) -> int:
    try:
        columns = os.get_terminal_size().columns
    except OSError:
        columns = default
    return max(20, columns - 1)


def _truncate_text(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return f"{text[:max_len - 3]}..."


def _lerp_channel(start: int, end: int, ratio: float) -> int:
    return int(round(start + ((end - start) * ratio)))


def _interpolate_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    safe_ratio = clamp(ratio, 0.0, 1.0)
    return (
        _lerp_channel(start[0], end[0], safe_ratio),
        _lerp_channel(start[1], end[1], safe_ratio),
        _lerp_channel(start[2], end[2], safe_ratio),
    )


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def _resolve_hud_gradient_color(elapsed_ratio: float, threshold_ratio: float) -> str:
    safe_elapsed = clamp(elapsed_ratio, 0.0, 1.0)
    safe_threshold = clamp(threshold_ratio, 0.10, 1.00)
    color_system = getattr(console, "color_system", None)
    if color_system != "truecolor":
        return resolve_hud_color(safe_elapsed, safe_threshold)

    color_stops: list[tuple[float, tuple[int, int, int]]] = [
        (0.00, (0, 220, 255)),
        (0.45, (65, 210, 120)),
        (0.75, (255, 210, 0)),
        (1.00, (255, 70, 70)),
    ]
    for index in range(1, len(color_stops)):
        stop_ratio, stop_color = color_stops[index]
        prev_ratio, prev_color = color_stops[index - 1]
        if safe_elapsed <= stop_ratio:
            segment_span = max(0.001, stop_ratio - prev_ratio)
            segment_ratio = (safe_elapsed - prev_ratio) / segment_span
            return _rgb_to_hex(_interpolate_rgb(prev_color, stop_color, segment_ratio))
    return _rgb_to_hex(color_stops[-1][1])


def render_fishing_hud_line(
    attempt,
    typed: Sequence[str],
    time_left: float,
    *,
    total_time_s: Optional[float] = None,
    perfect_threshold_ratio: float = 0.20,
    perfect_catch_enabled: bool = True,
    ability_counter_text: str = "",
    weather_text: str = "",
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
    remaining_ratio = max(0.0, min(1.0, time_left / total_time))
    elapsed_ratio = 1.0 - remaining_ratio
    safe_threshold = clamp(perfect_threshold_ratio, 0.10, 1.00)
    bar_len = 20
    filled = int(bar_len * remaining_ratio)
    bar = ("=" * filled) + ("." * (bar_len - filled))
    bar_color = _resolve_hud_gradient_color(elapsed_ratio, safe_threshold)

    is_perfect = perfect_catch_enabled and elapsed_ratio <= safe_threshold
    perfect_label = "Perfect: ON" if is_perfect else "Perfect: OFF"

    hits_segment = f"Hits: {typed_count}/{len(seq)}"
    ability_segment = ability_counter_text.strip()
    time_segment = f"Time: [{bar}] {time_left:0.2f}s"

    prefix_segments = ["HUD", hits_segment]
    if ability_segment:
        prefix_segments.append(ability_segment)
    prefix_segments.append(time_segment)
    prefix_plain = " | ".join(prefix_segments)
    max_width = _terminal_line_width()
    free_space = max_width - len(prefix_plain)

    esc_segment = ""
    esc_label = "ESC sai"
    delimiter = " | "
    esc_total_len = len(delimiter) + len(esc_label)
    if free_space >= esc_total_len:
        esc_segment = esc_label

    hud_text = Text()
    hud_text.append("HUD", style=f"bold {_active_accent_color}")
    hud_text.append(f" | {hits_segment}")
    if ability_segment:
        hud_text.append(f" | {ability_segment}")
    hud_text.append(f" | {time_segment}", style=bar_color)
    hud_text.append(f" | {perfect_label}")
    weather_segment = weather_text.strip()
    if weather_segment:
        hud_text.append(f" | {weather_segment}")
    if esc_segment:
        hud_text.append(f" | {esc_segment}")

    with console.capture() as capture:
        console.print(hud_text, end="")
    return "\r" + capture.get()
