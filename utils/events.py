from __future__ import annotations

import random
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.mutations import Mutation
    from utils.pesca import FishProfile


@dataclass(frozen=True)
class EventDefinition:
    name: str
    description: str
    chance: float
    interval_s: float
    duration_s: float
    luck_multiplier: float
    xp_multiplier: float
    fish_profiles: List["FishProfile"]
    rarity_weights: Dict[str, float]
    mutations: List["Mutation"]


@dataclass
class ActiveEvent:
    definition: EventDefinition
    started_at: float
    ends_at: float

    def time_left(self) -> float:
        return max(0.0, self.ends_at - time.monotonic())


class EventManager:
    def __init__(self, events: List[EventDefinition], dev_tools_enabled: bool = False):
        self._events = list(events)
        self._dev_tools_enabled = bool(dev_tools_enabled)
        self._lock = threading.Lock()
        self._active: Optional[ActiveEvent] = None
        self._last_checks = {event.name: time.monotonic() for event in self._events}
        self._pending_notifications: List[str] = []
        self._suppress_notifications = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self._events or self._thread:
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._thread = None

    def suppress_notifications(self, value: bool) -> None:
        with self._lock:
            self._suppress_notifications = value

    def pop_notifications(self) -> List[str]:
        with self._lock:
            notifications = self._pending_notifications[:]
            self._pending_notifications.clear()
        return notifications

    def get_active_event(self) -> Optional[ActiveEvent]:
        with self._lock:
            return self._active

    def list_events(self) -> List[EventDefinition]:
        with self._lock:
            return list(self._events)

    def force_event(self, event_name: str) -> Optional[EventDefinition]:
        if not self._dev_tools_enabled:
            return None

        target_name = event_name.casefold()
        selected: Optional[EventDefinition] = None
        now = time.monotonic()
        previous: Optional[ActiveEvent] = None

        with self._lock:
            for event in self._events:
                if event.name.casefold() == target_name:
                    selected = event
                    break
            if not selected:
                return None
            previous = self._active
            self._active = ActiveEvent(
                definition=selected,
                started_at=now,
                ends_at=now + selected.duration_s,
            )
            self._last_checks[selected.name] = now

        if previous and previous.definition.name != selected.name:
            self._emit_notification(
                f"O evento '{previous.definition.name}' foi encerrado (forcado)."
            )
        self._emit_notification(
            f"Evento iniciado: {selected.name}! {selected.description}"
        )
        return selected

    def _emit_notification(self, message: str) -> None:
        with self._lock:
            if self._suppress_notifications:
                self._pending_notifications.append(message)
                return
        print(f"\n🔔 {message}")
        sys.stdout.flush()

    def _activate_event(self, event: EventDefinition, now: float) -> None:
        active = ActiveEvent(
            definition=event,
            started_at=now,
            ends_at=now + event.duration_s,
        )
        with self._lock:
            self._active = active
        self._emit_notification(
            f"Evento iniciado: {event.name}! {event.description}"
        )

    def _end_active_event(self) -> None:
        with self._lock:
            active = self._active
            self._active = None
        if active:
            self._emit_notification(f"O evento '{active.definition.name}' terminou.")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()

            active = self.get_active_event()
            if active and now >= active.ends_at:
                self._end_active_event()

            if not self.get_active_event():
                for event in self._events:
                    last_check = self._last_checks.get(event.name, now)
                    if now - last_check < event.interval_s:
                        continue

                    self._last_checks[event.name] = now
                    if random.random() <= event.chance:
                        self._activate_event(event, now)
                        break

            time.sleep(1)
