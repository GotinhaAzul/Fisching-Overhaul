from __future__ import annotations

from dataclasses import dataclass, field
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


UI_COLORS_ORDER: List[str] = [
    "ocean_blue",
    "sunset_orange",
    "emerald_green",
    "golden",
    "rose_pink",
    "arctic_white",
    "storm_gray",
    "lava_red",
    "royal_purple",
    "neon_lime",
    "lagoon_mint",
    "open_sea_teal",
    "river_azure",
    "reef_coral",
    "swamp_olive",
    "crystal_violet",
    "brine_amber",
    "vertigo_indigo",
    "abyss_navy",
    "desolate_silver",
    "farseas_crimson",
    "cafeteria_mocha",
]

UI_COLOR_DEFINITIONS: Dict[str, UIColorDefinition] = {
    "ocean_blue": UIColorDefinition(
        color_id="ocean_blue",
        name="Azul Oceano",
        accent_color=Fore.CYAN,
    ),
    "sunset_orange": UIColorDefinition(
        color_id="sunset_orange",
        name="Laranja Sunset",
        accent_color=Fore.LIGHTRED_EX,
    ),
    "emerald_green": UIColorDefinition(
        color_id="emerald_green",
        name="Verde Esmeralda",
        accent_color=Fore.LIGHTGREEN_EX,
    ),
    "golden": UIColorDefinition(
        color_id="golden",
        name="Dourado",
        accent_color=Fore.YELLOW,
    ),
    "rose_pink": UIColorDefinition(
        color_id="rose_pink",
        name="Rosa",
        accent_color=Fore.LIGHTMAGENTA_EX,
    ),
    "arctic_white": UIColorDefinition(
        color_id="arctic_white",
        name="Branco Artico",
        accent_color=Fore.WHITE,
    ),
    "storm_gray": UIColorDefinition(
        color_id="storm_gray",
        name="Cinza Tempestade",
        accent_color=Fore.LIGHTBLACK_EX,
    ),
    "lava_red": UIColorDefinition(
        color_id="lava_red",
        name="Vermelho Lava",
        accent_color=Fore.RED,
    ),
    "royal_purple": UIColorDefinition(
        color_id="royal_purple",
        name="Roxo Real",
        accent_color=Fore.MAGENTA,
    ),
    "neon_lime": UIColorDefinition(
        color_id="neon_lime",
        name="Lima Neon",
        accent_color=Fore.GREEN,
    ),
    "lagoon_mint": UIColorDefinition(
        color_id="lagoon_mint",
        name="Menta da Lagoa",
        accent_color=Fore.LIGHTGREEN_EX,
    ),
    "open_sea_teal": UIColorDefinition(
        color_id="open_sea_teal",
        name="Azul do Mar Aberto",
        accent_color=Fore.CYAN,
    ),
    "river_azure": UIColorDefinition(
        color_id="river_azure",
        name="Azul Correnteza",
        accent_color=Fore.LIGHTBLUE_EX,
    ),
    "reef_coral": UIColorDefinition(
        color_id="reef_coral",
        name="Coral do Recife",
        accent_color=Fore.LIGHTRED_EX,
    ),
    "swamp_olive": UIColorDefinition(
        color_id="swamp_olive",
        name="Oliva do Pantano",
        accent_color=Fore.YELLOW,
    ),
    "crystal_violet": UIColorDefinition(
        color_id="crystal_violet",
        name="Violeta Cristalino",
        accent_color=Fore.LIGHTMAGENTA_EX,
    ),
    "brine_amber": UIColorDefinition(
        color_id="brine_amber",
        name="Ambar Salmoura",
        accent_color=Fore.YELLOW,
    ),
    "vertigo_indigo": UIColorDefinition(
        color_id="vertigo_indigo",
        name="Indigo Vertigo",
        accent_color=Fore.BLUE,
    ),
    "abyss_navy": UIColorDefinition(
        color_id="abyss_navy",
        name="Marinho Abissal",
        accent_color=Fore.BLUE,
    ),
    "desolate_silver": UIColorDefinition(
        color_id="desolate_silver",
        name="Prata Desolada",
        accent_color=Fore.WHITE,
    ),
    "farseas_crimson": UIColorDefinition(
        color_id="farseas_crimson",
        name="Carmesim de Farseas",
        accent_color=Fore.RED,
    ),
    "cafeteria_mocha": UIColorDefinition(
        color_id="cafeteria_mocha",
        name="Mocha da Cafeteria",
        accent_color=Fore.LIGHTYELLOW_EX,
    ),
}

UI_ICONS_ORDER: List[str] = [
    "cat",
    "fish",
    "star",
    "wave",
    "anchor",
    "crab",
    "shell",
    "hook",
    "boat",
    "treasure",
    "pool_lagoa",
    "pool_mar",
    "pool_rio",
    "pool_grandreef",
    "pool_pantano",
    "pool_crystalcove",
    "pool_brinepool",
    "pool_vertigo",
    "pool_thedepths",
    "pool_desolatedeep",
    "pool_farseas_eye",
    "pool_cafeteria_coffee",
]

UI_ICON_DEFINITIONS: Dict[str, UIIconDefinition] = {
    "cat": UIIconDefinition(
        icon_id="cat",
        name="Gato",
        badge_lines=(
            "  /\\_/\\  ",
            " ( o.o ) ",
            "  > ^ <  ",
        ),
    ),
    "fish": UIIconDefinition(
        icon_id="fish",
        name="Peixe",
        badge_lines=(
            "  ><(((>  ",
            "   / _ \\  ",
            "  /_/ \\_\\ ",
        ),
    ),
    "star": UIIconDefinition(
        icon_id="star",
        name="Estrela",
        badge_lines=(
            "    /\\    ",
            " < (**) > ",
            "    \\/    ",
        ),
    ),
    "wave": UIIconDefinition(
        icon_id="wave",
        name="Onda",
        badge_lines=(
            " ~~~~~~~~ ",
            "  ~~~~~~  ",
            " ~~~~~~~~ ",
        ),
    ),
    "anchor": UIIconDefinition(
        icon_id="anchor",
        name="Ancora",
        badge_lines=(
            "    |     ",
            " --(_)--  ",
            "   / \\    ",
        ),
    ),
    "crab": UIIconDefinition(
        icon_id="crab",
        name="Caranguejo",
        badge_lines=(
            " \\_\\_/ /  ",
            " (o   o)  ",
            " /_/^\\_\\  ",
        ),
    ),
    "shell": UIIconDefinition(
        icon_id="shell",
        name="Concha",
        badge_lines=(
            "  .----.  ",
            " / .--. \\ ",
            " '----'  ",
        ),
    ),
    "hook": UIIconDefinition(
        icon_id="hook",
        name="Anzol",
        badge_lines=(
            "    __    ",
            "   / /_   ",
            "   \\__/   ",
        ),
    ),
    "boat": UIIconDefinition(
        icon_id="boat",
        name="Barco",
        badge_lines=(
            "    |\\    ",
            "   /_|_\\  ",
            " ~~~|~~~  ",
        ),
    ),
    "treasure": UIIconDefinition(
        icon_id="treasure",
        name="Tesouro",
        badge_lines=(
            " .------. ",
            " | [$$] | ",
            " '------' ",
        ),
    ),
    "pool_lagoa": UIIconDefinition(
        icon_id="pool_lagoa",
        name="Lagoa",
        badge_lines=(
            "   .--.   ",
            " ~(____)~ ",
            "   '~~'   ",
        ),
    ),
    "pool_mar": UIIconDefinition(
        icon_id="pool_mar",
        name="Mar Aberto",
        badge_lines=(
            "  ~~~~~~  ",
            " ~~/\\~~~~ ",
            "~~~\\/~~~~ ",
        ),
    ),
    "pool_rio": UIIconDefinition(
        icon_id="pool_rio",
        name="Rio Correnteza",
        badge_lines=(
            " ~~>>~~~  ",
            ">~~>>~~>  ",
            " ~~>>~~~  ",
        ),
    ),
    "pool_grandreef": UIIconDefinition(
        icon_id="pool_grandreef",
        name="Grande Recife",
        badge_lines=(
            "   /\\/\\   ",
            " _/\\||/\\_ ",
            "   /||\\   ",
        ),
    ),
    "pool_pantano": UIIconDefinition(
        icon_id="pool_pantano",
        name="Pantano Mushgrove",
        badge_lines=(
            "  _^_  _^_",
            " (___)(___)",
            "  ||    || ",
        ),
    ),
    "pool_crystalcove": UIIconDefinition(
        icon_id="pool_crystalcove",
        name="Angra Cristal",
        badge_lines=(
            "   /\\ /\\  ",
            "  /__V__\\ ",
            "   \\/ \\/  ",
        ),
    ),
    "pool_brinepool": UIIconDefinition(
        icon_id="pool_brinepool",
        name="Piscina de Salmoura",
        badge_lines=(
            "   .--.   ",
            " ~(xxxx)~ ",
            "   \\/\\/   ",
        ),
    ),
    "pool_vertigo": UIIconDefinition(
        icon_id="pool_vertigo",
        name="Vertigo",
        badge_lines=(
            "   .--.   ",
            "  / @@ \\  ",
            "  \\_@@_/  ",
        ),
    ),
    "pool_thedepths": UIIconDefinition(
        icon_id="pool_thedepths",
        name="As profundezas",
        badge_lines=(
            "  ~~~~~~  ",
            "   \\  /   ",
            "    \\/    ",
        ),
    ),
    "pool_desolatedeep": UIIconDefinition(
        icon_id="pool_desolatedeep",
        name="Profundezas Desoladas",
        badge_lines=(
            "  _|[]|_  ",
            " |  __  | ",
            " |_/  \\_| ",
        ),
    ),
    "pool_farseas_eye": UIIconDefinition(
        icon_id="pool_farseas_eye",
        name="Olho de Farseas",
        badge_lines=(
            "  .-===-. ",
            " (  o o ) ",
            "  '-___-' ",
        ),
    ),
    "pool_cafeteria_coffee": UIIconDefinition(
        icon_id="pool_cafeteria_coffee",
        name="Xicara da Cafeteria",
        badge_lines=(
            "  (____)  ",
            "  |____|) ",
            "   ||||   ",
        ),
    ),
}

DEFAULT_UI_COLOR_ID = UI_COLORS_ORDER[0]
DEFAULT_UI_ICON_ID = UI_ICONS_ORDER[0]


@dataclass
class PlayerCosmeticsState:
    unlocked_ui_colors: Set[str] = field(default_factory=set)
    unlocked_ui_icons: Set[str] = field(default_factory=set)
    equipped_ui_color: str = DEFAULT_UI_COLOR_ID
    equipped_ui_icon: str = DEFAULT_UI_ICON_ID


def create_default_cosmetics_state() -> PlayerCosmeticsState:
    return PlayerCosmeticsState(
        unlocked_ui_colors={DEFAULT_UI_COLOR_ID},
        unlocked_ui_icons={DEFAULT_UI_ICON_ID},
        equipped_ui_color=DEFAULT_UI_COLOR_ID,
        equipped_ui_icon=DEFAULT_UI_ICON_ID,
    )


def serialize_cosmetics_state(state: PlayerCosmeticsState) -> Dict[str, object]:
    return {
        "unlocked_ui_colors": sorted(state.unlocked_ui_colors),
        "unlocked_ui_icons": sorted(state.unlocked_ui_icons),
        "equipped_ui_color": state.equipped_ui_color,
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
