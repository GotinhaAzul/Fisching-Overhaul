from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_DEFAULT_CONFIG: dict[str, Any] = {
    "catch_chance_percent": 1.0,
    "appraise_chance_percent": 1.0,
    "value_multiplier": 1.55,
    "display": {
        "label": "✦ Shiny",
        "color": "#FFD700",
        "catch_message": "✦ Um peixe SHINY apareceu!",
    },
}


@dataclass(frozen=True)
class ShinyDisplayConfig:
    label: str
    color: str
    catch_message: str


@dataclass(frozen=True)
class ShinyConfig:
    catch_chance_percent: float
    appraise_chance_percent: float
    value_multiplier: float
    display: ShinyDisplayConfig


def default_shiny_config() -> ShinyConfig:
    return _build_shiny_config(_DEFAULT_CONFIG)


def load_shiny_config(base_dir: Path) -> ShinyConfig:
    config_path = base_dir / "config" / "shiny.json"
    raw_config: Mapping[str, Any] = _DEFAULT_CONFIG
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, dict):
            raw_config = loaded
    return _build_shiny_config(raw_config)


def roll_shiny_on_catch(config: ShinyConfig) -> bool:
    return _roll_percent(config.catch_chance_percent)


def roll_shiny_on_appraise(config: ShinyConfig) -> bool:
    return _roll_percent(config.appraise_chance_percent)


def _build_shiny_config(raw_config: Mapping[str, Any]) -> ShinyConfig:
    raw_display = raw_config.get("display")
    if not isinstance(raw_display, dict):
        raw_display = _DEFAULT_CONFIG["display"]
    default_display = _DEFAULT_CONFIG["display"]
    return ShinyConfig(
        catch_chance_percent=_safe_float(
            raw_config.get("catch_chance_percent"),
            fallback=float(_DEFAULT_CONFIG["catch_chance_percent"]),
        ),
        appraise_chance_percent=_safe_float(
            raw_config.get("appraise_chance_percent"),
            fallback=float(_DEFAULT_CONFIG["appraise_chance_percent"]),
        ),
        value_multiplier=_safe_float(
            raw_config.get("value_multiplier"),
            fallback=float(_DEFAULT_CONFIG["value_multiplier"]),
        ),
        display=ShinyDisplayConfig(
            label=_safe_str(raw_display.get("label"), fallback=str(default_display["label"])),
            color=_safe_str(raw_display.get("color"), fallback=str(default_display["color"])),
            catch_message=_safe_str(
                raw_display.get("catch_message"),
                fallback=str(default_display["catch_message"]),
            ),
        ),
    )


def _roll_percent(chance_percent: float) -> bool:
    normalized_chance = min(100.0, max(0.0, chance_percent))
    return random.random() * 100.0 < normalized_chance


def _safe_float(value: object, *, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _safe_str(value: object, *, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback
