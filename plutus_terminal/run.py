"""Run plutus terminal."""

import asyncio
import gc
import logging
from pathlib import Path
import sys
from timeit import default_timer

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QSplashScreen,
    QSystemTrayIcon,
)
from qasync import QEventLoop

from plutus_terminal.core.config import CONFIG, AppConfig
from plutus_terminal.log_utils import setup_logging
from plutus_terminal.ui import resources
from plutus_terminal.ui.main_window import PlutusTerminal
from plutus_terminal.ui.widgets.new_account import NewAccountDialog

LOGGER = logging.getLogger(__name__)


class PlutusSystemTrayApp(QApplication):
    """Plutus System Tray App."""

    def __init__(self, argv: list[str]) -> None:
        """Initialize."""
        super().__init__(argv)
        self._start_time = default_timer()
        self.splash_screen = QSplashScreen()
        self.splash_screen.setPixmap(QPixmap(":/general/splash_screen"))
        self.splash_screen.show()
        self.processEvents()

        self.main_window = PlutusTerminal()

        self._tray_icon = QSystemTrayIcon()
        self._tray_icon.setIcon(QPixmap(":/icons/plutus_icon"))
        self._tray_icon.setToolTip("Plutus Terminal")
        self._init_tray()

    def _init_tray(self) -> None:
        """Initialize tray icon."""
        menu = QMenu()
        menu.addAction("Open Terminal", self.main_window.show)
        menu.addAction("Exit", self.exit)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.show()

        self._tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason: int) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.main_window.show()

    async def init_and_show(self) -> None:
        """Initialize window and show."""
        CONFIG.load_config()
        await self.main_window.init_async()
        self.splash_screen.hide()
        self.main_window.show()

        start_duration = default_timer() - self._start_time
        LOGGER.debug(
            "Plutus Terminal started in %s seconds",
            start_duration,
        )

    def validate_if_account(self) -> None:
        """Validate if there is at least one account.

        If no account is found a new account dialog will be shown.
        """
        if not AppConfig.get_all_keyring_accounts():
            new_account_dialog = NewAccountDialog()
            if not new_account_dialog.exec():
                sys.exit()


def run() -> None:
    """Run plutus terminal."""
    # Override gc threshold
    gc.set_threshold(100_000, 50, 100)

    setup_logging()
    app = PlutusSystemTrayApp([])
    relative_path = Path(__file__).parent
    with Path.open(relative_path.joinpath("ui/style.qss")) as f:
        app.setStyleSheet(f.read())

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    app.validate_if_account()

    event_loop.create_task(app.init_and_show())
    event_loop.run_until_complete(app_close_event.wait())
    event_loop.close()


if __name__ == "__main__":
    run()
