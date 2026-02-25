from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import utils.bestiary as bestiary
import utils.menu_input as menu_input
from utils.pagination import PAGE_NEXT_KEY, PAGE_PREV_KEY
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
