# ruff: noqa: S101, SLF001

"""Unit tests for configuration and account-management widgets."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import orjson
from PySide6 import QtCore, QtGui, QtWidgets

from plutus_terminal.core.exceptions import KeyringPasswordNotFoundError
from plutus_terminal.core.news.filter.types import ActionType, FilterType
from plutus_terminal.core.news.tree_news import TreeNews
from plutus_terminal.ui.widgets.config.account_config import AccountConfig, AccountWidget
from plutus_terminal.ui.widgets.config.config_dialog import ConfigDialog
from plutus_terminal.ui.widgets.config.news_config import (
    ColorButton,
    DataMatchingWidget,
    KeywordMatchingWidget,
    NewsFiltersConfig,
    NewsSourceConfig,
)
from plutus_terminal.ui.widgets.config.perps_config import PerpsConfig
from plutus_terminal.ui.widgets.config.terminal_config import TerminalConfig
from plutus_terminal.ui.widgets.config.toast_config import ToastConfig
from plutus_terminal.ui.widgets.new_account import NewAccountDialog
from plutus_terminal.ui.widgets.user_top_bar import UserTopBar
from tests.ui.helpers import AppConfigStub, UIControllerStub, ensure_app, process_events, run_async

if TYPE_CHECKING:
    from pathlib import Path

ensure_app()

_CUSTOM_LEVERAGE_BUTTON_1 = 3
_CUSTOM_LEVERAGE_BUTTON_2 = 7
_CUSTOM_LEVERAGE_BUTTON_7 = 90
_IMPORTED_LEVERAGE = 25
_TWO_CALLS = 2
_DEFAULT_TRADE_VALUE_HIGH = 1000
_API_KEY_SERVICE_COUNT = 3
_TAB_COUNT = 6
_TOAST_MESSAGE_DURATION = 7
_TOAST_WIDGET_DURATION = 42
_DEFAULT_TOAST_WIDGET_DURATION = 35
_RESET_BUTTON_WIDTH = 150


def _user_filter(*, filter_type: FilterType, action_type: ActionType) -> SimpleNamespace:
    """Create a lightweight user filter record."""
    match_pattern = {"keyword": "btc"}
    if filter_type is FilterType.DATA_MATCHING:
        match_pattern["data_key"] = "coin"
    action_args = {"coin": "BTC", "color": [255, 0, 0], "sound_path": ":/sfx/test"}
    return SimpleNamespace(
        id=1,
        filter_type=int(filter_type),
        match_pattern=orjson.dumps(match_pattern).decode("utf-8"),
        action_type=int(action_type),
        action_args=orjson.dumps(action_args).decode("utf-8"),
    )


def test_terminal_config_resets_defaults() -> None:
    """TerminalConfig should restore the built-in GUI defaults for its section."""
    app_config = AppConfigStub()
    app_config.set_gui_settings("news_desktop_notifications", False)
    widget = TerminalConfig(app_config)

    with patch(
        "plutus_terminal.ui.widgets.config.terminal_config.Toast.show_message"
    ) as show_message:
        widget._reset_defaults()

    assert app_config.get_gui_settings("news_desktop_notifications") is True
    assert app_config.get_gui_settings("toast_message_position") == "top_right"
    show_message.assert_called_once()


def test_terminal_config_reset_button_uses_warning_style() -> None:
    """TerminalConfig should style its reset button like the shared warning action."""
    app_config = AppConfigStub()
    widget = TerminalConfig(app_config)

    assert widget._reset_defaults_button.property("class") == "WARNING"
    assert widget._reset_defaults_button.minimumWidth() == _RESET_BUTTON_WIDTH


def test_terminal_config_backup_buttons_use_approved_style_and_equal_width_policy() -> None:
    """TerminalConfig should style backup actions consistently and split the row evenly."""
    app_config = AppConfigStub()
    widget = TerminalConfig(app_config)

    assert widget._import_settings_button.property("class") == "APPROVED"
    assert widget._export_settings_button.property("class") == "APPROVED"
    assert widget._import_settings_button.sizePolicy().horizontalPolicy() == (
        QtWidgets.QSizePolicy.Policy.Expanding
    )
    assert widget._export_settings_button.sizePolicy().horizontalPolicy() == (
        QtWidgets.QSizePolicy.Policy.Expanding
    )


def test_terminal_config_refreshes_unsaved_widget_state() -> None:
    """TerminalConfig should discard unsaved widget edits when refreshed."""
    app_config = AppConfigStub()
    widget = TerminalConfig(app_config)

    widget._show_images_checkbox.blockSignals(True)
    widget._show_images_checkbox.setChecked(False)
    widget._show_images_checkbox.blockSignals(False)
    widget.refresh_from_config()

    assert widget._show_images_checkbox.isChecked() is True
    assert widget._show_desktop_news_checkbox.isChecked() is False


def test_terminal_config_exports_and_imports_local_settings(tmp_path: Path) -> None:
    """TerminalConfig should export and import non-secret local settings snapshots."""
    app_config = AppConfigStub()
    imported_callback = Mock()
    widget = TerminalConfig(app_config, on_settings_imported=imported_callback)
    export_path = tmp_path / "settings.json"
    import_path = tmp_path / "import.json"
    import_path.write_bytes(
        orjson.dumps(
            {
                "version": 1,
                "gui_settings": {
                    "news_show_images": False,
                    "news_desktop_notifications": True,
                    "minimize_to_tray": False,
                    "toast_message_position": "bottom_left",
                    "toast_widget_position": "top_right",
                    "toast_message_duration": 8,
                    "toast_widget_duration": 15,
                },
                "trade_config": {"leverage": _IMPORTED_LEVERAGE},
                "user_filters": [],
            }
        )
    )

    with (
        patch(
            "plutus_terminal.ui.widgets.config.terminal_config.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(str(export_path), "JSON Files (*.json)"),
        ),
        patch(
            "plutus_terminal.ui.widgets.config.terminal_config.QtWidgets.QFileDialog.getOpenFileName",
            return_value=(str(import_path), "JSON Files (*.json)"),
        ),
        patch(
            "plutus_terminal.ui.widgets.config.terminal_config.Toast.show_message"
        ) as show_message,
    ):
        widget._export_local_settings()
        widget._import_local_settings()

    exported_payload = orjson.loads(export_path.read_bytes())
    assert exported_payload["version"] == 1
    assert app_config.get_gui_settings("news_show_images") is False
    assert app_config.get_gui_settings("toast_widget_position") == "top_right"
    assert app_config.leverage == _IMPORTED_LEVERAGE
    imported_callback.assert_called_once()
    assert show_message.call_count == _TWO_CALLS


def test_toast_config_updates_position_and_duration_settings() -> None:
    """ToastConfig should persist the independent message and widget settings."""
    app_config = AppConfigStub()
    widget = ToastConfig(app_config)

    with patch("plutus_terminal.ui.widgets.config.toast_config.Toast.show_message") as show_message:
        widget._set_message_position(widget._message_position_combobox.findData("bottom_right"))
        widget._set_widget_position(widget._widget_position_combobox.findData("top_left"))
        widget._set_message_duration(_TOAST_MESSAGE_DURATION)
        widget._set_widget_duration(_TOAST_WIDGET_DURATION)

    assert app_config.get_gui_settings("toast_message_position") == "bottom_right"
    assert app_config.get_gui_settings("toast_widget_position") == "top_left"
    assert app_config.get_gui_settings("toast_message_duration") == _TOAST_MESSAGE_DURATION
    assert app_config.get_gui_settings("toast_widget_duration") == _TOAST_WIDGET_DURATION
    assert show_message.call_count == _TWO_CALLS


def test_toast_config_resets_defaults() -> None:
    """ToastConfig should restore the built-in toast defaults for its section."""
    app_config = AppConfigStub()
    app_config.set_gui_settings("toast_message_position", "top_right")
    app_config.set_gui_settings("toast_widget_duration", 9000)
    widget = ToastConfig(app_config)

    with patch("plutus_terminal.ui.widgets.config.toast_config.Toast.show_message") as show_message:
        widget._reset_defaults()

    assert app_config.get_gui_settings("toast_message_position") == "bottom_left"
    assert app_config.get_gui_settings("toast_widget_duration") == _DEFAULT_TOAST_WIDGET_DURATION
    show_message.assert_called_once()


def test_toast_config_reset_button_uses_warning_style() -> None:
    """ToastConfig should style its reset button like the shared warning action."""
    app_config = AppConfigStub()
    widget = ToastConfig(app_config)

    assert widget._reset_defaults_button.property("class") == "WARNING"
    assert widget._reset_defaults_button.minimumWidth() == _RESET_BUTTON_WIDTH


def test_toast_config_refreshes_unsaved_widget_state() -> None:
    """ToastConfig should discard unsaved widget edits when refreshed."""
    app_config = AppConfigStub()
    widget = ToastConfig(app_config)

    widget._message_position_combobox.blockSignals(True)
    widget._message_position_combobox.setCurrentIndex(
        widget._message_position_combobox.findData("top_left")
    )
    widget._message_position_combobox.blockSignals(False)
    widget._widget_duration_spin.blockSignals(True)
    widget._widget_duration_spin.setValue(5000)
    widget._widget_duration_spin.blockSignals(False)
    widget.refresh_from_config()

    assert widget._message_position_combobox.currentData() == app_config.get_gui_settings(
        "toast_message_position"
    )
    assert widget._widget_duration_spin.value() == app_config.get_gui_settings(
        "toast_widget_duration"
    )


def test_perps_config_updates_trade_values_and_tp_sl() -> None:
    """PerpsConfig should write the edited trade and TP/SL settings back to config."""
    trade_value_lowest = 11
    trade_value_high = 44
    take_profit = 3.5
    stop_loss = 1.25
    controller = UIControllerStub()
    widget = PerpsConfig(controller)
    widget._trade_lowest_spin.setValue(trade_value_lowest)
    widget._trade_low_spin.setValue(22)
    widget._trade_med_spin.setValue(33)
    widget._trade_high_spin.setValue(trade_value_high)
    widget._tp_spin.setValue(take_profit)
    widget._sl_spin.setValue(stop_loss)

    with patch("plutus_terminal.ui.widgets.config.perps_config.Toast.show_message") as show_message:
        widget._update_trade_values()
        widget._update_tp_sl()

    assert controller.app_config.trade_value_lowest == trade_value_lowest
    assert controller.app_config.trade_value_high == trade_value_high
    assert controller.app_config.take_profit == take_profit
    assert controller.app_config.stop_loss == stop_loss
    assert show_message.call_count == _TWO_CALLS


def test_perps_config_keeps_visible_trade_top_bar() -> None:
    """PerpsConfig should expose a visible top bar for tab consistency."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)

    assert widget.top_bar.isHidden() is False
    assert widget.top_bar.title.text() == "Trade Settings"


def test_perps_config_trade_action_buttons_use_approved_style() -> None:
    """PerpsConfig should align its trade actions with the approved config button style."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)

    assert widget._tp_sl_update.property("class") == "APPROVED"
    assert widget._trade_values_update.property("class") == "APPROVED"
    assert widget._leverage_button_update.property("class") == "APPROVED"
    assert widget._leverage_set_button.property("class") == "APPROVED"


def test_perps_config_shows_current_pair_leverage_hint() -> None:
    """PerpsConfig should display and refresh the selected pair leverage cap."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)

    assert widget._pair_leverage_hint.text() == (
        "Current pair max: BTC/USDC 25x. Each pair may use a different cap."
    )

    run_async(controller.change_current_pair, "Crypto.ETH/USDC")
    process_events()

    assert widget._pair_leverage_hint.text() == (
        "Current pair max: ETH/USDC 50x. Each pair may use a different cap."
    )


def test_perps_config_exposes_100x_leverage_shortcut() -> None:
    """PerpsConfig should offer a 100x preset leverage button."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)

    assert widget._leverage_group.button(100) is not None


def test_perps_config_updates_custom_leverage_button_values() -> None:
    """PerpsConfig should persist user-defined leverage preset button values."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)

    widget._leverage_button_spins[0].setValue(3)
    widget._leverage_button_spins[1].setValue(7)
    widget._leverage_button_spins[6].setValue(90)

    with patch("plutus_terminal.ui.widgets.config.perps_config.Toast.show_message") as show_message:
        widget._update_leverage_button_values()

    assert controller.app_config.leverage_button_1 == _CUSTOM_LEVERAGE_BUTTON_1
    assert controller.app_config.leverage_button_2 == _CUSTOM_LEVERAGE_BUTTON_2
    assert controller.app_config.leverage_button_7 == _CUSTOM_LEVERAGE_BUTTON_7
    assert widget._leverage_group.button(_CUSTOM_LEVERAGE_BUTTON_7) is not None
    show_message.assert_called_once()


def test_perps_config_appends_live_exchange_maximum_button() -> None:
    """PerpsConfig should add the exchange max leverage button from API metadata."""
    controller = UIControllerStub()
    controller.current_exchange.max_leverage = 125
    widget = PerpsConfig(controller)

    assert widget._leverage_group.button(125) is not None


def test_perps_config_resets_defaults() -> None:
    """PerpsConfig should restore the default trade settings for the current account."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)
    widget._tp_spin.setValue(8.5)
    widget._trade_high_spin.setValue(999)

    with patch("plutus_terminal.ui.widgets.config.perps_config.Toast.show_message") as show_message:
        widget._reset_defaults()

    assert controller.app_config.take_profit == 0.0
    assert controller.app_config.trade_value_high == _DEFAULT_TRADE_VALUE_HIGH
    show_message.assert_called_once()


def test_perps_config_refreshes_unsaved_values() -> None:
    """PerpsConfig should discard unsaved edits when the dialog is reopened."""
    controller = UIControllerStub()
    widget = PerpsConfig(controller)

    widget._tp_spin.setValue(9.5)
    widget._trade_high_spin.setValue(777)
    widget.refresh_from_config()

    assert widget._tp_spin.value() == controller.app_config.take_profit
    assert widget._trade_high_spin.value() == controller.app_config.trade_value_high


def test_account_widget_deletes_account_via_app_config() -> None:
    """AccountWidget should remove its account through the shared config object."""
    app_config = AppConfigStub()
    account = app_config.current_keyring_account
    widget = AccountWidget(account, app_config)

    with patch(
        "plutus_terminal.ui.widgets.config.account_config.Toast.show_message"
    ) as show_message:
        widget._delete_account()

    assert account not in app_config.get_all_accounts()
    show_message.assert_called_once()


def test_account_widget_centers_delete_button_on_right() -> None:
    """AccountWidget should vertically center the delete button on the right edge."""
    app_config = AppConfigStub()
    widget = AccountWidget(app_config.current_keyring_account, app_config)

    delete_item = widget._top_layout.itemAt(widget._top_layout.count() - 1)

    assert delete_item.alignment() & QtCore.Qt.AlignmentFlag.AlignVCenter
    assert delete_item.alignment() & QtCore.Qt.AlignmentFlag.AlignRight


def test_account_config_populates_existing_accounts() -> None:
    """AccountConfig should render one AccountWidget per stored account."""
    expected_count = 2
    app_config = AppConfigStub()
    app_config._accounts.append(
        SimpleNamespace(id=2, username="other", exchange_name="orderly", exchange_type=0)
    )
    with patch(
        "plutus_terminal.ui.widgets.config.account_config.AppConfig.get_all_accounts",
        side_effect=app_config.get_all_accounts,
    ):
        widget = AccountConfig(SimpleNamespace(), app_config)

    account_widgets = widget.findChildren(AccountWidget)
    assert len(account_widgets) == expected_count


def test_color_button_emits_color_change() -> None:
    """ColorButton should emit changes when assigned a new color."""
    button = ColorButton(color=QtGui.QColor("red"))
    observed: list[QtGui.QColor] = []
    button.color_changed.connect(observed.append)

    button.set_color(QtGui.QColor("green"))

    assert observed[-1].name() == "#008000"


def test_keyword_matching_widget_writes_current_rule_to_db() -> None:
    """Keyword filter widgets should serialize their edited state back to the model."""
    widget = KeywordMatchingWidget(
        _user_filter(
            filter_type=FilterType.KEYWORD_MATCHING,
            action_type=ActionType.COIN_ASSOCIATION,
        )
    )
    widget.show()
    process_events()
    widget._match_pattern.setText("eth")
    widget._coin_line.setText("ETH")

    with patch(
        "plutus_terminal.ui.widgets.config.news_config.AppConfig.write_model_to_db"
    ) as write_db:
        widget.write_to_db()

    assert "eth" in widget._user_filter.match_pattern
    assert "ETH" in widget._user_filter.action_args
    write_db.assert_called_once()


def test_data_matching_widget_switches_visible_inputs_by_action() -> None:
    """Data filter widgets should only show the controls relevant to the chosen action."""
    widget = DataMatchingWidget(
        _user_filter(filter_type=FilterType.DATA_MATCHING, action_type=ActionType.COIN_ASSOCIATION)
    )
    widget.show()
    process_events()

    widget.on_action_change(widget._action_combo.findData(ActionType.SOUND_ASSOCIATION))
    assert widget._sound_combo.isVisible() is True
    assert widget._coin_line.isVisible() is False

    widget.on_action_change(widget._action_combo.findData(ActionType.IGNORE))
    assert widget._sound_combo.isVisible() is False
    assert widget._coin_line.isVisible() is False


def test_news_source_config_toggles_password_visibility_and_validates_api_keys() -> None:
    """NewsSourceConfig should expose saved values and block invalid API key formats."""
    controller = UIControllerStub()
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
            side_effect=KeyringPasswordNotFoundError,
        ),
    ):
        widget = NewsSourceConfig(controller)

    widget._tree_password_button.click()
    widget._tree_input.setText("bad key")

    assert widget._tree_input.echoMode() == QtWidgets.QLineEdit.EchoMode.Normal
    assert widget._tree_button.isEnabled() is False
    assert widget._tree_validation_label.isHidden() is False


def test_news_source_config_records_updated_news_source_key() -> None:
    """NewsSourceConfig should persist changed API keys and restart the news manager."""
    controller = UIControllerStub()
    with patch(
        "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
        side_effect=KeyringPasswordNotFoundError,
    ):
        widget = NewsSourceConfig(controller)

    widget._tree_input.setText("new-key")
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
            side_effect=KeyringPasswordNotFoundError,
        ),
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring_manager.set_news_source_api_key"
        ) as set_key,
        patch("plutus_terminal.ui.widgets.config.news_config.Toast.show_message") as show_message,
    ):
        run_async(widget.record_news_source_key, TreeNews.NEWS_SERVICE_NAME)

    set_key.assert_called_once()
    assert controller.news_manager_restarts == 1
    show_message.assert_called_once()


def test_news_source_config_update_buttons_use_approved_style() -> None:
    """NewsSourceConfig should style API update actions as approved config actions."""
    controller = UIControllerStub()
    with patch(
        "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
        side_effect=KeyringPasswordNotFoundError,
    ):
        widget = NewsSourceConfig(controller)

    assert widget._tree_button.property("class") == "APPROVED"
    assert widget._phoenix_button.property("class") == "APPROVED"
    assert widget._synoptic_button.property("class") == "APPROVED"


def test_news_source_config_resets_defaults() -> None:
    """NewsSourceConfig should clear stored API keys when reset to defaults."""
    controller = UIControllerStub()
    with patch(
        "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
        side_effect=KeyringPasswordNotFoundError,
    ):
        widget = NewsSourceConfig(controller)

    widget._tree_input.setText("abc")
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring.delete_password"
        ) as delete_password,
        patch("plutus_terminal.ui.widgets.config.news_config.Toast.show_message") as show_message,
    ):
        run_async(widget._reset_to_defaults)

    assert widget._tree_input.text() == ""
    assert controller.news_manager_restarts == 1
    assert delete_password.call_count == _API_KEY_SERVICE_COUNT
    show_message.assert_called_once()


def test_news_source_config_refreshes_unsaved_key_changes() -> None:
    """NewsSourceConfig should reload the saved key state when refreshed."""
    controller = UIControllerStub()
    with patch(
        "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
        side_effect=KeyringPasswordNotFoundError,
    ):
        widget = NewsSourceConfig(controller)

    widget._tree_input.setText("temporary-key")
    with patch(
        "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
        side_effect=KeyringPasswordNotFoundError,
    ):
        widget.refresh_from_config()

    assert widget._tree_input.text() == ""


def test_news_filters_config_adds_filters_and_refreshes_manager() -> None:
    """NewsFiltersConfig should add and save filters, then refresh the manager."""
    controller = UIControllerStub()
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.get_all_user_filters",
            return_value=[],
        ),
        patch(
            "plutus_terminal.ui.widgets.config.news_config.list_resources_from_prefix",
            return_value=["ding.wav"],
        ),
    ):
        widget = NewsFiltersConfig(controller)

    widget._add_keyword_filter()
    widget._add_data_filter()

    assert widget._keyword_matching_layout.count() > 1
    assert widget._data_matching_layout.count() > 1

    keyword_widget = next(
        item.widget()
        for item in [
            widget._keyword_matching_layout.itemAt(index)
            for index in range(widget._keyword_matching_layout.count())
        ]
        if isinstance(item.widget(), KeywordMatchingWidget)
    )
    keyword_widget._match_pattern.setText("eth")
    keyword_widget._coin_line.setText("ETH")

    data_widget = next(
        item.widget()
        for item in [
            widget._data_matching_layout.itemAt(index)
            for index in range(widget._data_matching_layout.count())
        ]
        if isinstance(item.widget(), DataMatchingWidget)
    )
    data_widget._match_pattern.setText("btc")
    data_widget._coin_line.setText("BTC")

    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.write_model_to_db"
        ) as write_db,
        patch("plutus_terminal.ui.widgets.config.news_config.Toast.show_message") as show_message,
    ):
        widget._save_filters()

    assert write_db.call_count == _TWO_CALLS
    assert controller.news_filter_manager.updated is True
    show_message.assert_called_once()


def test_news_filters_config_uses_consistent_action_button_sizes() -> None:
    """NewsFiltersConfig should keep its footer action buttons aligned in size."""
    controller = UIControllerStub()
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.get_all_user_filters",
            return_value=[],
        ),
        patch(
            "plutus_terminal.ui.widgets.config.news_config.list_resources_from_prefix",
            return_value=["ding.wav"],
        ),
    ):
        widget = NewsFiltersConfig(controller)

    assert widget._reload_filters_btn.minimumWidth() == _RESET_BUTTON_WIDTH
    assert widget._save_filters_btn.minimumWidth() == _RESET_BUTTON_WIDTH
    assert widget._keyword_matching_add_btn.property("class") == "APPROVED"
    assert widget._data_matching_add_btn.property("class") == "APPROVED"
    assert widget._save_filters_btn.property("class") == "APPROVED"


def test_news_filters_config_blocks_invalid_filter_save_and_warns() -> None:
    """NewsFiltersConfig should warn instead of saving invalid filters."""
    controller = UIControllerStub()
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.get_all_user_filters",
            return_value=[],
        ),
        patch(
            "plutus_terminal.ui.widgets.config.news_config.list_resources_from_prefix",
            return_value=["ding.wav"],
        ),
    ):
        widget = NewsFiltersConfig(controller)

    widget._add_keyword_filter()

    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.write_model_to_db"
        ) as write_db,
        patch("plutus_terminal.ui.widgets.config.news_config.Toast.show_message") as show_message,
    ):
        widget._save_filters()

    write_db.assert_not_called()
    show_message.assert_called_once()


def test_new_account_dialog_creates_account_for_valid_exchange() -> None:
    """NewAccountDialog should validate secrets and create the selected account."""
    app_config = AppConfigStub()

    class _DummyExchange:
        @staticmethod
        def exchange_type() -> int:
            return 0

        @staticmethod
        def name() -> str:
            return "Orderly"

        @staticmethod
        def new_account_info() -> dict[str, object]:
            return {
                "fields": [
                    {"label": "Account ID"},
                    {"label": "API Key"},
                    {"label": "Secret"},
                ]
            }

        @staticmethod
        def validate_secrets(_secrets: list[str]) -> tuple[bool, str]:
            return True, "ok"

    with (
        patch(
            "plutus_terminal.ui.widgets.new_account.VALID_EXCHANGES",
            {"orderly": _DummyExchange},
        ),
        patch(
            "plutus_terminal.ui.widgets.new_account.keyring_manager.set_exchange_password"
        ) as set_password,
        patch(
            "plutus_terminal.ui.widgets.new_account.Toast.show_message",
            return_value=b"toast-id",
        ),
        patch("plutus_terminal.ui.widgets.new_account.Toast.update_message"),
    ):
        dialog = NewAccountDialog(SimpleNamespace(), app_config)
        dialog._account_line_edit.setText("orderly_test")
        for index, line_edit in enumerate(dialog._secrets_line_edits):
            line_edit.setText(f"secret-{index}")
        dialog._create_new_account()

    assert dialog.new_account is not None
    assert app_config.current_keyring_account.username == "orderly_test"
    set_password.assert_called_once()


def test_new_account_dialog_uses_declared_select_field_values() -> None:
    """NewAccountDialog should render generic select fields and store option values."""
    app_config = AppConfigStub()
    pass_guard = SimpleNamespace()
    validated_secrets: list[str] = []

    class _DummyExchange:
        @staticmethod
        def exchange_type() -> int:
            return 0

        @staticmethod
        def name() -> str:
            return "Custom"

        @staticmethod
        def new_account_info() -> dict[str, object]:
            return {
                "fields": [
                    {"label": "API Key"},
                    {"label": "API Secret"},
                    {
                        "label": "Environment",
                        "field_type": "select",
                        "options": [
                            {"label": "Production", "value": "prod"},
                            {"label": "Sandbox", "value": "sandbox"},
                        ],
                    },
                ]
            }

        @staticmethod
        def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
            validated_secrets[:] = secrets
            return True, "ok"

    with (
        patch(
            "plutus_terminal.ui.widgets.new_account.VALID_EXCHANGES",
            {"custom": _DummyExchange},
        ),
        patch(
            "plutus_terminal.ui.widgets.new_account.keyring_manager.set_exchange_password"
        ) as set_password,
        patch(
            "plutus_terminal.ui.widgets.new_account.Toast.show_message",
            return_value=b"toast-id",
        ),
        patch("plutus_terminal.ui.widgets.new_account.Toast.update_message"),
    ):
        dialog = NewAccountDialog(pass_guard, app_config)
        dialog._account_line_edit.setText("custom_test")
        for index, line_edit in enumerate(dialog._secrets_line_edits):
            line_edit.setText(f"secret-{index}")

        network_combo = dialog._secret_inputs[-1]
        assert isinstance(network_combo, QtWidgets.QComboBox)
        assert dialog._secrets_labels[-1].text() == "Environment"

        network_combo.setCurrentIndex(1)
        dialog._create_new_account()

    assert validated_secrets == ["secret-0", "secret-1", "sandbox"]
    assert set_password.call_args.args[0] == "custom_test"
    assert set_password.call_args.args[1] == ["secret-0", "secret-1", "sandbox"]
    assert set_password.call_args.args[2] is pass_guard


def test_config_dialog_builds_expected_tabs() -> None:
    """ConfigDialog should render the project configuration sections as tabs."""
    controller = UIControllerStub()

    class _Section(QtWidgets.QWidget):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

    with (
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsSourceConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsFiltersConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.AccountConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.TerminalConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.ToastConfig", _Section),
    ):
        dialog = ConfigDialog(controller)

    assert dialog._tab_widget.count() == _TAB_COUNT
    assert dialog._tab_widget.tabText(0) == "Trade"
    assert dialog._tab_widget.tabText(1) == "News APIs"
    assert dialog._tab_widget.tabText(2) == "News Filters"
    assert dialog._tab_widget.tabText(4) == "Toasts"
    assert dialog._tab_widget.tabText(5) == "Terminal"


def test_config_dialog_refreshes_sections_before_opening() -> None:
    """ConfigDialog should refresh all sections before showing again."""
    controller = UIControllerStub()

    class _Section(QtWidgets.QWidget):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()
            self.refresh_calls = 0

        def refresh_from_config(self) -> None:
            self.refresh_calls += 1

    with (
        patch("plutus_terminal.ui.widgets.config.config_dialog.PerpsConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsSourceConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsFiltersConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.AccountConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.TerminalConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.ToastConfig", _Section),
    ):
        dialog = ConfigDialog(controller)
        dialog.refresh_from_config()

    assert dialog.persp_config.refresh_calls == 1
    assert dialog.news_source_config.refresh_calls == 1
    assert dialog.news_filters_config.refresh_calls == 1
    assert dialog.account_config.refresh_calls == 1
    assert dialog.terminal_config.refresh_calls == 1
    assert dialog.toast_config.refresh_calls == 1


def test_config_dialog_open_dialog_expands_to_trade_friendly_size() -> None:
    """ConfigDialog should reopen at a size large enough for the trade tab."""
    controller = UIControllerStub()

    class _Section(QtWidgets.QWidget):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()
            self.top_bar = QtWidgets.QWidget()

        def refresh_from_config(self) -> None:
            return None

    with (
        patch("plutus_terminal.ui.widgets.config.config_dialog.PerpsConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsSourceConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsFiltersConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.AccountConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.TerminalConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.ToastConfig", _Section),
    ):
        dialog = ConfigDialog(controller)
        dialog.resize(320, 240)
        dialog.open_dialog()
        process_events()

    assert dialog.width() >= dialog._DEFAULT_OPEN_SIZE.width()
    assert dialog.height() >= dialog._DEFAULT_OPEN_SIZE.height()


def test_user_top_bar_opens_config_dialog() -> None:
    """UserTopBar should expose a configuration button wired to the dialog."""
    config_dialog = SimpleNamespace(open_dialog=Mock())

    class _FakeAccountPicker(QtWidgets.QComboBox):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

    class _FakeClock(QtWidgets.QLabel):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__("clock")

    with (
        patch("plutus_terminal.ui.widgets.user_top_bar.AccountPicker", _FakeAccountPicker),
        patch("plutus_terminal.ui.widgets.user_top_bar.Clock", _FakeClock),
    ):
        bar = UserTopBar(config_dialog, UIControllerStub())
        bar._config_button.click()

    config_dialog.open_dialog.assert_called_once()
