from __future__ import annotations

from dataclasses import dataclass

from utils.modern_ui import render_fishing_hud_line
from utils.perfect_catch import (
    PerfectCatchConfig,
    is_perfect_catch,
    parse_perfect_catch_config,
    resolve_hud_color,
)


@dataclass
class _AttemptStub:
    sequence: list[str]
    time_limit_s: float


def test_parse_perfect_catch_defaults_characterization() -> None:
    parsed = parse_perfect_catch_config(None, source_label="pool.json")
    assert parsed == PerfectCatchConfig(enabled=True, threshold_ratio=0.80, xp_multiplier=1.50)


def test_parse_perfect_catch_missing_override_returns_none_characterization() -> None:
    parsed = parse_perfect_catch_config(
        None,
        source_label="fish.json",
        allow_missing=True,
    )
    assert parsed is None


def test_parse_perfect_catch_partial_override_inherits_fallback_characterization() -> None:
    pool_cfg = PerfectCatchConfig(enabled=False, threshold_ratio=0.82, xp_multiplier=2.2)
    parsed = parse_perfect_catch_config(
        {"xp_multiplier": 3.0},
        source_label="fish.json",
        fallback=pool_cfg,
        allow_missing=True,
    )
    assert parsed == PerfectCatchConfig(enabled=False, threshold_ratio=0.82, xp_multiplier=3.0)


def test_parse_perfect_catch_invalid_values_are_clamped_with_warning_characterization(
    capsys,
) -> None:
    parsed = parse_perfect_catch_config(
        {
            "enabled": "maybe",
            "threshold_ratio": 5,
            "xp_multiplier": 0.2,
        },
        source_label="pool.json",
    )
    captured = capsys.readouterr().out
    assert "perfect_catch.enabled invalido" in captured
    assert "perfect_catch.threshold_ratio fora do intervalo" in captured
    assert "perfect_catch.xp_multiplier fora do intervalo" in captured
    assert parsed == PerfectCatchConfig(enabled=True, threshold_ratio=1.0, xp_multiplier=1.0)


def test_is_perfect_catch_characterization() -> None:
    cfg = PerfectCatchConfig(enabled=True, threshold_ratio=0.70, xp_multiplier=1.5)
    assert is_perfect_catch(6.9, 10.0, cfg) is True
    assert is_perfect_catch(7.1, 10.0, cfg) is False
    assert is_perfect_catch(0.0, 0.0, cfg) is False


def test_resolve_hud_color_characterization() -> None:
    assert resolve_hud_color(0.10, 0.70) == "bright_cyan"
    assert resolve_hud_color(0.50, 0.70) == "green"
    assert resolve_hud_color(0.80, 0.70) == "yellow"
    assert resolve_hud_color(0.95, 0.70) == "red"


def test_render_fishing_hud_line_perfect_marker_characterization() -> None:
    attempt = _AttemptStub(sequence=["w", "a", "s"], time_limit_s=10.0)
    hud_on = render_fishing_hud_line(
        attempt,
        typed=[],
        time_left=8.0,
        total_time_s=10.0,
        perfect_threshold_ratio=0.70,
        perfect_catch_enabled=True,
    )
    hud_off = render_fishing_hud_line(
        attempt,
        typed=["w", "a"],
        time_left=1.0,
        total_time_s=10.0,
        perfect_threshold_ratio=0.70,
        perfect_catch_enabled=True,
    )

    assert "Perfect: ON" in hud_on
    assert "Perfect: OFF" in hud_off
