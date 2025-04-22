"""Central controller for managin the application."""

import logging

from plutus_terminal.controller.ui_controller import UIController
from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.news.filter.filter_manager import FilterManager
from plutus_terminal.core.password_guard import PasswordGuard
from plutus_terminal.message_bus import MessageBus
from plutus_terminal.ui.main_window import PlutusMainWindow

LOGGER = logging.getLogger(__name__)


class PlutusController:
    """Central controller for managin the application."""

    def __init__(self, pass_guard: PasswordGuard, app_config: AppConfig) -> None:
        """Initialize sync variables."""
        self.pass_guard = pass_guard

        self._message_bus = MessageBus()
        self._filter_manager = FilterManager()
        self._app_config = app_config
        self.ui_controller = UIController(
            self._message_bus, self._filter_manager, self.pass_guard, self._app_config
        )
        self.main_window = PlutusMainWindow(
            self.ui_controller,
        )

    def show_main_window(self) -> None:
        """Show main window."""
        self.main_window.show()

    async def init_async(self) -> None:
        """Initialize async shared variables."""
        await self.ui_controller.init_async()
        await self.main_window.init_async()

        # Set UI to use the default pair
        await self.ui_controller.change_current_pair(
            self.ui_controller.current_exchange.default_pair,
        )

    async def stop_async(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        LOGGER.debug("Stopping Plutus Terminal async")
        await self.ui_controller.stop_async()
