from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

from utils.manager_lifecycle import ManagerLifecycle

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
    remaining_fish_names: List[str]

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

        self._lifecycle = ManagerLifecycle()
        self._lock = self._lifecycle.lock

    def start(self) -> None:
        self._lifecycle.start(self._run_loop, enabled=bool(self._hunts))

    def stop(self) -> None:
        self._lifecycle.stop()

    def suppress_notifications(self, value: bool) -> None:
        self._lifecycle.suppress_notifications(value)

    def pop_notifications(self) -> List[str]:
        return self._lifecycle.pop_notifications()

    def get_active_hunt_for_pool(self, pool_name: str) -> Optional[ActiveHunt]:
        with self._lock:
            return self._active_by_pool.get(pool_name)

    def list_hunts(self) -> List[HuntDefinition]:
        with self._lock:
            return list(self._hunts)

    def get_available_fish_for_pool(self, pool_name: str) -> List["FishProfile"]:
        with self._lock:
            active = self._active_by_pool.get(pool_name)
            if not active:
                return []
            remaining_names = set(active.remaining_fish_names)
            return [
                fish
                for fish in active.definition.fish_profiles
                if fish.name in remaining_names
            ]

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
            self._active_by_pool[selected.pool_name] = self._build_active_hunt(selected, now)
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

    def get_available_fish_for_pool(self, pool_name: str) -> List["FishProfile"]:
        with self._lock:
            active = self._active_by_pool.get(pool_name)
            if not active:
                return []
            return list(self._resolve_remaining_fish(active))

    def consume_hunt_fish(
        self,
        pool_name: str,
        fish_name: str,
        *,
        catchable_fish_names: set[str],
    ) -> bool:
        del catchable_fish_names

        notification: Optional[str] = None
        with self._lock:
            active = self._active_by_pool.get(pool_name)
            if not active:
                return False

            remaining_fish_names = [
                name for name in active.remaining_fish_names if name != fish_name
            ]
            if len(remaining_fish_names) == len(active.remaining_fish_names):
                return False

            active.remaining_fish_names = remaining_fish_names
            if active.remaining_fish_names:
                return False

            notification = self._end_active_hunt_locked(
                pool_name,
                ended_at=time.monotonic(),
            )

        if notification:
            self._emit_notification(notification)
        return bool(notification)

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
                    "remaining_fish_names": list(active.remaining_fish_names),
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
                remaining_fish_names = self._restore_remaining_fish_names(
                    definition,
                    raw_entry.get("remaining_fish_names"),
                )
                if not remaining_fish_names:
                    continue
                self._active_by_pool[pool_name] = ActiveHunt(
                    definition=definition,
                    started_at=now,
                    ends_at=now + remaining_s,
                    remaining_fish_names=remaining_fish_names,
                )

    def _emit_notification(self, message: str) -> None:
        self._lifecycle.emit_notification(message)

    def _run_loop(self) -> None:
        while not self._lifecycle.stop_event.is_set():
            now = time.monotonic()
            notifications: List[str] = []

            with self._lock:
                for pool_name, active in list(self._active_by_pool.items()):
                    if now < active.ends_at:
                        continue
                    notification = self._end_active_hunt_locked(pool_name, ended_at=now)
                    if notification:
                        notifications.append(notification)

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

                    self._active_by_pool[definition.pool_name] = self._build_active_hunt(
                        definition,
                        now,
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
    def _build_active_hunt(definition: HuntDefinition, now: float) -> ActiveHunt:
        return ActiveHunt(
            definition=definition,
            started_at=now,
            ends_at=now + definition.duration_s,
            remaining_fish_names=[fish.name for fish in definition.fish_profiles],
        )

    @staticmethod
    def _restore_remaining_fish_names(
        definition: HuntDefinition,
        raw_remaining_fish_names: object,
    ) -> List[str]:
        if not isinstance(raw_remaining_fish_names, list):
            return [fish.name for fish in definition.fish_profiles]

        fish_counts: Dict[str, int] = {}
        for fish in definition.fish_profiles:
            fish_counts[fish.name] = fish_counts.get(fish.name, 0) + 1

        restored: List[str] = []
        for raw_name in raw_remaining_fish_names:
            if not isinstance(raw_name, str):
                continue
            remaining_count = fish_counts.get(raw_name, 0)
            if remaining_count <= 0:
                continue
            restored.append(raw_name)
            fish_counts[raw_name] = remaining_count - 1
        return restored

    @staticmethod
    def _resolve_remaining_fish(active: ActiveHunt) -> List["FishProfile"]:
        fish_by_name: Dict[str, List["FishProfile"]] = {}
        for fish in active.definition.fish_profiles:
            fish_by_name.setdefault(fish.name, []).append(fish)

        resolved: List["FishProfile"] = []
        for fish_name in active.remaining_fish_names:
            matches = fish_by_name.get(fish_name)
            if not matches:
                continue
            resolved.append(matches.pop(0))
        return resolved

    def _end_active_hunt_locked(
        self,
        pool_name: str,
        *,
        ended_at: float,
    ) -> Optional[str]:
        active = self._active_by_pool.pop(pool_name, None)
        if not active:
            return None

        progress = self._progress_by_hunt.get(active.definition.hunt_id)
        if progress:
            progress.cooldown_ends_at = max(
                progress.cooldown_ends_at,
                ended_at + max(0.0, active.definition.cooldown_s),
            )
        return f"A hunt '{active.definition.name}' terminou."

    @staticmethod
    def _clamp_disturbance(definition: HuntDefinition, value: float) -> float:
        upper = max(0.0, definition.disturbance_max)
        if upper <= 0:
            return 0.0
        return max(0.0, min(upper, float(value)))
