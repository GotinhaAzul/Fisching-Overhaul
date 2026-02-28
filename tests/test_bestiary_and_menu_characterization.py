from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import utils.bestiary as bestiary
import utils.menu_input as menu_input
from utils.pagination import PAGE_NEXT_KEY, PAGE_PREV_KEY
from utils.bestiary_rewards import (
    BestiaryRewardDefinition,
    BestiaryRewardState,
    get_claimable_bestiary_rewards,
    load_bestiary_rewards,
)
from utils.rods import Rod


@dataclass
class _DummyFish:
    name: str
    rarity: str = "Comum"
    description: str = ""
    kg_min: float = 1.0
    kg_max: float = 2.0
    counts_for_bestiary_completion: bool = True


@dataclass
class _DummyPool:
    name: str
    fish_profiles: list[_DummyFish]
    folder: Path
    description: str = ""
    counts_for_bestiary_completion: bool = True
    hidden_from_bestiary_until_unlocked: bool = False


class _ChoiceFeeder:
    def __init__(self, values: list[str]) -> None:
        self._values = values
        self._iter: Iterator[str] = iter(values)
        self.calls = 0

    def __call__(
        self,
        _prompt: str,
        _total_pages: int,
        *,
        extra_instant_keys: Optional[set[str]] = None,
    ) -> str:
        del extra_instant_keys
        self.calls += 1
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise AssertionError("Unexpected extra choice prompt.") from exc

    @property
    def total_expected(self) -> int:
        return len(self._values)


def _make_rod(name: str) -> Rod:
    return Rod(
        name=name,
        luck=0.0,
        kg_max=100.0,
        control=0.0,
        description="",
        price=0.0,
    )


def test_read_menu_choice_strip_path_characterization(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt="": "  1  ")
    assert menu_input.read_menu_choice("> ") == "1"


def test_read_menu_choice_instant_key_fallback_characterization(monkeypatch) -> None:
    monkeypatch.setattr(menu_input.os, "name", "posix", raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "  P  ")
    assert menu_input.read_menu_choice("> ", instant_keys={"p"}) == "P"


def test_bestiary_read_choice_lower_and_hotkeys_characterization(monkeypatch) -> None:
    captured: dict[str, set[str]] = {}

    def fake_read_menu_choice(_prompt: str, *, instant_keys=()) -> str:
        captured["keys"] = set(instant_keys)
        return "G"

    monkeypatch.setattr(bestiary, "read_menu_choice", fake_read_menu_choice)
    choice = bestiary._read_choice("> ", total_pages=2, extra_instant_keys={"g"})
    assert choice == "g"
    assert PAGE_NEXT_KEY in captured["keys"]
    assert PAGE_PREV_KEY in captured["keys"]
    assert "g" in captured["keys"]


def test_show_rods_bestiary_pagination_flow_characterization(monkeypatch) -> None:
    rods = [_make_rod(f"Rod {index:02d}") for index in range(1, 13)]
    unlocked = {rod.name for rod in rods}
    feeder = _ChoiceFeeder([PAGE_NEXT_KEY, "0"])

    monkeypatch.setattr(bestiary, "use_modern_ui", lambda: False)
    monkeypatch.setattr(bestiary, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    monkeypatch.setattr(bestiary, "_read_choice", feeder)

    bestiary.show_rods_bestiary(rods, unlocked)
    assert feeder.calls == feeder.total_expected


def test_show_rods_bestiary_modern_flow_characterization(monkeypatch) -> None:
    rods = [_make_rod(f"Rod {index:02d}") for index in range(1, 4)]
    unlocked = {rod.name for rod in rods}
    feeder = _ChoiceFeeder(["0"])

    monkeypatch.setattr(bestiary, "use_modern_ui", lambda: True)
    monkeypatch.setattr(bestiary, "clear_screen", lambda: None)
    monkeypatch.setattr(bestiary, "print_menu_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    monkeypatch.setattr(bestiary, "_read_choice", feeder)

    bestiary.show_rods_bestiary(rods, unlocked)
    assert feeder.calls == feeder.total_expected


def test_show_fish_bestiary_section_pagination_flow_characterization(monkeypatch) -> None:
    fish = [_DummyFish(f"Fish {index:02d}") for index in range(1, 13)]
    section = bestiary.FishBestiarySection(
        title="Lagoa Tranquila",
        fish_profiles=fish,
        completion_fish_names={item.name for item in fish},
    )
    feeder = _ChoiceFeeder([PAGE_NEXT_KEY, "0"])

    monkeypatch.setattr(bestiary, "use_modern_ui", lambda: False)
    monkeypatch.setattr(bestiary, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    monkeypatch.setattr(bestiary, "_read_choice", feeder)

    bestiary._show_fish_bestiary_section(section, {item.name for item in fish})
    assert feeder.calls == feeder.total_expected


def test_show_pools_bestiary_pagination_flow_characterization(monkeypatch) -> None:
    pools = [
        _DummyPool(
            name=f"Pool {index:02d}",
            fish_profiles=[_DummyFish(f"Fish {index:02d}")],
            folder=Path(f"pool_{index:02d}"),
        )
        for index in range(1, 13)
    ]
    unlocked = {pool.name for pool in pools}
    feeder = _ChoiceFeeder([PAGE_NEXT_KEY, "0"])

    monkeypatch.setattr(bestiary, "use_modern_ui", lambda: False)
    monkeypatch.setattr(bestiary, "clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    monkeypatch.setattr(bestiary, "_read_choice", feeder)

    bestiary.show_pools_bestiary(pools, unlocked)
    assert feeder.calls == feeder.total_expected


def test_new_pool_rewards_require_exact_pool_name_matching() -> None:
    rewards_dir = Path(__file__).resolve().parent.parent / "bestiary_rewards"
    rewards = load_bestiary_rewards(rewards_dir)
    rewards_by_id = {reward.reward_id: reward for reward in rewards}

    baia_reward = rewards_by_id["pool_baiadosol_100"]
    snowcap_reward = rewards_by_id["pool_snowcap_100"]
    assert baia_reward.target_pool == "Baia do Sol"
    assert snowcap_reward.target_pool == "Geleira Snowcap"

    reward_state = BestiaryRewardState()
    claimable_exact = get_claimable_bestiary_rewards(
        [baia_reward, snowcap_reward],
        reward_state,
        category="fish",
        fish_global_percent=0.0,
        fish_percent_by_pool={
            "Baia do Sol": 100.0,
            "Geleira Snowcap": 100.0,
        },
        rods_percent=0.0,
        pools_percent=0.0,
    )
    assert {reward.reward_id for reward in claimable_exact} == {
        "pool_baiadosol_100",
        "pool_snowcap_100",
    }

    claimable_mismatch = get_claimable_bestiary_rewards(
        [baia_reward, snowcap_reward],
        reward_state,
        category="fish",
        fish_global_percent=0.0,
        fish_percent_by_pool={
            "Baía do Sol": 100.0,
            "Snowcap": 100.0,
        },
        rods_percent=0.0,
        pools_percent=0.0,
    )
    assert claimable_mismatch == []


def test_bestiary_reward_preview_line_includes_itemized_summary() -> None:
    reward = BestiaryRewardDefinition(
        reward_id="pool_baiadosol_100",
        name="Brilho da Baia do Sol",
        trigger_type="fish_bestiary",
        threshold_percent=100.0,
        target_pool="Baia do Sol",
        rewards=[
            {"type": "ui_color", "color_id": "solar_gold"},
            {"type": "ui_icon", "icon_id": "pool_baiadosol"},
            {"type": "money", "amount": 2300},
            {"type": "xp", "amount": 580},
            {"type": "bait", "bait_id": "cheap_bait_crate/coral", "amount": 10},
        ],
    )

    preview_lines = bestiary._build_claim_preview_lines([reward])
    assert len(preview_lines) == 1
    preview_line = preview_lines[0]
    assert "Brilho da Baia do Sol" in preview_line
    assert "Cor: Ouro Solar" in preview_line
    assert "Icone: Baia do Sol" in preview_line
    assert "R$ 2300.00" in preview_line
    assert "580 XP" in preview_line
    assert "10x cheap_bait_crate/coral" in preview_line


def test_claim_output_is_itemized_in_show_bestiary(monkeypatch) -> None:
    rods = [_make_rod("Vara Bambu")]
    pools = [
        _DummyPool(
            name="Lagoa Tranquila",
            fish_profiles=[_DummyFish("Tilapia")],
            folder=Path("lagoa"),
        )
    ]
    reward = BestiaryRewardDefinition(
        reward_id="rods_100_test",
        name="Colecionador de Varas",
        trigger_type="rods_bestiary",
        threshold_percent=100.0,
        target_pool="All",
        rewards=[{"type": "xp", "amount": 50}],
    )
    reward_state = BestiaryRewardState()

    menu_inputs = iter(["2", "", "0"])
    rod_choices = iter(["g", "0"])
    captured_notes: list[str] = []

    monkeypatch.setattr(bestiary, "clear_screen", lambda: None)
    monkeypatch.setattr(bestiary, "use_modern_ui", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(menu_inputs))
    monkeypatch.setattr(
        bestiary,
        "_read_choice",
        lambda _prompt, _total_pages, extra_instant_keys=None: next(rod_choices),
    )
    monkeypatch.setattr(
        bestiary,
        "_print_claim_notes",
        lambda notes: captured_notes.extend(notes),
    )

    bestiary.show_bestiary(
        pools=pools,
        available_rods=rods,
        owned_rods=rods,
        unlocked_pools={pool.name for pool in pools},
        discovered_fish={"Tilapia"},
        bestiary_rewards=[reward],
        bestiary_reward_state=reward_state,
        on_claim_bestiary_reward=lambda _reward: ["✨ +50 XP"],
    )

    assert captured_notes == [
        "Resgatado: Colecionador de Varas",
        "  - ✨ +50 XP",
    ]
