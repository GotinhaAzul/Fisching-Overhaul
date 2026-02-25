from __future__ import annotations

from typing import Any

from utils.events import EventDefinition, EventManager
from utils.hunts import HuntDefinition, HuntManager


def _event(
    name: str,
    *,
    description: str = "Descricao",
    duration_s: float = 30.0,
) -> EventDefinition:
    return EventDefinition(
        name=name,
        description=description,
        chance=0.0,
        interval_s=30.0,
        duration_s=duration_s,
        luck_multiplier=1.0,
        xp_multiplier=1.0,
        fish_profiles=[],
        rarity_weights={},
        mutations=[],
    )


def _hunt(
    hunt_id: str,
    *,
    name: str = "Hunt",
    pool_name: str = "Rio",
    duration_s: float = 40.0,
) -> HuntDefinition:
    return HuntDefinition(
        hunt_id=hunt_id,
        name=name,
        description="Descricao",
        pool_name=pool_name,
        duration_s=duration_s,
        check_interval_s=30.0,
        disturbance_per_catch=2.0,
        disturbance_max=10.0,
        rarity_weights={},
        fish_profiles=[],
        cooldown_s=20.0,
        disturbance_decay_per_check=0.0,
    )


def test_event_manager_force_event_notification_queue_characterization(monkeypatch) -> None:
    now = {"value": 100.0}
    monkeypatch.setattr("utils.events.time.monotonic", lambda: now["value"])

    manager = EventManager([_event("Tempestade", description="Ventos fortes")], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    selected = manager.force_event("tempestade")
    assert selected is not None
    assert selected.name == "Tempestade"

    active = manager.get_active_event()
    assert active is not None
    assert active.definition.name == "Tempestade"
    assert active.started_at == 100.0
    assert active.ends_at == 130.0
    assert manager.pop_notifications() == [
        "Evento iniciado: Tempestade! Ventos fortes"
    ]


def test_event_manager_force_event_replacement_notifications_characterization(monkeypatch) -> None:
    monkeypatch.setattr("utils.events.time.monotonic", lambda: 250.0)

    manager = EventManager([_event("Nublado"), _event("Tempestade")], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.force_event("nublado")
    assert manager.pop_notifications() == ["Evento iniciado: Nublado! Descricao"]

    manager.force_event("tempestade")
    assert manager.pop_notifications() == [
        "O evento 'Nublado' foi encerrado (forcado).",
        "Evento iniciado: Tempestade! Descricao",
    ]


def test_event_manager_force_event_disabled_characterization() -> None:
    manager = EventManager([_event("Tempestade")], dev_tools_enabled=False)
    assert manager.force_event("tempestade") is None
    assert manager.get_active_event() is None
    assert manager.pop_notifications() == []


def test_hunt_manager_force_hunt_notification_queue_characterization(monkeypatch) -> None:
    now = {"value": 80.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunt = _hunt("h1", name="Caos")
    manager = HuntManager([hunt], dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.record_catch("Rio")
    before_state = manager.serialize_state()
    before_disturbance = before_state["hunts"]["h1"]["disturbance"]
    assert isinstance(before_disturbance, float)
    assert before_disturbance > 0.0

    selected = manager.force_hunt("h1")
    assert selected is not None
    assert selected.hunt_id == "h1"

    active = manager.get_active_hunt_for_pool("Rio")
    assert active is not None
    assert active.definition.hunt_id == "h1"
    assert active.started_at == 80.0
    assert active.ends_at == 120.0
    assert manager.pop_notifications() == ["Hunt iniciada em Rio: Caos"]

    after_state = manager.serialize_state()
    assert after_state["hunts"]["h1"]["disturbance"] == 0.0


def test_hunt_manager_serialize_restore_roundtrip_characterization(monkeypatch) -> None:
    now = {"value": 500.0}
    monkeypatch.setattr("utils.hunts.time.monotonic", lambda: now["value"])

    hunts = [_hunt("h1", name="Caos"), _hunt("h2", name="Marola", pool_name="Lagoa")]
    manager = HuntManager(hunts, dev_tools_enabled=True)
    manager.suppress_notifications(True)

    manager.record_catch("Rio")
    manager.force_hunt("h1")
    raw_state = manager.serialize_state()

    restored = HuntManager(hunts, dev_tools_enabled=True)
    restored.restore_state(raw_state)
    restored_state = restored.serialize_state()

    assert set(restored_state["hunts"].keys()) == {"h1", "h2"}
    assert restored_state["hunts"]["h1"]["disturbance"] == 0.0
    assert restored_state["hunts"]["h2"]["disturbance"] == 0.0

    active_by_pool: Any = restored_state["active_by_pool"]
    assert isinstance(active_by_pool, dict)
    assert "Rio" in active_by_pool
    assert active_by_pool["Rio"]["hunt_id"] == "h1"
    assert active_by_pool["Rio"]["remaining_s"] > 0.0
