from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.weather import WeatherConfig, WeatherDefinition, WeatherManager, load_weather
from utils.manager_lifecycle import ManagerLifecycle


def _weather(
    weather_id: str = "clear",
    *,
    name: str = "Limpo",
    icon: str = "☀️",
    xp_multiplier: float = 1.0,
    luck_bonus: float = 0.0,
    control_bonus: float = 0.0,
) -> WeatherDefinition:
    return WeatherDefinition(
        id=weather_id,
        name=name,
        description="Descricao",
        icon=icon,
        xp_multiplier=xp_multiplier,
        luck_bonus=luck_bonus,
        control_bonus=control_bonus,
    )


# ── Loader tests ────────────────────────────────────────────────────────


def test_load_weather_from_disk(tmp_path: Path) -> None:
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()

    (weather_dir / "clear.json").write_text(
        json.dumps({"name": "Limpo", "icon": "☀️", "xp_multiplier": 1.0}),
        encoding="utf-8",
    )
    (weather_dir / "rainy.json").write_text(
        json.dumps({"name": "Chuvoso", "icon": "🌧️", "xp_multiplier": 1.1, "luck_bonus": 0.0}),
        encoding="utf-8",
    )
    (weather_dir / "config.json").write_text(
        json.dumps({
            "rotation_interval_minutes": 10,
            "change_chance_percent": 50,
            "default_weather": "clear",
        }),
        encoding="utf-8",
    )

    weathers, config = load_weather(tmp_path)

    assert len(weathers) == 2
    names = {w.id for w in weathers}
    assert "clear" in names
    assert "rainy" in names
    assert config.rotation_interval_s == 600.0
    assert config.change_chance == 0.5
    assert config.default_weather_id == "clear"


def test_load_weather_missing_directory(tmp_path: Path) -> None:
    weathers, config = load_weather(tmp_path)
    assert weathers == []
    assert config == WeatherConfig()


def test_load_weather_malformed_json_skipped(tmp_path: Path) -> None:
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "bad.json").write_text("{invalid json", encoding="utf-8")
    (weather_dir / "good.json").write_text(
        json.dumps({"name": "Bom", "icon": "☀️"}),
        encoding="utf-8",
    )

    weathers, config = load_weather(tmp_path)
    assert len(weathers) == 1
    assert weathers[0].id == "good"


def test_load_weather_malformed_payload_skipped(tmp_path: Path) -> None:
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "list.json").write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    (weather_dir / "bad_value.json").write_text(
        json.dumps({"name": "Ruim", "xp_multiplier": "fast"}),
        encoding="utf-8",
    )
    (weather_dir / "good.json").write_text(
        json.dumps({"name": "Bom", "icon": "☀️", "xp_multiplier": 1.15}),
        encoding="utf-8",
    )

    weathers, _ = load_weather(tmp_path)

    assert len(weathers) == 1
    assert weathers[0].id == "good"
    assert weathers[0].xp_multiplier == 1.15


def test_load_weather_defaults_for_missing_fields(tmp_path: Path) -> None:
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "minimal.json").write_text(
        json.dumps({"name": "Minimal"}),
        encoding="utf-8",
    )

    weathers, _ = load_weather(tmp_path)
    assert len(weathers) == 1
    w = weathers[0]
    assert w.xp_multiplier == 1.0
    assert w.luck_bonus == 0.0
    assert w.control_bonus == 0.0
    assert w.icon == ""


def test_load_weather_config_defaults_when_missing(tmp_path: Path) -> None:
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "clear.json").write_text(
        json.dumps({"name": "Limpo"}),
        encoding="utf-8",
    )

    _, config = load_weather(tmp_path)
    assert config.rotation_interval_s == 300.0
    assert config.change_chance == 0.4
    assert config.default_weather_id == "clear"


def test_load_weather_config_defaults_when_malformed_payload(tmp_path: Path) -> None:
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "clear.json").write_text(
        json.dumps({"name": "Limpo"}),
        encoding="utf-8",
    )
    (weather_dir / "config.json").write_text(
        json.dumps({"rotation_interval_minutes": "fast"}),
        encoding="utf-8",
    )

    _, config = load_weather(tmp_path)

    assert config == WeatherConfig()


# ── Manager tests ───────────────────────────────────────────────────────


def test_weather_manager_initial_active_weather() -> None:
    clear = _weather("clear")
    rainy = _weather("rainy", name="Chuvoso", icon="🌧️")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, rainy], config)
    active = manager.get_active_weather()
    assert active is not None
    assert active.id == "clear"


def test_weather_manager_fallback_to_first_weather() -> None:
    rainy = _weather("rainy", name="Chuvoso")
    config = WeatherConfig(default_weather_id="nonexistent")

    manager = WeatherManager([rainy], config)
    active = manager.get_active_weather()
    assert active is not None
    assert active.id == "rainy"


def test_weather_manager_force_weather_dev_mode() -> None:
    clear = _weather("clear")
    rainy = _weather("rainy", name="Chuvoso")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, rainy], config, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    result = manager.force_weather("rainy")
    assert result is not None
    assert result.id == "rainy"
    assert manager.get_active_weather().id == "rainy"

    notifications = manager.pop_notifications()
    assert len(notifications) == 1
    assert "Chuvoso" in notifications[0]


def test_weather_manager_force_weather_disabled_without_dev_mode() -> None:
    clear = _weather("clear")
    rainy = _weather("rainy", name="Chuvoso")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, rainy], config, dev_tools_enabled=False)
    result = manager.force_weather("rainy")
    assert result is None
    assert manager.get_active_weather().id == "clear"


def test_weather_manager_force_nonexistent_weather() -> None:
    clear = _weather("clear")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear], config, dev_tools_enabled=True)
    result = manager.force_weather("nonexistent")
    assert result is None


def test_weather_manager_list_weathers() -> None:
    clear = _weather("clear")
    rainy = _weather("rainy", name="Chuvoso")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, rainy], config)
    listed = manager.list_weathers()
    assert len(listed) == 2
    assert {w.id for w in listed} == {"clear", "rainy"}


def test_weather_manager_rotation(monkeypatch) -> None:
    """Test that _rotate picks a different weather from the current one."""
    clear = _weather("clear")
    rainy = _weather("rainy", name="Chuvoso")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, rainy], config, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    # Force rotation by calling _rotate directly
    monkeypatch.setattr("utils.weather.random.choice", lambda candidates: rainy)
    manager._rotate()

    active = manager.get_active_weather()
    assert active.id == "rainy"

    notifications = manager.pop_notifications()
    assert len(notifications) == 1
    assert "Chuvoso" in notifications[0]


def test_weather_manager_no_weathers() -> None:
    config = WeatherConfig(default_weather_id="clear")
    manager = WeatherManager([], config)
    assert manager.get_active_weather() is None


# ── Modifier value tests ────────────────────────────────────────────────


def test_weather_xp_multiplier_applied() -> None:
    w = _weather("rainy", xp_multiplier=1.1)
    base_xp = 100
    result = int(round(base_xp * w.xp_multiplier))
    assert result == 110


def test_weather_luck_bonus_additive() -> None:
    w = _weather("foggy", luck_bonus=0.02)
    base_luck = 0.5
    result = base_luck + w.luck_bonus
    assert abs(result - 0.52) < 1e-9


def test_weather_control_bonus_additive() -> None:
    w = _weather("windy", control_bonus=0.1)
    base_control = 1.0
    result = base_control + w.control_bonus
    assert abs(result - 1.1) < 1e-9


def test_weather_notification_includes_modifiers() -> None:
    rainy = _weather("rainy", name="Chuvoso", icon="🌧️", xp_multiplier=1.1)
    clear = _weather("clear")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, rainy], config, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    import utils.weather as weather_mod
    original_choice = weather_mod.random.choice
    weather_mod.random.choice = lambda candidates: rainy
    try:
        manager._rotate()
    finally:
        weather_mod.random.choice = original_choice

    notifications = manager.pop_notifications()
    assert len(notifications) == 1
    assert "+10% XP" in notifications[0]


def test_weather_notification_formats_negative_modifiers() -> None:
    harsh = _weather(
        "harsh",
        name="Hostil",
        icon="🌫️",
        luck_bonus=-0.10,
        control_bonus=-0.5,
    )
    clear = _weather("clear")
    config = WeatherConfig(default_weather_id="clear")

    manager = WeatherManager([clear, harsh], config, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    import utils.weather as weather_mod
    original_choice = weather_mod.random.choice
    weather_mod.random.choice = lambda candidates: harsh
    try:
        manager._rotate()
    finally:
        weather_mod.random.choice = original_choice

    notifications = manager.pop_notifications()
    assert len(notifications) == 1
    assert "-0.10 luck" in notifications[0]
    assert "-0.5 control" in notifications[0]
