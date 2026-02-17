from __future__ import annotations

import random
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.pesca import FishProfile


@dataclass(frozen=True)
class HuntDefinition:
    hunt_id: str
    name: str
    description: str
    pool_name: str
    duration_s: float
    check_interval_s: float
    disturbance_per_catch: float
    disturbance_max: float
    rarity_weights: Dict[str, float]
    fish_profiles: List["FishProfile"]
    cooldown_s: float = 0.0
    disturbance_decay_per_check: float = 0.0


@dataclass
class ActiveHunt:
    definition: HuntDefinition
    started_at: float
    ends_at: float

    def time_left(self) -> float:
        return max(0.0, self.ends_at - time.monotonic())


@dataclass
class HuntProgressState:
    disturbance: float = 0.0
    last_check: float = 0.0
    cooldown_ends_at: float = 0.0


class HuntManager:
    def __init__(self, hunts: List[HuntDefinition], dev_tools_enabled: bool = False):
        self._hunts = list(hunts)
        self._dev_tools_enabled = bool(dev_tools_enabled)
        self._hunts_by_id = {hunt.hunt_id: hunt for hunt in self._hunts}
        self._hunts_by_pool: Dict[str, List[HuntDefinition]] = {}
        for hunt in self._hunts:
            self._hunts_by_pool.setdefault(hunt.pool_name, []).append(hunt)

        now = time.monotonic()
        self._progress_by_hunt: Dict[str, HuntProgressState] = {
            hunt.hunt_id: HuntProgressState(
                disturbance=0.0,
                last_check=now,
                cooldown_ends_at=0.0,
            )
            for hunt in self._hunts
        }
        self._active_by_pool: Dict[str, ActiveHunt] = {}

        self._lock = threading.Lock()
        self._pending_notifications: List[str] = []
        self._suppress_notifications = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self._hunts or self._thread:
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

    def get_active_hunt_for_pool(self, pool_name: str) -> Optional[ActiveHunt]:
        with self._lock:
            return self._active_by_pool.get(pool_name)

    def list_hunts(self) -> List[HuntDefinition]:
        with self._lock:
            return list(self._hunts)

    def force_hunt(self, hunt_id: str) -> Optional[HuntDefinition]:
        if not self._dev_tools_enabled:
            return None

        target_id = hunt_id.casefold()
        selected: Optional[HuntDefinition] = None
        now = time.monotonic()
        replaced: Optional[ActiveHunt] = None

        with self._lock:
            for hunt in self._hunts:
                if hunt.hunt_id.casefold() == target_id:
                    selected = hunt
                    break
            if not selected:
                return None

            replaced = self._active_by_pool.get(selected.pool_name)
            self._active_by_pool[selected.pool_name] = ActiveHunt(
                definition=selected,
                started_at=now,
                ends_at=now + selected.duration_s,
            )
            progress = self._progress_by_hunt.get(selected.hunt_id)
            if progress:
                progress.disturbance = 0.0

        if replaced and replaced.definition.hunt_id != selected.hunt_id:
            self._emit_notification(
                f"A hunt '{replaced.definition.name}' foi encerrada (forcada)."
            )
        self._emit_notification(
            f"Hunt iniciada em {selected.pool_name}: {selected.name}"
        )
        return selected

    def record_catch(self, pool_name: str) -> None:
        definitions = self._hunts_by_pool.get(pool_name, [])
        if not definitions:
            return

        with self._lock:
            for definition in definitions:
                progress = self._progress_by_hunt.get(definition.hunt_id)
                if not progress:
                    continue
                updated = progress.disturbance + max(0.0, definition.disturbance_per_catch)
                progress.disturbance = self._clamp_disturbance(definition, updated)

    def serialize_state(self) -> Dict[str, object]:
        now = time.monotonic()
        with self._lock:
            hunts_data: Dict[str, Dict[str, float]] = {}
            for definition in self._hunts:
                progress = self._progress_by_hunt.get(definition.hunt_id)
                if not progress:
                    continue
                next_check_in = 0.0
                if definition.check_interval_s > 0:
                    elapsed = now - progress.last_check
                    next_check_in = max(0.0, definition.check_interval_s - elapsed)
                hunts_data[definition.hunt_id] = {
                    "disturbance": self._clamp_disturbance(definition, progress.disturbance),
                    "cooldown_remaining_s": max(0.0, progress.cooldown_ends_at - now),
                    "next_check_in_s": next_check_in,
                }

            active_data: Dict[str, Dict[str, object]] = {}
            for pool_name, active in self._active_by_pool.items():
                remaining_s = max(0.0, active.ends_at - now)
                if remaining_s <= 0:
                    continue
                active_data[pool_name] = {
                    "hunt_id": active.definition.hunt_id,
                    "remaining_s": remaining_s,
                }

        return {
            "hunts": hunts_data,
            "active_by_pool": active_data,
        }

    def restore_state(self, raw_state: object) -> None:
        now = time.monotonic()

        with self._lock:
            self._active_by_pool.clear()
            self._progress_by_hunt = {
                hunt.hunt_id: HuntProgressState(
                    disturbance=0.0,
                    last_check=now,
                    cooldown_ends_at=0.0,
                )
                for hunt in self._hunts
            }

            if not isinstance(raw_state, dict):
                return

            raw_hunts = raw_state.get("hunts")
            if isinstance(raw_hunts, dict):
                for hunt_id, raw_progress in raw_hunts.items():
                    if not isinstance(hunt_id, str) or not isinstance(raw_progress, dict):
                        continue
                    definition = self._hunts_by_id.get(hunt_id)
                    progress = self._progress_by_hunt.get(hunt_id)
                    if not definition or not progress:
                        continue

                    disturbance = self._safe_float(raw_progress.get("disturbance"))
                    cooldown_remaining = max(0.0, self._safe_float(raw_progress.get("cooldown_remaining_s")))
                    next_check_in = max(0.0, self._safe_float(raw_progress.get("next_check_in_s")))
                    if definition.check_interval_s > 0:
                        next_check_in = min(definition.check_interval_s, next_check_in)
                        elapsed = definition.check_interval_s - next_check_in
                        progress.last_check = now - elapsed
                    else:
                        progress.last_check = now
                    progress.disturbance = self._clamp_disturbance(definition, disturbance)
                    progress.cooldown_ends_at = now + cooldown_remaining

            raw_active = raw_state.get("active_by_pool")
            if not isinstance(raw_active, dict):
                return

            for pool_name, raw_entry in raw_active.items():
                if not isinstance(pool_name, str) or not isinstance(raw_entry, dict):
                    continue
                hunt_id = raw_entry.get("hunt_id")
                if not isinstance(hunt_id, str):
                    continue
                definition = self._hunts_by_id.get(hunt_id)
                if not definition or definition.pool_name != pool_name:
                    continue
                if pool_name in self._active_by_pool:
                    continue
                remaining_s = max(0.0, self._safe_float(raw_entry.get("remaining_s")))
                if remaining_s <= 0:
                    continue
                self._active_by_pool[pool_name] = ActiveHunt(
                    definition=definition,
                    started_at=now,
                    ends_at=now + remaining_s,
                )

    def _emit_notification(self, message: str) -> None:
        with self._lock:
            if self._suppress_notifications:
                self._pending_notifications.append(message)
                return
        print(f"\n🔔 {message}")
        sys.stdout.flush()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            notifications: List[str] = []

            with self._lock:
                for pool_name, active in list(self._active_by_pool.items()):
                    if now < active.ends_at:
                        continue
                    self._active_by_pool.pop(pool_name, None)
                    progress = self._progress_by_hunt.get(active.definition.hunt_id)
                    if progress:
                        progress.cooldown_ends_at = max(
                            progress.cooldown_ends_at,
                            now + max(0.0, active.definition.cooldown_s),
                        )
                    notifications.append(f"A hunt '{active.definition.name}' terminou.")

                for definition in self._hunts:
                    progress = self._progress_by_hunt.get(definition.hunt_id)
                    if not progress:
                        continue
                    if now - progress.last_check < definition.check_interval_s:
                        continue

                    progress.last_check = now
                    if definition.pool_name in self._active_by_pool:
                        continue

                    if definition.disturbance_decay_per_check > 0:
                        decayed = progress.disturbance - definition.disturbance_decay_per_check
                        progress.disturbance = self._clamp_disturbance(definition, decayed)

                    if now < progress.cooldown_ends_at:
                        continue

                    guaranteed = progress.disturbance >= definition.disturbance_max
                    dynamic_spawn_chance = 0.0
                    if definition.disturbance_max > 0:
                        dynamic_spawn_chance = max(
                            0.0,
                            min(1.0, progress.disturbance / definition.disturbance_max),
                        )
                    should_spawn = guaranteed or (
                        dynamic_spawn_chance > 0 and random.random() <= dynamic_spawn_chance
                    )
                    if not should_spawn:
                        continue

                    self._active_by_pool[definition.pool_name] = ActiveHunt(
                        definition=definition,
                        started_at=now,
                        ends_at=now + definition.duration_s,
                    )
                    progress.disturbance = 0.0
                    notifications.append(
                        f"Hunt iniciada em {definition.pool_name}: {definition.name}"
                    )

            for message in notifications:
                self._emit_notification(message)

            time.sleep(1)

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp_disturbance(definition: HuntDefinition, value: float) -> float:
        upper = max(0.0, definition.disturbance_max)
        if upper <= 0:
            return 0.0
        return max(0.0, min(upper, float(value)))
