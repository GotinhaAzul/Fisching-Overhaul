from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest
import utils.market as market
from utils.modern_ui import MenuOption
from utils.inventory import InventoryEntry
from utils.rods import Rod
from utils.rod_upgrades import (
    MAX_UPGRADE_PERCENT,
    MIN_UPGRADE_PERCENT,
    RodUpgradeState,
    UpgradeRequirement,
    apply_stat_bonus,
    calculate_upgrade_bonus,
    generate_fish_requirements,
    get_effective_rod,
    restore_rod_upgrade_state,
)


@dataclass
class _DummyFish:
    name: str
    rarity: str
    base_value: float
    kg_min: float
    kg_max: float


@dataclass
class _DummyPool:
    name: str
    fish_profiles: list[_DummyFish]
    folder: Path


class _InputFeeder:
    def __init__(self, values: list[str]) -> None:
        self._iter: Iterator[str] = iter(values)

    def __call__(self, _prompt: str = "") -> str:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise AssertionError("Unexpected extra input prompt.") from exc


def _rod(
    name: str,
    *,
    price: float = 0.0,
    luck: float = 0.10,
    kg_max: float = 100.0,
    control: float = 0.40,
) -> Rod:
    return Rod(
        name=name,
        luck=luck,
        kg_max=kg_max,
        control=control,
        description=name,
        price=price,
        unlocked_default=price == 0.0,
    )


def test_restore_and_apply_rod_upgrade_state_characterization() -> None:
    state = restore_rod_upgrade_state(
        {
            "Ignis": {
                "luck": 0.12,
                "kg_max": 0.30,
                "control": 0.001,
                "unknown": 0.9,
            },
            "Corrompida": "bad",
            "Zero": {"luck": 0},
        }
    )

    assert state.to_dict() == {
        "Ignis": {
            "luck": 0.12,
            "kg_max": MAX_UPGRADE_PERCENT,
            "control": MIN_UPGRADE_PERCENT,
        }
    }

    ignis = _rod("Ignis", price=1000.0)
    effective_ignis = get_effective_rod(ignis, state)
    assert effective_ignis.luck == pytest.approx(0.112)
    assert effective_ignis.kg_max == pytest.approx(125.0)
    assert effective_ignis.control == pytest.approx(0.404)
    assert apply_stat_bonus(ignis, "control", 0.25) == pytest.approx(0.5)


def test_generate_requirements_and_bonus_characterization(monkeypatch) -> None:
    fish_a = _DummyFish("Tilapia", "Comum", 10.0, 1.0, 3.0)
    fish_b = _DummyFish("Piracanjuba", "Raro", 20.0, 1.0, 4.0)

    randint_values = iter([2, 5, 2])
    monkeypatch.setattr(
        "utils.rod_upgrades.random.randint",
        lambda _a, _b: next(randint_values),
    )
    monkeypatch.setattr(
        "utils.rod_upgrades.random.sample",
        lambda population, count: list(population)[:count],
    )

    requirements = generate_fish_requirements([fish_a, fish_b], _rod("Ignis"))
    assert requirements == [
        UpgradeRequirement(fish_name="Tilapia", rarity="Comum", count=5),
        UpgradeRequirement(fish_name="Piracanjuba", rarity="Raro", count=2),
    ]

    monkeypatch.setattr("utils.rod_upgrades.random.uniform", lambda _a, _b: 0.04)
    assert calculate_upgrade_bonus(requirements) == MAX_UPGRADE_PERCENT

    monkeypatch.setattr("utils.rod_upgrades.random.uniform", lambda _a, _b: -0.08)
    assert calculate_upgrade_bonus([]) == MIN_UPGRADE_PERCENT


def test_show_market_upgrade_flow_characterization(monkeypatch) -> None:
    starter = _rod("Vara Bambu")
    premium = _rod("Vara Carbono", price=50.0)
    fish = _DummyFish("Tilapia", "Comum", 10.0, 1.0, 3.0)
    bonus_fish = _DummyFish("Dourado", "Raro", 40.0, 2.0, 5.0)
    locked_fish = _DummyFish("Piranha", "Epico", 70.0, 1.0, 2.0)
    selected_pool = _DummyPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa"),
    )
    unlocked_bonus_pool = _DummyPool(
        name="Rio Dourado",
        fish_profiles=[bonus_fish],
        folder=Path("rio_dourado"),
    )
    locked_pool = _DummyPool(
        name="Caverna Proibida",
        fish_profiles=[locked_fish],
        folder=Path("caverna_proibida"),
    )
    inventory = [
        InventoryEntry(name="Dourado", rarity="Raro", kg=3.0, base_value=40.0),
        InventoryEntry(name="Pacu", rarity="Comum", kg=1.2, base_value=8.0),
    ]
    money_spent: list[float] = []
    delivered_names: list[str] = []
    upgrade_state = RodUpgradeState()
    seen_requirement_pool: list[str] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    def _capture_requirements(pool_fish, _rod):
        seen_requirement_pool.extend(fish_profile.name for fish_profile in pool_fish)
        return [UpgradeRequirement("Dourado", "Raro", 1)]

    monkeypatch.setattr(market, "generate_fish_requirements", _capture_requirements)
    monkeypatch.setattr(market, "calculate_upgrade_bonus", lambda _requirements: 0.18)
    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["6", "2", "1", "1", "0", "0"]),
    )

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=1000.0,
        selected_pool=selected_pool,
        level=20,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter, premium],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        pools=[selected_pool, unlocked_bonus_pool, locked_pool],
        unlocked_pools={"Lagoa Tranquila", "rio_dourado"},
        rod_upgrade_state=upgrade_state,
        on_money_spent=money_spent.append,
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    assert balance == 600.0
    assert level == 20
    assert xp == 0
    assert seen_requirement_pool == ["Tilapia", "Dourado"]
    assert [entry.name for entry in inventory] == ["Pacu"]
    assert money_spent == [400.0]
    assert delivered_names == ["Dourado"]
    assert upgrade_state.to_dict() == {"Vara Carbono": {"luck": 0.18}}


def test_show_market_upgrade_blocks_unsellable_materials_characterization(monkeypatch) -> None:
    starter = _rod("Vara Bambu")
    premium = _rod("Vara Carbono", price=50.0)
    fish = _DummyFish("Tilapia", "Comum", 10.0, 1.0, 3.0)
    selected_pool = _DummyPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa"),
    )
    inventory = [
        InventoryEntry(
            name="Tilapia",
            rarity="Comum",
            kg=2.0,
            base_value=10.0,
            is_unsellable=True,
        ),
        InventoryEntry(name="Pacu", rarity="Comum", kg=1.2, base_value=8.0),
    ]
    money_spent: list[float] = []
    delivered_names: list[str] = []
    upgrade_state = RodUpgradeState()

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(
        market,
        "generate_fish_requirements",
        lambda _pool_fish, _rod: [UpgradeRequirement("Tilapia", "Comum", 1)],
    )
    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["6", "2", "1", "0", "0"]),
    )

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=1000.0,
        selected_pool=selected_pool,
        level=20,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter, premium],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        rod_upgrade_state=upgrade_state,
        on_money_spent=money_spent.append,
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    assert balance == 1000.0
    assert level == 20
    assert xp == 0
    assert [entry.name for entry in inventory] == ["Tilapia", "Pacu"]
    assert inventory[0].is_unsellable is True
    assert money_spent == []
    assert delivered_names == []
    assert upgrade_state.to_dict() == {}


def test_show_market_persists_upgrade_recipe_per_rod_until_upgrade(monkeypatch) -> None:
    starter = _rod("Vara Bambu")
    premium = _rod("Vara Carbono", price=50.0)
    fish = _DummyFish("Tilapia", "Comum", 10.0, 1.0, 3.0)
    selected_pool = _DummyPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa"),
    )
    inventory = [
        InventoryEntry(name="Dourado", rarity="Raro", kg=3.0, base_value=40.0),
        InventoryEntry(name="Pacu", rarity="Comum", kg=1.2, base_value=8.0),
    ]
    delivered_names: list[str] = []
    upgrade_state = RodUpgradeState()
    requirement_calls: list[int] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)

    def _generate_requirements(_pool_fish, _rod):
        requirement_calls.append(1)
        if len(requirement_calls) == 1:
            return [UpgradeRequirement("Dourado", "Raro", 1)]
        return [UpgradeRequirement("Pacu", "Comum", 1)]

    monkeypatch.setattr(market, "generate_fish_requirements", _generate_requirements)
    monkeypatch.setattr(market, "calculate_upgrade_bonus", lambda _requirements: 0.18)

    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["6", "2", "1", "0", "0"]),
    )
    balance, _, _ = market.show_market(
        inventory=inventory,
        balance=1000.0,
        selected_pool=selected_pool,
        level=20,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter, premium],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        rod_upgrade_state=upgrade_state,
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    assert balance == 1000.0
    assert len(requirement_calls) == 1
    assert upgrade_state.get_recipe("Vara Carbono") is not None
    assert [entry.name for entry in inventory] == ["Dourado", "Pacu"]

    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["6", "2", "1", "1", "0", "0"]),
    )
    balance, _, _ = market.show_market(
        inventory=inventory,
        balance=1000.0,
        selected_pool=selected_pool,
        level=20,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter, premium],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        rod_upgrade_state=upgrade_state,
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    assert balance == 600.0
    assert len(requirement_calls) == 1
    assert [entry.name for entry in inventory] == ["Pacu"]
    assert delivered_names == ["Dourado"]
    assert upgrade_state.get_recipe("Vara Carbono") is None
    assert upgrade_state.to_dict() == {"Vara Carbono": {"luck": 0.18}}


def test_show_market_hides_zero_value_stats_from_upgrade_selection(monkeypatch) -> None:
    starter = _rod("Vara Bambu")
    premium = _rod("Vara Prisma", price=50.0, control=0.0)
    fish = _DummyFish("Tilapia", "Comum", 10.0, 1.0, 3.0)
    selected_pool = _DummyPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa"),
    )
    captured_options: list[MenuOption] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)

    def _capture_panel(
        title,
        *,
        options,
        **_kwargs,
    ):
        if title == "Escolha o Stat":
            captured_options[:] = list(options)

    monkeypatch.setattr(market, "print_menu_panel", _capture_panel)
    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["6", "2", "0", "0"]),
    )

    balance, level, xp = market.show_market(
        inventory=[],
        balance=1000.0,
        selected_pool=selected_pool,
        level=20,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter, premium],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        rod_upgrade_state=RodUpgradeState(),
    )

    assert balance == 1000.0
    assert level == 20
    assert xp == 0
    assert [option.label for option in captured_options] == ["Sorte", "Peso Max", "Voltar"]


def test_show_market_hides_blocked_market_options_characterization(monkeypatch) -> None:
    starter = _rod("Vara Bambu")
    fish = _DummyFish("Tilapia", "Comum", 10.0, 1.0, 3.0)
    selected_pool = _DummyPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa"),
    )
    captured_lines: list[str] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)

    def _capture_lines(lines, gap_lines=1) -> None:
        del gap_lines
        captured_lines[:] = list(lines)

    monkeypatch.setattr(market, "print_spaced_lines", _capture_lines)
    monkeypatch.setattr("builtins.input", _InputFeeder(["0"]))

    balance, level, xp = market.show_market(
        inventory=[],
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[],
    )

    assert balance == 100.0
    assert level == 1
    assert xp == 0
    assert "6. Melhorar vara" not in captured_lines
    assert "7. Crafting de varas (bloqueado)" not in captured_lines
