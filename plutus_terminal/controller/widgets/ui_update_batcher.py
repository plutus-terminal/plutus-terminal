"""Shared UI batching for market-data-driven redraws."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, ClassVar
import weakref

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:
    from collections.abc import Callable


class _UserInteractionEventFilter(QObject):
    """Track user input events that should temporarily outrank redraws."""

    _USER_EVENT_TYPES: ClassVar[set[QEvent.Type]] = {
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.Wheel,
        QEvent.Type.FocusIn,
        QEvent.Type.TouchBegin,
    }

    def __init__(self, batcher: UiUpdateBatcher) -> None:
        """Initialize the event filter with a weak batcher reference."""
        super().__init__()
        self._batcher_ref: weakref.ReferenceType[UiUpdateBatcher] = weakref.ref(batcher)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Record user interaction timing without consuming the event."""
        del watched
        batcher = self._batcher_ref()
        if batcher is None:
            return False
        if event.type() in self._USER_EVENT_TYPES:
            batcher.mark_user_interaction()
        return False


class UiUpdateBatcher(QObject):
    """Coalesce UI redraw work and defer it behind active user input."""

    DEFAULT_FLUSH_INTERVAL_MS: ClassVar[int] = 150
    DEFAULT_USER_PRIORITY_WINDOW_MS: ClassVar[int] = 125
    _shared_instance: ClassVar[UiUpdateBatcher | None] = None

    def __init__(
        self,
        flush_interval_ms: int = DEFAULT_FLUSH_INTERVAL_MS,
        user_priority_window_ms: int = DEFAULT_USER_PRIORITY_WINDOW_MS,
    ) -> None:
        """Initialize batching state and deferred flush timer."""
        super().__init__()
        self._flush_interval_ms = flush_interval_ms
        self._user_priority_window_ms = user_priority_window_ms
        self._pending_updates: dict[str, Callable[[], None]] = {}
        self._user_priority_deadline = 0.0
        self._event_filter: _UserInteractionEventFilter | None = None
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.timeout.connect(self._flush_or_defer)
        self._install_event_filter()

    @classmethod
    def shared(cls) -> UiUpdateBatcher:
        """Return the shared application-wide UI batcher instance."""
        if cls._shared_instance is None:
            cls._shared_instance = cls()
        return cls._shared_instance

    def submit(self, key: str, callback: Callable[[], None]) -> None:
        """Store the latest redraw callback for one logical update key."""
        self._install_event_filter()
        self._pending_updates[key] = callback
        if self._flush_timer.isActive():
            return
        self._flush_timer.start(self._flush_interval_ms)

    def mark_user_interaction(self) -> None:
        """Delay queued redraws briefly so user input runs first."""
        self._user_priority_deadline = time.monotonic() + (self._user_priority_window_ms / 1000)

    def _install_event_filter(self) -> None:
        """Attach the user-input event filter once a Qt app exists."""
        app = QApplication.instance()
        if app is None or self._event_filter is not None:
            return
        self._event_filter = _UserInteractionEventFilter(self)
        app.installEventFilter(self._event_filter)

    def _flush_or_defer(self) -> None:
        """Flush pending redraws unless active user input still has priority."""
        if not self._pending_updates:
            return
        remaining_priority_ms = self._remaining_user_priority_ms()
        if remaining_priority_ms > 0:
            self._flush_timer.start(remaining_priority_ms)
            return
        callbacks = list(self._pending_updates.values())
        self._pending_updates.clear()
        for callback in callbacks:
            callback()

    def _remaining_user_priority_ms(self) -> int:
        """Return remaining user-priority delay in whole milliseconds."""
        remaining_seconds = self._user_priority_deadline - time.monotonic()
        if remaining_seconds <= 0:
            return 0
        return max(math.ceil(remaining_seconds * 1000), 1)
