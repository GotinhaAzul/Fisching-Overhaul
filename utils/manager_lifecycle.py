from __future__ import annotations

import sys
import threading
from typing import Callable, List, Optional


class ManagerLifecycle:
    """Shared thread/notification lifecycle used by background managers."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pending_notifications: List[str] = []
        self._suppress_notifications = False

    def start(self, run_loop: Callable[[], None], *, enabled: bool) -> None:
        if not enabled or self._thread:
            return
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._thread = None

    def suppress_notifications(self, value: bool) -> None:
        with self.lock:
            self._suppress_notifications = bool(value)

    def pop_notifications(self) -> List[str]:
        with self.lock:
            notifications = self._pending_notifications[:]
            self._pending_notifications.clear()
        return notifications

    def emit_notification(self, message: str) -> None:
        with self.lock:
            if self._suppress_notifications:
                self._pending_notifications.append(message)
                return
        print(f"\n🔔 {message}")
        sys.stdout.flush()
