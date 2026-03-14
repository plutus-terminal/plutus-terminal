# ruff: noqa: S101, SLF001

"""Focused regression tests for UI pair selection flows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar, cast
import unittest

from PySide6 import QtCore, QtWidgets

from plutus_terminal.controller.ui_controller import UIController
from plutus_terminal.ui.widgets.news_widget import NewsWidget

if TYPE_CHECKING:
    from plutus_terminal.core.news.types import NewsData


class _MessageBus(QtCore.QObject):
    """Minimal signal-only message bus for controller tests."""

    send_message = QtCore.Signal(object)


class _FetcherStub:
    """Track subscribe and unsubscribe calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def subscribe_to_price(self, pair: str) -> None:
        """Record subscription requests."""
        self.calls.append(("subscribe", pair))

    async def unsubscribe_to_price(self, pair: str) -> None:
        """Record unsubscription requests."""
        self.calls.append(("unsubscribe", pair))


class _ExchangeStub:
    """Minimal exchange surface used by pair-change tests."""

    def __init__(self) -> None:
        self.available_pairs = {"Crypto.BTC/USDC", "Crypto.ETH/USDC"}
        self.default_pair = "Crypto.BTC/USDC"
        self.fetcher = _FetcherStub()


class _AppConfigStub(QtCore.QObject):
    """Expose the few config values NewsWidget needs."""

    def __init__(self) -> None:
        super().__init__()
        self.trade_value_lowest = 10
        self.trade_value_low = 25
        self.trade_value_medium = 50
        self.trade_value_high = 100


def _build_news_data() -> NewsData:
    """Create minimal news payload for widget tests."""
    return {
        "news_id": "news-1",
        "title": "BTC moves",
        "link": cast("Any", QtCore.QUrl("https://example.com")),
        "body": "",
        "image": "",
        "is_quote": False,
        "quote_message": "",
        "quote_user": "",
        "quote_image": "",
        "is_reply": False,
        "is_self_reply": False,
        "reply_user": "",
        "reply_message": "",
        "reply_image": "",
        "is_retweet": False,
        "retweet_user": "",
        "icon": "",
        "source": "webs",
        "time": datetime.now(timezone.utc),
        "coin": set(),
        "feed": "Feed",
        "sfx": ":/sfx/test",
        "is_update": False,
        "update_type": "",
        "applied_updates": set(),
        "summary_title": "",
        "summary_body": "",
        "is_important": False,
        "ignored": False,
    }


class UIControllerPairSelectionTests(unittest.IsolatedAsyncioTestCase):
    """Verify controller pair changes keep subscription counts balanced."""

    def setUp(self) -> None:
        """Create a controller with a stubbed exchange."""
        self.controller = UIController(
            cast("Any", _MessageBus()),
            cast("Any", object()),
            cast("Any", object()),
            cast("Any", object()),
        )
        self.exchange = _ExchangeStub()
        self.controller.current_exchange = cast("Any", self.exchange)
        self.controller.current_pair = "Crypto.BTC/USDC"

    async def test_change_current_pair_subscribes_initial_current_pair_once(self) -> None:
        """Allow initial same-pair setup without duplicating later subscriptions."""
        seen_pairs: list[str] = []
        self.controller.pair_changed.connect(seen_pairs.append)

        await self.controller.change_current_pair("Crypto.BTC/USDC")
        await self.controller.change_current_pair("Crypto.BTC/USDC")

        assert self.exchange.fetcher.calls == [("subscribe", "Crypto.BTC/USDC")]
        assert seen_pairs == ["Crypto.BTC/USDC"]

    async def test_change_current_pair_switches_and_unsubscribes_previous_pair(self) -> None:
        """Move the controller subscription to the next pair exactly once."""
        self.controller._is_current_pair_subscribed = True

        await self.controller.change_current_pair("Crypto.ETH/USDC")

        assert self.exchange.fetcher.calls == [
            ("subscribe", "Crypto.ETH/USDC"),
            ("unsubscribe", "Crypto.BTC/USDC"),
        ]
        assert self.controller.current_pair == "Crypto.ETH/USDC"


class NewsWidgetPairSelectionTests(unittest.TestCase):
    """Verify pair-interaction clicks stay separate from news selection."""

    _app: ClassVar[QtWidgets.QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        """Ensure one QApplication exists for widget tests."""
        cls._app = cast(
            "QtWidgets.QApplication",
            QtWidgets.QApplication.instance() or QtWidgets.QApplication([]),
        )

    def test_pair_interaction_detection_ignores_clicks_inside_pair_region(self) -> None:
        """Treat descendants of the pair interaction group as non-selecting clicks."""
        widget = NewsWidget(
            news_data=_build_news_data(),
            format_to_pair=lambda coin: f"Crypto.{coin}/USDC",
            available_pairs={"Crypto.BTC/USDC"},
            display_delay=False,
            app_config=cast("Any", _AppConfigStub()),
        )
        pair_group = QtWidgets.QGroupBox(widget)
        pair_group.setProperty("news_pair_interaction", True)
        pair_button = QtWidgets.QPushButton(pair_group)

        assert widget._is_pair_interaction_target(pair_button) is True
        assert widget._is_pair_interaction_target(widget.title_label) is False
