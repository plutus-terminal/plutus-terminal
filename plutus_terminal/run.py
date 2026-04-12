"""Run plutus terminal."""

from __future__ import annotations

import asyncio
import ctypes
import gc
from importlib import import_module
from pathlib import Path
import platform
import sys
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QSplashScreen,
    QSystemTrayIcon,
)
from qasync import QEventLoop, asyncSlot
import setproctitle

from plutus_terminal.ui import resources

if TYPE_CHECKING:
    from plutus_terminal.core.password_guard import PasswordGuard


class StyledSplashScreen(QSplashScreen):
    """Styled splash screen."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.setObjectName("splash_screen")
        self._pixmap = QPixmap(":/general/splash_screen")
        self.setPixmap(self._pixmap)

        self._message = ""
        width = self._pixmap.size().width()
        height = self._pixmap.size().height()
        self._pos = QPoint(int(width * 0.6), int(height * 0.75))
        self._color: QColor | Qt.GlobalColor = Qt.GlobalColor.white
        self.setFont(QFont("Segoe UI", 18))
        self.font().setBold(True)
        self.font().setUnderline(True)

    def show_message(
        self, text: str, color: QColor | Qt.GlobalColor = Qt.GlobalColor.white
    ) -> None:
        """Show message."""
        self._message = text
        self._color = color
        self._reposition()
        self.show()

    def _reposition(self) -> None:
        """Force repaint."""
        self.repaint()

    def paintEvent(self, event: Any) -> None:  # noqa: ANN401
        """Override paint event."""
        super().paintEvent(event)
        if not self._message:
            return
        painter = QPainter(self)
        painter.setPen(self._color)
        painter.drawText(self._pos, self._message)
        painter.end()


class PlutusSystemTrayApp(QApplication):
    """Plutus System Tray App."""

    def __init__(self, argv: list[str]) -> None:
        """Initialize."""
        super().__init__(argv)
        self.splash_screen = StyledSplashScreen()
        self.splash_screen.show()
        self.splash_screen.raise_()
        self.splash_screen.show_message(
            "Initializing Plutus Terminal...",
        )
        self.processEvents()

        relative_path = Path(__file__).parent
        with Path.open(relative_path.joinpath("ui/style.qss")) as f:
            self.setStyleSheet(f.read())
        self.processEvents()

        self.pass_guard = self.input_password()
        self._create_controller()

        self._tray_icon = QSystemTrayIcon()
        self._tray_icon.setIcon(QPixmap(":/icons/plutus_icon"))
        self._tray_icon.setToolTip("Plutus Terminal")

        self._init_tray()

    def _create_controller(self) -> None:
        """Create controller."""
        self.splash_screen.show_message("Creating Plutus Controller...")
        self.processEvents()
        plutus_controller_module = import_module("plutus_terminal.controller.plutus_controller")
        plutus_controller = plutus_controller_module.PlutusController
        self.plutus_controller = plutus_controller(self.pass_guard, self._app_config)

    def _init_tray(self) -> None:
        """Initialize tray icon."""
        menu = QMenu()
        menu.addAction("Open Terminal", self.plutus_controller.show_main_window)
        menu.addAction("Exit", self.exit)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.show()

        self._tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason: int) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.plutus_controller.show_main_window()

    async def init_and_show(self) -> None:
        """Initialize window and show."""
        self._app_config.load_all_configs()
        self.splash_screen.show_message("Initializing Plutus Controller...")
        await self.plutus_controller.init_async()
        self.splash_screen.hide()
        self.plutus_controller.show_main_window()

    def validate_if_account(self) -> None:
        """Validate if there is at least one account.

        If no account is found a new account dialog will be shown.
        """
        config_module = import_module("plutus_terminal.core.config")
        new_account_module = import_module("plutus_terminal.ui.widgets.new_account")
        app_config = config_module.AppConfig
        new_account_dialog_cls = new_account_module.NewAccountDialog
        if not app_config.get_all_accounts():
            new_account_dialog = new_account_dialog_cls(self.pass_guard, self._app_config)
            if not new_account_dialog.exec():
                sys.exit()

    def input_password(self) -> PasswordGuard:
        """Input password."""
        self.splash_screen.show_message(
            "Unlocking Plutus Terminal...",
        )
        self.processEvents()
        config_module = import_module("plutus_terminal.core.config")
        password_guard_module = import_module("plutus_terminal.core.password_guard")
        password_dialog_module = import_module("plutus_terminal.ui.widgets.password_dialog")
        app_config = config_module.AppConfig
        password_guard_cls = password_guard_module.PasswordGuard
        create_password_dialog = password_dialog_module.CreatePasswordDialog
        unlock_password_dialog = password_dialog_module.UnlockPasswordDialog
        self._app_config = app_config()
        pass_guard = password_guard_cls(self._app_config)
        dialog: Any
        if self._app_config.get_gui_settings("first_run"):
            dialog = create_password_dialog(pass_guard)
            if not dialog.exec():
                sys.exit()
        else:
            dialog = unlock_password_dialog(pass_guard)
            if not dialog.exec():
                sys.exit()
        if not pass_guard.password:
            sys.exit()
        return pass_guard

    @asyncSlot()
    async def cleanup(self) -> None:
        """Clean up async connections before closing."""
        await self.plutus_controller.stop_async()


def run() -> None:
    """Run plutus terminal."""
    app = PlutusSystemTrayApp([])

    # Override gc threshold
    gc.set_threshold(100_000, 50, 100)

    # Set process name
    if platform.system() == "Windows":
        ctypes.windll.kernel32.SetConsoleTitleW("Plutus Terminal")  # type: ignore
    else:
        setproctitle.setproctitle("Plutus Terminal")

    log_utils = import_module("plutus_terminal.log_utils")
    install_asyncio_exception_logging = log_utils.install_asyncio_exception_logging
    setup_logging = log_utils.setup_logging
    setup_logging()

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    install_asyncio_exception_logging(event_loop)

    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    app.validate_if_account()

    async def run_and_await() -> None:
        """Run all and await close event."""
        await app.init_and_show()
        await app_close_event.wait()

    event_loop.create_task(run_and_await())
    event_loop.run_forever()

    event_loop.run_until_complete(app.cleanup())
    event_loop.close()


if __name__ == "__main__":
    run()
