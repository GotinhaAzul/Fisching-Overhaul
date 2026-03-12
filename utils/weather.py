"""utils/weather.py — Weather rotation system."""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from utils.manager_lifecycle import ManagerLifecycle

logger = logging.getLogger(__name__)

# ── Data ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WeatherDefinition:
    id: str
    name: str
    description: str
    icon: str
    xp_multiplier: float = 1.0
    luck_bonus: float = 0.0
    control_bonus: float = 0.0


@dataclass(frozen=True)
class WeatherConfig:
    rotation_interval_s: float = 300.0
    change_chance: float = 0.4
    default_weather_id: str = "clear"


# ── Loader ──────────────────────────────────────────────────────────────


def _coerce_mapping(data: object, *, source_name: str) -> dict[str, object]:
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object in {source_name}")
    return data


def _signed_decimal(value: float, precision: int) -> str:
    return f"{value:+.{precision}f}"


def load_weather(base_dir: Path) -> tuple[list[WeatherDefinition], WeatherConfig]:
    weather_dir = base_dir / "weather"
    weathers: list[WeatherDefinition] = []

    if not weather_dir.is_dir():
        logger.warning("weather: directory %s not found, using empty list", weather_dir)
        return weathers, WeatherConfig()

    for path in sorted(weather_dir.glob("*.json")):
        if path.name == "config.json":
            continue
        try:
            data = _coerce_mapping(
                json.loads(path.read_text(encoding="utf-8")),
                source_name=path.name,
            )
            weather = WeatherDefinition(
                id=path.stem,
                name=str(data.get("name", path.stem)),
                description=str(data.get("description", "")),
                icon=str(data.get("icon", "")),
                xp_multiplier=float(data.get("xp_multiplier", 1.0)),
                luck_bonus=float(data.get("luck_bonus", 0.0)),
                control_bonus=float(data.get("control_bonus", 0.0)),
            )
        except (TypeError, ValueError, json.JSONDecodeError, OSError) as exc:
            logger.warning("weather: skipping %s: %s", path.name, exc)
            continue

        weathers.append(weather)

    # Load config
    config_path = weather_dir / "config.json"
    config = WeatherConfig()
    if config_path.is_file():
        try:
            cfg = _coerce_mapping(
                json.loads(config_path.read_text(encoding="utf-8")),
                source_name=config_path.name,
            )
            config = WeatherConfig(
                rotation_interval_s=float(cfg.get("rotation_interval_minutes", 5)) * 60,
                change_chance=float(cfg.get("change_chance_percent", 40)) / 100,
                default_weather_id=str(cfg.get("default_weather", "clear")),
            )
        except (TypeError, ValueError, json.JSONDecodeError, OSError) as exc:
            logger.warning("weather: config.json malformed, using defaults: %s", exc)

    return weathers, config


# ── Manager ─────────────────────────────────────────────────────────────


class WeatherManager:
    def __init__(
        self,
        weathers: list[WeatherDefinition],
        config: WeatherConfig,
        dev_tools_enabled: bool = False,
    ) -> None:
        self._weathers: Dict[str, WeatherDefinition] = {w.id: w for w in weathers}
        self._config = config
        self._dev_tools_enabled = bool(dev_tools_enabled)
        self._lifecycle = ManagerLifecycle()
        self._lock = self._lifecycle.lock

        default = self._weathers.get(config.default_weather_id)
        if default is None and weathers:
            default = weathers[0]
        self._active: Optional[WeatherDefinition] = default
        self._last_rotation = time.monotonic()

    def start(self) -> None:
        self._lifecycle.start(self._run_loop, enabled=bool(self._weathers))

    def stop(self) -> None:
        self._lifecycle.stop()

    def suppress_notifications(self, value: bool) -> None:
        self._lifecycle.suppress_notifications(value)

    def pop_notifications(self) -> List[str]:
        return self._lifecycle.pop_notifications()

    def get_active_weather(self) -> Optional[WeatherDefinition]:
        with self._lock:
            return self._active

    def list_weathers(self) -> List[WeatherDefinition]:
        with self._lock:
            return list(self._weathers.values())

    def force_weather(self, weather_id: str) -> Optional[WeatherDefinition]:
        if not self._dev_tools_enabled:
            return None
        with self._lock:
            w = self._weathers.get(weather_id)
            if w is None:
                return None
            self._active = w
            self._last_rotation = time.monotonic()
        self._lifecycle.emit_notification(f"Clima forçado: {w.icon} {w.name}")
        return w

    def _run_loop(self) -> None:
        while not self._lifecycle.stop_event.is_set():
            now = time.monotonic()
            if now - self._last_rotation >= self._config.rotation_interval_s:
                self._last_rotation = now
                if random.random() <= self._config.change_chance:
                    self._rotate()
            time.sleep(1)

    def _rotate(self) -> None:
        with self._lock:
            candidates = [
                w for w in self._weathers.values()
                if w.id != (self._active.id if self._active else "")
            ]
            if not candidates:
                return
            new_weather = random.choice(candidates)
            self._active = new_weather

        # Build modifier summary for notification
        parts: list[str] = []
        if new_weather.xp_multiplier != 1.0:
            pct = int(round((new_weather.xp_multiplier - 1.0) * 100))
            sign = "+" if pct >= 0 else ""
            parts.append(f"{sign}{pct}% XP")
        if new_weather.luck_bonus != 0.0:
            parts.append(f"{_signed_decimal(new_weather.luck_bonus, 2)} luck")
        if new_weather.control_bonus != 0.0:
            parts.append(f"{_signed_decimal(new_weather.control_bonus, 1)} control")
        suffix = f" ({', '.join(parts)})" if parts else ""

        self._lifecycle.emit_notification(
            f"O clima mudou para {new_weather.icon} {new_weather.name}{suffix}"
        )
