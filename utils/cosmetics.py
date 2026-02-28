from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Set

from colorama import Fore


@dataclass(frozen=True)
class UIColorDefinition:
    color_id: str
    name: str
    accent_color: str


@dataclass(frozen=True)
class UIIconDefinition:
    icon_id: str
    name: str
    badge_lines: Sequence[str]


_CATALOG_DIR = Path(__file__).resolve().parent.parent / "cosmetics_catalog"
_COLOR_CATALOG_PATH = _CATALOG_DIR / "ui_colors.json"
_ICON_CATALOG_PATH = _CATALOG_DIR / "ui_icons.json"
_DEFAULT_ACCENT_COLOR = Fore.CYAN

_FORE_COLORS_BY_NAME: Dict[str, str] = {
    name: value
    for name, value in vars(Fore).items()
    if name.isupper() and isinstance(value, str)
}


def _load_catalog_items(path: Path, root_key: str) -> List[Dict[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    raw_items = data.get(root_key)
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _load_ui_colors() -> tuple[List[str], Dict[str, UIColorDefinition]]:
    order: List[str] = []
    definitions: Dict[str, UIColorDefinition] = {}
    for item in _load_catalog_items(_COLOR_CATALOG_PATH, "colors"):
        color_id = item.get("color_id")
        name = item.get("name")
        accent_color_name = item.get("accent_color")
        if not isinstance(color_id, str) or not color_id:
            continue
        if not isinstance(name, str) or not name:
            continue
        accent_color = (
            _FORE_COLORS_BY_NAME.get(accent_color_name)
            if isinstance(accent_color_name, str)
            else None
        )
        definitions[color_id] = UIColorDefinition(
            color_id=color_id,
            name=name,
            accent_color=accent_color or _DEFAULT_ACCENT_COLOR,
        )
        order.append(color_id)
    return order, definitions


def _load_ui_icons() -> tuple[List[str], Dict[str, UIIconDefinition]]:
    order: List[str] = []
    definitions: Dict[str, UIIconDefinition] = {}
    for item in _load_catalog_items(_ICON_CATALOG_PATH, "icons"):
        icon_id = item.get("icon_id")
        name = item.get("name")
        raw_badge_lines = item.get("badge_lines")
        if not isinstance(icon_id, str) or not icon_id:
            continue
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(raw_badge_lines, list):
            continue
        badge_lines = tuple(line for line in raw_badge_lines if isinstance(line, str))
        if not badge_lines:
            continue
        definitions[icon_id] = UIIconDefinition(
            icon_id=icon_id,
            name=name,
            badge_lines=badge_lines,
        )
        order.append(icon_id)
    return order, definitions


def _fallback_color_catalog() -> tuple[List[str], Dict[str, UIColorDefinition]]:
    fallback = UIColorDefinition(
        color_id="ocean_blue",
        name="Azul Oceano",
        accent_color=Fore.CYAN,
    )
    return [fallback.color_id], {fallback.color_id: fallback}


def _fallback_icon_catalog() -> tuple[List[str], Dict[str, UIIconDefinition]]:
    fallback = UIIconDefinition(
        icon_id="cat",
        name="Gato",
        badge_lines=(
            "  /\\_/\\  ",
            " ( o.o ) ",
            "  > ^ <  ",
        ),
    )
    return [fallback.icon_id], {fallback.icon_id: fallback}


UI_COLORS_ORDER, UI_COLOR_DEFINITIONS = _load_ui_colors()
if not UI_COLORS_ORDER:
    UI_COLORS_ORDER, UI_COLOR_DEFINITIONS = _fallback_color_catalog()

UI_ICONS_ORDER, UI_ICON_DEFINITIONS = _load_ui_icons()
if not UI_ICONS_ORDER:
    UI_ICONS_ORDER, UI_ICON_DEFINITIONS = _fallback_icon_catalog()

DEFAULT_UI_COLOR_ID = UI_COLORS_ORDER[0]
DEFAULT_UI_ICON_ID = UI_ICONS_ORDER[0]


@dataclass
class PlayerCosmeticsState:
    unlocked_ui_colors: Set[str] = field(default_factory=set)
    unlocked_ui_icons: Set[str] = field(default_factory=set)
    equipped_ui_color: str = DEFAULT_UI_COLOR_ID
    equipped_icon_color: str = DEFAULT_UI_COLOR_ID
    equipped_ui_icon: str = DEFAULT_UI_ICON_ID


def create_default_cosmetics_state() -> PlayerCosmeticsState:
    return PlayerCosmeticsState(
        unlocked_ui_colors={DEFAULT_UI_COLOR_ID},
        unlocked_ui_icons={DEFAULT_UI_ICON_ID},
        equipped_ui_color=DEFAULT_UI_COLOR_ID,
        equipped_icon_color=DEFAULT_UI_COLOR_ID,
        equipped_ui_icon=DEFAULT_UI_ICON_ID,
    )


def serialize_cosmetics_state(state: PlayerCosmeticsState) -> Dict[str, object]:
    return {
        "unlocked_ui_colors": sorted(state.unlocked_ui_colors),
        "unlocked_ui_icons": sorted(state.unlocked_ui_icons),
        "equipped_ui_color": state.equipped_ui_color,
        "equipped_icon_color": state.equipped_icon_color,
        "equipped_ui_icon": state.equipped_ui_icon,
    }


def restore_cosmetics_state(raw_state: object) -> PlayerCosmeticsState:
    state = create_default_cosmetics_state()
    if not isinstance(raw_state, dict):
        return state

    raw_colors = raw_state.get("unlocked_ui_colors")
    if isinstance(raw_colors, list):
        state.unlocked_ui_colors = {
            color_id
            for color_id in raw_colors
            if isinstance(color_id, str) and color_id in UI_COLOR_DEFINITIONS
        } or {DEFAULT_UI_COLOR_ID}

    raw_icons = raw_state.get("unlocked_ui_icons")
    if isinstance(raw_icons, list):
        state.unlocked_ui_icons = {
            icon_id
            for icon_id in raw_icons
            if isinstance(icon_id, str) and icon_id in UI_ICON_DEFINITIONS
        } or {DEFAULT_UI_ICON_ID}

    equipped_color = raw_state.get("equipped_ui_color")
    if (
        isinstance(equipped_color, str)
        and equipped_color in state.unlocked_ui_colors
    ):
        state.equipped_ui_color = equipped_color

    equipped_icon_color = raw_state.get("equipped_icon_color")
    if (
        isinstance(equipped_icon_color, str)
        and equipped_icon_color in state.unlocked_ui_colors
    ):
        state.equipped_icon_color = equipped_icon_color
    else:
        state.equipped_icon_color = state.equipped_ui_color

    equipped_icon = raw_state.get("equipped_ui_icon")
    if (
        isinstance(equipped_icon, str)
        and equipped_icon in state.unlocked_ui_icons
    ):
        state.equipped_ui_icon = equipped_icon

    return state


def unlock_ui_color(state: PlayerCosmeticsState, color_id: str) -> bool:
    if color_id not in UI_COLOR_DEFINITIONS:
        return False
    if color_id in state.unlocked_ui_colors:
        return False
    state.unlocked_ui_colors.add(color_id)
    return True


def unlock_ui_icon(state: PlayerCosmeticsState, icon_id: str) -> bool:
    if icon_id not in UI_ICON_DEFINITIONS:
        return False
    if icon_id in state.unlocked_ui_icons:
        return False
    state.unlocked_ui_icons.add(icon_id)
    return True


def equip_ui_color(state: PlayerCosmeticsState, color_id: str) -> bool:
    if color_id not in state.unlocked_ui_colors:
        return False
    state.equipped_ui_color = color_id
    return True


def equip_ui_icon(state: PlayerCosmeticsState, icon_id: str) -> bool:
    if icon_id not in state.unlocked_ui_icons:
        return False
    state.equipped_ui_icon = icon_id
    return True


def equip_icon_color(state: PlayerCosmeticsState, color_id: str) -> bool:
    if color_id not in state.unlocked_ui_colors:
        return False
    state.equipped_icon_color = color_id
    return True


def list_unlocked_ui_colors(state: PlayerCosmeticsState) -> List[UIColorDefinition]:
    return [
        UI_COLOR_DEFINITIONS[color_id]
        for color_id in UI_COLORS_ORDER
        if color_id in state.unlocked_ui_colors
    ]


def list_unlocked_ui_icons(state: PlayerCosmeticsState) -> List[UIIconDefinition]:
    return [
        UI_ICON_DEFINITIONS[icon_id]
        for icon_id in UI_ICONS_ORDER
        if icon_id in state.unlocked_ui_icons
    ]
