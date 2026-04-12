# ruff: noqa: S101, SLF001

"""Integration coverage for the composed app window."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
import unittest
from unittest.mock import patch

from PySide6 import QtWidgets

from plutus_terminal.core.exchange.orderly.exchange import OrderlyExchange
from plutus_terminal.ui.main_window import PlutusMainWindow
from tests.ui.helpers import (
    AppConfigStub,
    MessageBusStub,
    NewsManagerStub,
    UIControllerStub,
    ensure_app,
)

if TYPE_CHECKING:
    from plutus_terminal.core.config import AppConfig
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.message_bus import MessageBus
    from tests.ui.helpers import ExchangeStub

ensure_app()


class _StubChart(QtWidgets.QWidget):
    """Simple chart replacement for main-window tests."""

    def __init__(self, _ui_controller: object) -> None:
        super().__init__()


class _StubConfigDialog(QtWidgets.QDialog):
    """Simple config-dialog replacement for main-window tests."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        super().__init__()

    def open_dialog(self) -> None:
        """Match the production dialog API used by the top bar."""


class MainWindowIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Cover the composed app window and the opt-in live Orderly flow."""

    async def test_main_window_initializes_composed_widgets(self) -> None:
        """Main window should wire its core panes together during async init."""
        controller = UIControllerStub()
        with (
            patch("plutus_terminal.ui.main_window.TradingChart", _StubChart),
            patch("plutus_terminal.ui.main_window.ConfigDialog", _StubConfigDialog),
        ):
            window = PlutusMainWindow(cast("UIController", controller))
            await window.init_async()

        assert window.centralWidget() is window.main_widget
        assert window._news_list is not None
        assert window._perps_trade is not None
        assert window._trade_table is not None

    async def test_orderly_testnet_main_window_integration(self) -> None:
        """Opt-in live integration should initialize the main window with an Orderly testnet account."""
        account_id = os.getenv("PLUTUS_TEST_ORDERLY_ACCOUNT_ID")
        api_key = os.getenv("PLUTUS_TEST_ORDERLY_API_KEY")
        secret = os.getenv("PLUTUS_TEST_ORDERLY_SECRET")
        if not all((account_id, api_key, secret)):
            self.skipTest(
                "Set PLUTUS_TEST_ORDERLY_ACCOUNT_ID/API_KEY/SECRET to run live UI integration"
            )

        app_config = AppConfigStub()
        app_config.current_keyring_account = SimpleNamespace(
            id=1,
            username=os.getenv("PLUTUS_TEST_ORDERLY_USERNAME", "orderly_testnet"),
            exchange_name="orderly",
            exchange_type=0,
        )
        message_bus = MessageBusStub()
        secrets = [account_id, api_key, secret, "testnet"]

        with (
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.keyring_manager.get_exchange_password",
                return_value=secrets,
            ),
            patch("plutus_terminal.ui.main_window.TradingChart", _StubChart),
            patch("plutus_terminal.ui.main_window.ConfigDialog", _StubConfigDialog),
        ):
            exchange = await OrderlyExchange.create(
                cast("MessageBus", message_bus),
                cast("PasswordGuard", SimpleNamespace()),
                cast("AppConfig", app_config),
            )
            controller = UIControllerStub(
                exchange=cast("ExchangeStub", exchange),
                app_config=app_config,
                message_bus=message_bus,
            )
            controller.news_manager = NewsManagerStub([])
            controller.current_pair = exchange.default_pair
            window = PlutusMainWindow(cast("UIController", controller))
            try:
                await window.init_async()
                assert exchange.account_info["Network"] == "testnet"
                assert window._perps_trade._pair_combo_box.count() > 0
                assert "USD" in window._account_info._balance_value.text()
            finally:
                await exchange.stop_async()
