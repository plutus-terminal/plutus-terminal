"""Clock widget with timezone support."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
from zoneinfo import ZoneInfo

from PySide6 import QtWidgets

LOGGER = logging.getLogger(__name__)


class Clock(QtWidgets.QLabel):
    """Clock widget with timezone support."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("clock")
        self._timezone = datetime.now().astimezone().tzinfo
        self._async_tasks: list[asyncio.Task] = []
        self._async_tasks.append(asyncio.create_task(self._update_time()))

    def set_timezone(self, timezone_name: str) -> None:
        """Set the timezone for the clock.

        Args:
            timezone_name: Timezone name (from zoneinfo database)
        """
        try:
            self._timezone = ZoneInfo(timezone_name)
            LOGGER.debug("Changed timezone to %s", timezone_name)
        except KeyError:
            LOGGER.exception("Invalid timezone: %s", timezone_name)
            msg = f"Invalid timezone: {timezone_name}"
            raise ValueError(msg) from None

    async def _update_time(self) -> None:
        """Update time display."""
        while True:
            # Get current UTC time first
            utc_time = datetime.now(timezone.utc)
            # Convert to target timezone
            local_time = utc_time.astimezone(self._timezone)
            formatted_time = local_time.strftime("%H:%M:%S.%f")[:-3]
            self.setText(formatted_time)
            await asyncio.sleep(0.1)
