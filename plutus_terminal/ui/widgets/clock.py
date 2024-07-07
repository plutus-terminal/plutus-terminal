"""Clock widget with time from the web."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

from httpx import AsyncClient, ConnectError, HTTPStatusError, ReadTimeout
from PySide6 import QtWidgets
from tenacity import before_sleep_log, retry, retry_if_exception_type, wait_exponential

LOGGER = logging.getLogger(__name__)


class WebClock(QtWidgets.QLabel):
    """Clock widget with time from the web."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self.setObjectName("clock")
        self.async_client = AsyncClient()
        self._last_sync = datetime.now(timezone.utc)
        self._async_tasks: list[asyncio.Task] = []
        self._sync_interval = 60

        self._async_tasks.append(asyncio.create_task(self._update_time()))

    @retry(
        retry=(
            retry_if_exception_type(HTTPStatusError)
            | retry_if_exception_type(ReadTimeout)
            | retry_if_exception_type(ConnectError)
        ),
        wait=wait_exponential(multiplier=1, min=0.15, max=2),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
    )
    async def _update_time(self) -> None:
        """Update time."""
        self._last_sync, offset = await self._get_time_offset()
        while True:
            current_time = datetime.now(timezone.utc)

            if (current_time - self._last_sync).total_seconds() > self._sync_interval:
                self._last_sync, offset = await self._get_time_offset()

            formated_time = (current_time - timedelta(seconds=offset)).strftime(
                "%H:%M:%S",
            )
            self.setText(f"{formated_time} UTC")

            await asyncio.sleep(1)

    async def _get_time_offset(self) -> tuple[datetime, float]:
        """Get time."""
        response = await self.async_client.get(
            "http://worldtimeapi.org/api/timezone/Etc/UTC",
        )
        response.raise_for_status()
        data = response.json()
        api_time = datetime.fromisoformat(data["datetime"])
        local_time = datetime.now(timezone.utc)
        offset = (local_time - api_time).total_seconds()
        LOGGER.debug("Synced time from web, current offest %s", offset)
        return local_time, offset
