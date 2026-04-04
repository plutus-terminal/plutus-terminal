# ruff: noqa: S101, SLF001

"""Unit tests for configuration and account-management widgets."""

from __future__ import annotations

from types import SimpleNamespace
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
    NewsConfig,
)
from plutus_terminal.ui.widgets.config.perps_config import PerpsConfig
from plutus_terminal.ui.widgets.config.terminal_config import TerminalConfig
from plutus_terminal.ui.widgets.config.web3_config import RPCConfig, Web3Config
from plutus_terminal.ui.widgets.new_account import NewAccountDialog
from plutus_terminal.ui.widgets.user_top_bar import UserTopBar
from tests.ui.helpers import AppConfigStub, UIControllerStub, ensure_app, process_events, run_async

ensure_app()

_CUSTOM_LEVERAGE_BUTTON_1 = 3
_CUSTOM_LEVERAGE_BUTTON_2 = 7
_CUSTOM_LEVERAGE_BUTTON_7 = 90


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


def test_terminal_config_updates_toast_position_setting() -> None:
    """TerminalConfig should persist toast position changes and notify the user."""
    app_config = AppConfigStub()
    widget = TerminalConfig(app_config)

    with patch(
        "plutus_terminal.ui.widgets.config.terminal_config.Toast.show_message"
    ) as show_message:
        widget._set_toast_position(widget._toast_position_combobox.findData("bottom_left"))

    assert app_config.get_gui_settings("toast_position") == "bottom_left"
    show_message.assert_called_once()


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

    expected_call_count = 2
    assert controller.app_config.trade_value_lowest == trade_value_lowest
    assert controller.app_config.trade_value_high == trade_value_high
    assert controller.app_config.take_profit == take_profit
    assert controller.app_config.stop_loss == stop_loss
    assert show_message.call_count == expected_call_count


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


def test_rpc_config_add_remove_and_write() -> None:
    """RPCConfig should manage its editable RPC list and persist updates."""
    rpc = SimpleNamespace(
        chain_name="Arbitrum", rpc_urls=orjson.dumps(["https://a"]).decode("utf-8")
    )
    widget = RPCConfig(rpc)
    widget._input_field.setText("https://b")
    widget._add_rpc()
    widget._list.selectionModel().select(
        widget._model.index(0, 0),
        QtCore.QItemSelectionModel.SelectionFlag.Select,
    )

    with patch(
        "plutus_terminal.ui.widgets.config.web3_config.AppConfig.write_model_to_db"
    ) as write_db:
        widget._remove_rpc()
        widget.write_to_db()

    assert widget._model.stringList() == ["https://b"]
    write_db.assert_called_once()


def test_web3_config_saves_all_rpc_widgets() -> None:
    """Web3Config should forward saves to each nested RPC widget."""
    with patch(
        "plutus_terminal.ui.widgets.config.web3_config.AppConfig.get_all_web3_rpc",
        return_value=[
            SimpleNamespace(
                chain_name="Arbitrum", rpc_urls=orjson.dumps(["https://a"]).decode("utf-8")
            )
        ],
    ):
        widget = Web3Config()

    rpc_widget = widget._rpcs_layout.itemAt(0).widget()
    rpc_widget.write_to_db = Mock()
    with patch("plutus_terminal.ui.widgets.config.web3_config.Toast.show_message") as show_message:
        widget._save_rpcs()

    rpc_widget.write_to_db.assert_called_once()
    show_message.assert_called_once()


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

    account_widgets = [
        widget._account_box_layout.itemAt(index).widget()
        for index in range(widget._account_box_layout.count())
        if isinstance(widget._account_box_layout.itemAt(index).widget(), AccountWidget)
    ]

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
            filter_type=FilterType.KEYWORD_MATCHING, action_type=ActionType.COIN_ASSOCIATION
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


def test_news_config_toggles_password_visibility_and_adds_filters() -> None:
    """NewsConfig should expose stored secrets and create new filter rows."""
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
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
            side_effect=KeyringPasswordNotFoundError,
        ),
    ):
        widget = NewsConfig(controller)

    widget._tree_password_button.click()
    widget._add_keyword_filter()
    widget._add_data_filter()

    assert widget._tree_input.echoMode() == QtWidgets.QLineEdit.EchoMode.Normal
    assert widget._keyword_matching_layout.count() > 1
    assert widget._data_matching_layout.count() > 1


def test_news_config_records_updated_news_source_key() -> None:
    """NewsConfig should persist changed API keys and restart the news manager."""
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
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
            side_effect=KeyringPasswordNotFoundError,
        ),
    ):
        widget = NewsConfig(controller)

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


def test_news_config_saves_filters_and_refreshes_manager() -> None:
    """Saving filters should persist all filter rows and refresh the active filter manager."""
    controller = UIControllerStub()
    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.get_all_user_filters",
            return_value=[
                _user_filter(filter_type=FilterType.KEYWORD_MATCHING, action_type=ActionType.IGNORE)
            ],
        ),
        patch(
            "plutus_terminal.ui.widgets.config.news_config.list_resources_from_prefix",
            return_value=["ding.wav"],
        ),
        patch(
            "plutus_terminal.ui.widgets.config.news_config.keyring_manager.get_news_source_api_key",
            side_effect=KeyringPasswordNotFoundError,
        ),
    ):
        widget = NewsConfig(controller)

    with (
        patch(
            "plutus_terminal.ui.widgets.config.news_config.AppConfig.write_model_to_db"
        ) as write_db,
        patch("plutus_terminal.ui.widgets.config.news_config.Toast.show_message") as show_message,
    ):
        widget._save_filters()

    write_db.assert_called()
    assert controller.news_filter_manager.updated is True
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
            return {"secrets": ["Account ID", "API Key", "Secret"]}

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


def test_config_dialog_builds_expected_tabs() -> None:
    """ConfigDialog should render the project configuration sections as tabs."""
    controller = UIControllerStub()

    class _Section(QtWidgets.QWidget):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

    with (
        patch("plutus_terminal.ui.widgets.config.config_dialog.NewsConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.Web3Config", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.AccountConfig", _Section),
        patch("plutus_terminal.ui.widgets.config.config_dialog.TerminalConfig", _Section),
    ):
        dialog = ConfigDialog(controller)

    expected_tab_count = 5

    assert dialog._tab_widget.count() == expected_tab_count
    assert dialog._tab_widget.tabText(0) == "Trade"
    assert dialog._tab_widget.tabText(4) == "Terminal"


def test_user_top_bar_opens_config_dialog() -> None:
    """UserTopBar should expose a configuration button wired to the dialog."""
    config_dialog = SimpleNamespace(show=Mock())

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

    config_dialog.show.assert_called_once()
