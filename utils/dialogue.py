import random


MENU_LINES = [
    "🌊 A maré está agitada hoje.",
    "🐟 Dizem que os peixes estão famintos!",
    "☀️ Um dia perfeito para lançar a isca.",
    "🌬️ O vento sopra a favor dos pescadores.",
]

MARKET_LINES = [
    "🧺 Peixe fresco chegando toda hora!",
    "💰 Bom preço para quem vende hoje.",
    "🪝 Equipamentos novos saindo do forno.",
    "🧊 Mantenha o peixe gelado para valorizar!",
]


def get_menu_line() -> str:
    return random.choice(MENU_LINES)


def get_market_line() -> str:
    return random.choice(MARKET_LINES)
