from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import utils.market as market
from utils.baits import BaitDefinition
from utils.inventory import InventoryEntry, calculate_entry_value
from utils.mutations import Mutation
from utils.rods import Rod


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


@dataclass
class _FakeCrate:
    crate_id: str
    name: str
    price: float
    roll_min: int
    roll_max: int
    baits: tuple[BaitDefinition, ...]
    rarity_chances: dict[str, float]

    def expected_rolls(self) -> float:
        return 1.0

    def open_crate(self) -> list[BaitDefinition]:
        return [self.baits[0]]


class _InputFeeder:
    def __init__(self, values: list[str]) -> None:
        self._iter: Iterator[str] = iter(values)

    def __call__(self, _prompt: str = "") -> str:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise AssertionError("Unexpected extra input prompt.") from exc


def _make_rods() -> tuple[Rod, Rod]:
    starter = Rod(
        name="Vara Bambu",
        luck=0.0,
        kg_max=100.0,
        control=0.0,
        description="Starter",
        price=0.0,
        unlocked_default=True,
    )
    premium = Rod(
        name="Vara Carbono",
        luck=0.1,
        kg_max=150.0,
        control=0.2,
        description="Premium",
        price=50.0,
    )
    return starter, premium


def _make_pool_and_fish() -> tuple[_DummyPool, _DummyFish]:
    fish = _DummyFish(
        name="Tilapia",
        rarity="Comum",
        base_value=10.0,
        kg_min=1.0,
        kg_max=3.0,
    )
    pool = _DummyPool(
        name="Lagoa Tranquila",
        fish_profiles=[fish],
        folder=Path("lagoa"),
    )
    return pool, fish


def test_show_market_sell_individual_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    inventory = [
        InventoryEntry(
            name=fish.name,
            rarity=fish.rarity,
            kg=2.0,
            base_value=fish.base_value,
        )
    ]
    money_earned: list[float] = []
    sold_names: list[str] = []
    delivered_names: list[str] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["1", "1", "1", "", "0"]),
    )

    balance, level, xp = market.show_market(
        inventory,
        0.0,
        selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        on_money_earned=money_earned.append,
        on_fish_sold=lambda entry: sold_names.append(entry.name),
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    expected_value = calculate_entry_value(
        InventoryEntry(name=fish.name, rarity=fish.rarity, kg=2.0, base_value=fish.base_value)
    )
    assert inventory == []
    assert balance == expected_value
    assert level == 1
    assert xp == 0
    assert money_earned == [expected_value]
    assert sold_names == [fish.name]
    assert delivered_names == [fish.name]


def test_show_market_buy_rod_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    owned_rods = [starter]

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", _InputFeeder(["2", "1", "", "0"]))

    balance, level, xp = market.show_market(
        inventory=[],
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=owned_rods,
        fish_by_name={fish.name: fish},
        available_mutations=[],
    )

    assert [rod.name for rod in owned_rods] == ["Vara Bambu", "Vara Carbono"]
    assert balance == 50.0
    assert level == 1
    assert xp == 0


def test_show_market_pool_order_delivery_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    inventory = [
        InventoryEntry(name=fish.name, rarity=fish.rarity, kg=2.0, base_value=fish.base_value),
        InventoryEntry(name="Pacu", rarity="Comum", kg=1.0, base_value=8.0),
    ]
    pool_orders = {
        selected_pool.name: market.PoolMarketOrder(
            pool_name=selected_pool.name,
            fish_name=fish.name,
            rarity=fish.rarity,
            required_count=1,
            reward_money=30.0,
            reward_xp=15,
            expires_at=1_000_000_000.0,
        )
    }

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.time, "time", lambda: 100.0)
    monkeypatch.setattr("builtins.input", _InputFeeder(["3", "s", "", "0"]))

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=10.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        pool_orders=pool_orders,
    )

    assert balance == 40.0
    assert level == 1
    assert xp == 15
    assert [entry.name for entry in inventory] == ["Pacu"]
    assert selected_pool.name in pool_orders
    assert pool_orders[selected_pool.name].required_count >= market.ORDER_MIN_COUNT


def test_show_market_appraise_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    entry = InventoryEntry(name=fish.name, rarity=fish.rarity, kg=2.0, base_value=fish.base_value)
    inventory = [entry]
    mutation = Mutation(
        name="Albino",
        description="",
        xp_multiplier=1.5,
        gold_multiplier=1.1,
        chance=1.0,
        required_rods=(),
    )

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.random, "uniform", lambda _a, _b: 2.8)
    monkeypatch.setattr(market, "filter_mutations_for_rod", lambda mutations, _rod_name: list(mutations))
    monkeypatch.setattr(market, "choose_mutation", lambda _mutations: mutation)
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", "1", "s", "", "0"]))

    original_value = calculate_entry_value(entry)
    expected_cost = max(1.0, original_value * 0.35)

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[mutation],
        equipped_rod=starter,
    )

    assert level == 1
    assert xp == 0
    assert balance == 100.0 - expected_cost
    assert entry.kg == 2.8
    assert entry.mutation_name == "Albino"
    assert entry.mutation_xp_multiplier == 1.5
    assert entry.mutation_gold_multiplier == 1.1


def test_show_market_bait_crate_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    bait = BaitDefinition(
        bait_id="cheap/minhoca",
        crate_id="cheap",
        name="Minhoca",
        control=0.0,
        luck=0.0,
        kg_plus=0.0,
        rarity="Comum",
    )
    crate = _FakeCrate(
        crate_id="cheap",
        name="Caixa barata",
        price=10.0,
        roll_min=1,
        roll_max=1,
        baits=(bait,),
        rarity_chances={"Comum": 1.0},
    )
    bait_inventory: dict[str, int] = {}
    spent: list[float] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", _InputFeeder(["5", "1", "2", "s", "", "0", "0"]))

    balance, level, xp = market.show_market(
        inventory=[],
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        bait_crates=[crate],
        bait_inventory=bait_inventory,
        bait_by_id={bait.bait_id: bait},
        on_money_spent=spent.append,
    )

    assert level == 1
    assert xp == 0
    assert balance == 80.0
    assert bait_inventory == {"cheap/minhoca": 2}
    assert spent == [20.0]
