# ruff: noqa: S101, SLF001

"""Unit tests for basic reusable UI widgets and dialogs."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from PySide6 import QtCore, QtGui, QtWidgets
import pytest

from plutus_terminal.core.exceptions import InvalidPasswordError
from plutus_terminal.ui.widgets.account_picker import AccountPicker
from plutus_terminal.ui.widgets.clock import Clock
from plutus_terminal.ui.widgets.decimal_spin_box import DecimalSpinBox, DecimalSpinBoxWithButton
from plutus_terminal.ui.widgets.double_spin_button import DoubleSpinBoxWithButton
from plutus_terminal.ui.widgets.image_web_viewer import ImageDisplayModal, ImageWebViewer
from plutus_terminal.ui.widgets.log_viewer import LogViewer
from plutus_terminal.ui.widgets.password_dialog import CreatePasswordDialog, UnlockPasswordDialog
from plutus_terminal.ui.widgets.toast import Toast
from plutus_terminal.ui.widgets.top_bar_widget import TopBar
from tests.ui.helpers import (
    AppConfigStub,
    UIControllerStub,
    create_closed_task,
    ensure_app,
    process_events,
    run_async,
)

if TYPE_CHECKING:
    from pathlib import Path


ensure_app()

_LOG_VIEWER_BUTTON_HEIGHT = 35
_TOAST_TIMEOUT_SECONDS = 7
_TOAST_TIMEOUT_MILLISECONDS = 7000


class _PasswordGuard:
    """Password guard double for password dialog tests."""

    def __init__(self) -> None:
        self._password = ""

    @property
    def password(self) -> str:
        return self._password

    @password.setter
    def password(self, value: str) -> None:
        if value == "wrong":
            raise InvalidPasswordError
        self._password = value


def test_top_bar_adds_widget_to_layout() -> None:
    """TopBar keeps appended widgets in the visible header row."""
    bar = TopBar("Example")
    extra = QtWidgets.QLabel("extra")

    bar.add_widget(extra)

    assert bar.title.text() == "Example"
    assert bar.bar_layout.indexOf(extra) >= 0


def test_decimal_spin_box_tracks_decimal_values() -> None:
    """DecimalSpinBox preserves Decimal semantics across setters and changes."""
    box = DecimalSpinBox()
    observed: list[Decimal] = []
    box.decimalValueChanged.connect(observed.append)

    box.setRange(Decimal("1.25"), Decimal("9.75"))
    box.setValue(Decimal("2.5"))

    assert box.minimum() == Decimal("1.25")
    assert box.maximum() == Decimal("9.75")
    assert box.value() == Decimal("2.5")
    assert observed[-1] == Decimal("2.5")


def test_decimal_spin_box_with_button_starts_at_zero_minimum() -> None:
    """Trade spin boxes should not allow negative values by default."""
    box = DecimalSpinBoxWithButton("USD")

    assert box.minimum() == Decimal("0")
    assert box.button.text() == "USD"


def test_double_spin_box_button_emits_signal() -> None:
    """Embedded spin-box button stays clickable for auxiliary actions."""
    box = DoubleSpinBoxWithButton("%")
    observed: list[str] = []
    box.buttonClicked.connect(lambda: observed.append("clicked"))

    box.button.click()

    assert observed == ["clicked"]


def test_clock_rejects_invalid_timezone() -> None:
    """Clock validates zoneinfo names instead of silently accepting bad input."""
    with patch(
        "plutus_terminal.ui.widgets.clock.asyncio.create_task",
        side_effect=create_closed_task,
    ):
        clock = Clock()

    with pytest.raises(ValueError, match="Invalid timezone"):
        clock.set_timezone("Mars/Olympus_Mons")


def test_account_picker_switches_to_selected_account() -> None:
    """Picking an existing account updates the shared current account."""
    controller = UIControllerStub(app_config=AppConfigStub())
    second = SimpleNamespace(id=2, username="alt", exchange_name="orderly", exchange_type=0)
    controller.app_config._accounts.append(second)
    picker = AccountPicker(controller)

    picker._on_account_changed(1)

    assert controller.app_config.current_keyring_account == second


def test_account_picker_restores_previous_index_when_new_account_is_cancelled() -> None:
    """Cancelling the new-account flow keeps the current account selected."""
    controller = UIControllerStub(app_config=AppConfigStub())

    class _CancelledDialog:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.new_account = None

        def exec(self) -> int:
            return 0

    with patch("plutus_terminal.ui.widgets.account_picker.NewAccountDialog", _CancelledDialog):
        picker = AccountPicker(controller)
        original_index = picker.currentIndex()

        picker._on_account_changed(picker.count() - 1)

    assert picker.currentIndex() == original_index


def test_create_password_dialog_requires_matching_passwords() -> None:
    """Password creation should block mismatched confirmation input."""
    dialog = CreatePasswordDialog(_PasswordGuard())
    dialog._password_line_edit.setText("alpha")
    dialog._confirm_line_edit.setText("beta")

    dialog._create_password()

    assert dialog._status_label.text() == "Passwords do not match"


def test_unlock_password_dialog_rejects_invalid_password() -> None:
    """Unlock dialog surfaces invalid-password failures to the user."""
    dialog = UnlockPasswordDialog(_PasswordGuard())
    dialog._password_line_edit.setText("wrong")

    dialog._unlock_password()

    assert dialog._status_label.text() == "Invalid password"


def test_log_viewer_loads_tails_and_copies_log_content(tmp_path: Path) -> None:
    """Log viewer should display, tail, and copy the active session log."""
    log_path = tmp_path / "session.log"
    log_path.write_text("line-1\nline-2", encoding="utf-8")
    viewer = LogViewer()
    viewer._log_path = log_path

    with patch("plutus_terminal.ui.widgets.log_viewer.Toast.show_message") as show_message:
        viewer.show()
        process_events()
        log_path.write_text("line-1\nline-2\nline-3", encoding="utf-8")
        viewer._poll_log_file()
        viewer._copy_log_content()

    assert "line-3" in viewer._log_view.toPlainText()
    assert QtWidgets.QApplication.clipboard().text() == "line-1\nline-2\nline-3"
    assert viewer.windowIcon().isNull() is False
    assert viewer._toggle_tail_button.minimumHeight() == _LOG_VIEWER_BUTTON_HEIGHT
    show_message.assert_called()


def test_toast_pin_toggle_updates_object_name() -> None:
    """Pinned toasts should stop auto-close and expose their pinned state."""
    toast_config = SimpleNamespace(get_gui_settings=lambda _key: "top_right")
    with patch("plutus_terminal.ui.widgets.toast.AppConfig", return_value=toast_config):
        toast = Toast()
        toast._timer.setInterval(100)
        toast._timer.start()

        toast._pin_toast()
        assert toast.objectName() == "pinned"
        assert toast._timer.isActive() is False

        toast._pin_toast()
        assert toast.objectName() == ""


def test_image_web_viewer_sets_pixmap_from_network_reply() -> None:
    """ImageWebViewer should load scaled image data from a reply payload."""
    parent = QtWidgets.QWidget()
    parent.resize(320, 200)
    viewer = ImageWebViewer(parent)
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("red"))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")

    class _Reply:
        def readAll(self) -> QtCore.QByteArray:
            return buffer.data()

    viewer._set_newtwork_image(_Reply())

    assert viewer.pixmap() is not None
    assert viewer.pixmap().isNull() is False


def test_image_display_modal_shows_for_main_window() -> None:
    """Image modal should attach to the active top-level main window."""
    window = QtWidgets.QMainWindow()
    window.resize(400, 300)
    window.show()
    pixmap = QtGui.QPixmap(20, 20)
    pixmap.fill(QtGui.QColor("blue"))

    ImageDisplayModal.show_modal(pixmap)
    process_events()

    modals = window.findChildren(ImageDisplayModal)
    assert modals


def test_toast_show_message_updates_existing_message() -> None:
    """Toast message ids should reuse the existing toast instead of stacking duplicates."""
    message_id = b"toast-id"
    with (
        patch(
            "plutus_terminal.ui.widgets.toast.Toast.show_widget", return_value=message_id
        ) as show_widget,
        patch("plutus_terminal.ui.widgets.toast.Toast.update_message") as update_message,
    ):
        first = Toast.show_message("hello", message_id=message_id)
        Toast._toasts_win[message_id] = Mock()
        second = Toast.show_message("updated", message_id=message_id)

    assert first == second == message_id
    show_widget.assert_called_once()
    update_message.assert_called_once()


def test_toast_show_widget_converts_seconds_to_milliseconds() -> None:
    """Toast widgets should store timeout values in seconds but start the timer in ms."""
    app_config = AppConfigStub()

    class _FakeTimer:
        def __init__(self) -> None:
            self.interval = None

        def setInterval(self, interval: int) -> None:
            self.interval = interval

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    fake_timer = _FakeTimer()

    def _fake_init(
        self: Toast,
        _parent: QtWidgets.QWidget | None = None,
        desktop: bool = False,
        message_id: bytes | None = None,
        toast_kind: object = None,
    ) -> None:
        self._timer = fake_timer  # type: ignore[assignment]
        self._desktop = desktop  # type: ignore[assignment]
        self._toast_kind = toast_kind  # type: ignore[assignment]
        self._app_config = app_config  # type: ignore[assignment]
        self._id = message_id or b"toast-id"  # type: ignore[assignment]

    def _fake_add_message_widget(_self: Toast, _message_widget: QtWidgets.QWidget) -> None:
        return None

    def _fake_set_property(_self: Toast, *_args: object, **_kwargs: object) -> None:
        return None

    def _fake_show(_self: Toast) -> None:
        return None

    def _fake_resize(_self: Toast, *_args: object, **_kwargs: object) -> None:
        return None

    fake_window = QtWidgets.QMainWindow()
    fake_window.resize(400, 300)

    with (
        patch("plutus_terminal.ui.widgets.toast.AppConfig", return_value=app_config),
        patch.object(Toast, "__init__", _fake_init),
        patch.object(Toast, "add_message_widget", _fake_add_message_widget),
        patch.object(Toast, "setProperty", _fake_set_property),
        patch.object(Toast, "show", _fake_show),
        patch.object(Toast, "resize", _fake_resize),
        patch(
            "plutus_terminal.ui.widgets.toast.QApplication.topLevelWidgets",
            return_value=[fake_window],
        ),
    ):
        Toast.show_widget(QtWidgets.QLabel("toast"), timeout=_TOAST_TIMEOUT_SECONDS)

    assert fake_timer.interval == _TOAST_TIMEOUT_MILLISECONDS
