from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator

import utils.market as market
from utils.baits import BaitDefinition
from utils.inventory import InventoryEntry, calculate_entry_value
from utils.mutations import Mutation
from utils.pagination import PAGE_NEXT_KEY
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


def _make_named_fish(index: int) -> _DummyFish:
    return _DummyFish(
        name=f"Peixe {index}",
        rarity="Comum",
        base_value=10.0 + index,
        kg_min=1.0,
        kg_max=5.0,
    )


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


def test_show_market_sell_individual_blocks_unsellable_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    inventory = [
        InventoryEntry(
            name=fish.name,
            rarity=fish.rarity,
            kg=2.0,
            base_value=fish.base_value,
            is_unsellable=True,
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

    assert balance == 0.0
    assert level == 1
    assert xp == 0
    assert len(inventory) == 1
    assert inventory[0].name == fish.name
    assert money_earned == []
    assert sold_names == []
    assert delivered_names == []


def test_show_market_sell_individual_pagination_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, _ = _make_pool_and_fish()
    fishes = [_make_named_fish(index) for index in range(1, 12)]
    inventory = [
        InventoryEntry(
            name=fish.name,
            rarity=fish.rarity,
            kg=1.0 + (index * 0.1),
            base_value=fish.base_value,
        )
        for index, fish in enumerate(fishes, start=1)
    ]
    target_entry = inventory[-1]
    money_earned: list[float] = []
    sold_names: list[str] = []
    delivered_names: list[str] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(
        "builtins.input",
        _InputFeeder(["1", "1", PAGE_NEXT_KEY, "1", "", "0"]),
    )

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=0.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish for fish in fishes},
        available_mutations=[],
        on_money_earned=money_earned.append,
        on_fish_sold=lambda entry: sold_names.append(entry.name),
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    expected_value = calculate_entry_value(target_entry)
    assert balance == expected_value
    assert level == 1
    assert xp == 0
    assert len(inventory) == 10
    assert target_entry.name not in [entry.name for entry in inventory]
    assert money_earned == [expected_value]
    assert sold_names == [target_entry.name]
    assert delivered_names == [target_entry.name]


def test_show_market_sell_all_keeps_unsellable_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    sellable = InventoryEntry(
        name=fish.name,
        rarity=fish.rarity,
        kg=2.0,
        base_value=fish.base_value,
    )
    unsellable = InventoryEntry(
        name="Pacu de Missao",
        rarity="Comum",
        kg=1.0,
        base_value=8.0,
        is_unsellable=True,
    )
    inventory = [sellable, unsellable]
    money_earned: list[float] = []
    sold_names: list[str] = []
    delivered_names: list[str] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", _InputFeeder(["1", "2", "", "0"]))

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=0.0,
        selected_pool=selected_pool,
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

    expected_value = calculate_entry_value(sellable)
    assert balance == expected_value
    assert level == 1
    assert xp == 0
    assert len(inventory) == 1
    assert inventory[0].name == "Pacu de Missao"
    assert inventory[0].is_unsellable is True
    assert money_earned == [expected_value]
    assert sold_names == [fish.name]
    assert delivered_names == [fish.name]


def test_show_market_buy_rod_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    owned_rods = [starter]

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", _InputFeeder(["2", "1", "s", "", "0"]))

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


def test_show_market_pool_order_ignores_unsellable_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    inventory = [
        InventoryEntry(
            name=fish.name,
            rarity=fish.rarity,
            kg=2.0,
            base_value=fish.base_value,
            is_unsellable=True,
        ),
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
    sold_names: list[str] = []
    delivered_names: list[str] = []

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.time, "time", lambda: 100.0)
    monkeypatch.setattr("builtins.input", _InputFeeder(["3", "", "0"]))

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
        on_fish_sold=lambda entry: sold_names.append(entry.name),
        on_fish_delivered=lambda entry: delivered_names.append(entry.name),
    )

    assert balance == 10.0
    assert level == 1
    assert xp == 0
    assert [entry.name for entry in inventory] == [fish.name, "Pacu"]
    assert selected_pool.name in pool_orders
    assert sold_names == []
    assert delivered_names == []


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
    monkeypatch.setattr(market, "filter_mutations_for_appraisal", lambda mutations: list(mutations))
    monkeypatch.setattr(market, "choose_mutation", lambda _mutations: mutation)
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", "1", "t", "0", "0"]))

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


def test_show_market_appraise_selection_pagination_flow_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, _ = _make_pool_and_fish()
    fishes = [_make_named_fish(index) for index in range(1, 12)]
    inventory = [
        InventoryEntry(
            name=fish.name,
            rarity=fish.rarity,
            kg=2.0,
            base_value=fish.base_value,
        )
        for fish in fishes
    ]
    target_entry = inventory[-1]

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.random, "uniform", lambda _a, _b: 4.2)
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", PAGE_NEXT_KEY, "1", "t", "0", "0"]))

    expected_cost = max(1.0, calculate_entry_value(target_entry) * 0.35)

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish for fish in fishes},
        available_mutations=[],
        equipped_rod=starter,
    )

    assert level == 1
    assert xp == 0
    assert balance == 100.0 - expected_cost
    assert target_entry.kg == 4.2
    assert target_entry.mutation_name is None
    assert all(entry.kg == 2.0 for entry in inventory[:-1])


def test_show_market_appraise_quick_repeat_same_fish_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    entry = InventoryEntry(name=fish.name, rarity=fish.rarity, kg=2.0, base_value=fish.base_value)
    inventory = [entry]

    kg_rolls = iter([2.4, 2.9])
    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.random, "uniform", lambda _a, _b: next(kg_rolls))
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", "1", "t", "t", "0", "0"]))

    original_value = calculate_entry_value(entry)
    expected_first_cost = max(1.0, original_value * 0.35)
    value_after_first = calculate_entry_value(
        InventoryEntry(name=fish.name, rarity=fish.rarity, kg=2.4, base_value=fish.base_value)
    )
    expected_second_cost = max(1.0, value_after_first * 0.35)

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        equipped_rod=starter,
    )

    assert level == 1
    assert xp == 0
    assert balance == 100.0 - expected_first_cost - expected_second_cost
    assert entry.kg == 2.9
    assert entry.mutation_name is None
    assert entry.mutation_xp_multiplier == 1.0
    assert entry.mutation_gold_multiplier == 1.0


def test_show_market_appraise_mutation_confirmation_cancel_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    entry = InventoryEntry(
        name=fish.name,
        rarity=fish.rarity,
        kg=2.0,
        base_value=fish.base_value,
        mutation_name="Albino",
        mutation_xp_multiplier=1.5,
        mutation_gold_multiplier=1.1,
    )
    inventory = [entry]
    money_spent: list[float] = []

    def _unexpected_uniform(_a: float, _b: float) -> float:
        raise AssertionError("Appraise should not reroll KG when mutation confirmation is canceled.")

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.random, "uniform", _unexpected_uniform)
    monkeypatch.setattr(
        market,
        "choose_mutation",
        lambda _mutations: (_ for _ in ()).throw(
            AssertionError("Appraise should not reroll mutation when confirmation is canceled.")
        ),
    )
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", "1", "t", "n", "0", "0"]))

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=50.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[],
        equipped_rod=starter,
        on_money_spent=money_spent.append,
    )

    assert level == 1
    assert xp == 0
    assert balance == 50.0
    assert money_spent == []
    assert entry.kg == 2.0
    assert entry.mutation_name == "Albino"
    assert entry.mutation_xp_multiplier == 1.5
    assert entry.mutation_gold_multiplier == 1.1


def test_show_market_appraise_mutation_confirmation_accept_characterization(monkeypatch) -> None:
    starter, premium = _make_rods()
    selected_pool, fish = _make_pool_and_fish()
    entry = InventoryEntry(
        name=fish.name,
        rarity=fish.rarity,
        kg=2.0,
        base_value=fish.base_value,
        mutation_name="Albino",
        mutation_xp_multiplier=1.5,
        mutation_gold_multiplier=1.1,
    )
    inventory = [entry]
    mutation = Mutation(
        name="Noir",
        description="",
        xp_multiplier=1.6,
        gold_multiplier=1.2,
        chance=1.0,
        required_rods=(),
    )

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.random, "uniform", lambda _a, _b: 2.6)
    monkeypatch.setattr(market, "filter_mutations_for_appraisal", lambda mutations: list(mutations))
    monkeypatch.setattr(market, "choose_mutation", lambda _mutations: mutation)
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", "1", "t", "s", "0", "0"]))

    original_value = calculate_entry_value(entry)
    expected_cost = max(1.0, original_value * 0.35)

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=80.0,
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
    assert balance == 80.0 - expected_cost
    assert entry.kg == 2.6
    assert entry.mutation_name == "Noir"
    assert entry.mutation_xp_multiplier == 1.6
    assert entry.mutation_gold_multiplier == 1.2


def test_show_market_appraise_excludes_rod_exclusive_mutations(monkeypatch) -> None:
    starter, premium = _make_rods()
    starter = replace(starter, name="Promessa Luminescente")
    selected_pool, fish = _make_pool_and_fish()
    entry = InventoryEntry(name=fish.name, rarity=fish.rarity, kg=2.0, base_value=fish.base_value)
    inventory = [entry]
    global_mutation = Mutation(
        name="Albino",
        description="",
        xp_multiplier=1.5,
        gold_multiplier=1.1,
        chance=1.0,
        required_rods=(),
    )
    rod_exclusive_mutation = Mutation(
        name="Prometido",
        description="",
        xp_multiplier=1.8,
        gold_multiplier=1.4,
        chance=1.0,
        required_rods=("Promessa Luminescente",),
    )

    def _choose_only_from_global_pool(mutations: list[Mutation]) -> Mutation:
        assert [mutation.name for mutation in mutations] == ["Albino"]
        return mutations[0]

    monkeypatch.setattr(market, "clear_screen", lambda: None)
    monkeypatch.setattr(market.random, "uniform", lambda _a, _b: 2.8)
    monkeypatch.setattr(market, "choose_mutation", _choose_only_from_global_pool)
    monkeypatch.setattr("builtins.input", _InputFeeder(["4", "1", "t", "0", "0"]))

    balance, level, xp = market.show_market(
        inventory=inventory,
        balance=100.0,
        selected_pool=selected_pool,
        level=1,
        xp=0,
        available_rods=[starter, premium],
        owned_rods=[starter],
        fish_by_name={fish.name: fish},
        available_mutations=[global_mutation, rod_exclusive_mutation],
        equipped_rod=starter,
    )

    assert level == 1
    assert xp == 0
    assert balance < 100.0
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
