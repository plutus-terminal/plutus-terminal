# ruff: noqa: S101, PT009, PT027, PLR2004, SLF001

"""Focused parity tests for Orderly exchange orchestration behavior."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from httpx import HTTPStatusError, Request, Response, TimeoutException

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.orderly.exchange import OrderlyExchange
from plutus_terminal.core.exchange.orderly.models import OrderlyNetwork
from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRequestError
from plutus_terminal.core.types_ import MessageLevel, PerpsTradeDirection, PerpsTradeType


def _build_message_bus() -> SimpleNamespace:
    return SimpleNamespace(
        send_message=SimpleNamespace(emit=Mock()),
        orders_fetched=SimpleNamespace(emit=Mock(), connect=Mock()),
        positions_fetched=SimpleNamespace(emit=Mock(), connect=Mock()),
        balance_fetched=SimpleNamespace(emit=Mock()),
        subscribed_prices_fetched=SimpleNamespace(emit=Mock()),
    )


def _build_app_config() -> SimpleNamespace:
    return SimpleNamespace(
        current_keyring_account=SimpleNamespace(username="orderly-user"),
        leverage=5,
        take_profit=0,
        stop_loss=0,
    )


def _build_market_registry(
    *,
    min_notional: Decimal = Decimal("1"),
    max_leverage: int = 20,
) -> SimpleNamespace:
    market_rule = SimpleNamespace(min_notional=min_notional, max_leverage=max_leverage)
    return SimpleNamespace(
        pairs={"Crypto.BTC/USDC"},
        get_symbol_for_pair=Mock(return_value="PERP_BTC_USDC"),
        get_rule_by_pair=Mock(return_value=market_rule),
    )


def _build_exchange(
    *,
    message_bus: SimpleNamespace | None = None,
    app_config: SimpleNamespace | None = None,
    market_registry: SimpleNamespace | None = None,
    trader: SimpleNamespace | None = None,
    fetcher: SimpleNamespace | None = None,
    max_leverage: int = 50,
) -> OrderlyExchange:
    exchange = OrderlyExchange.__new__(OrderlyExchange)
    exchange.message_bus = message_bus or _build_message_bus()
    exchange._pass_guard = object()
    exchange.app_config = app_config or _build_app_config()
    exchange._market_registry = market_registry or _build_market_registry()
    exchange._trader = trader or SimpleNamespace(
        create_order=AsyncMock(),
        edit_order=AsyncMock(),
        cancel_order=AsyncMock(),
        close_position=AsyncMock(),
        set_leverage=AsyncMock(),
    )
    exchange._fetcher = fetcher or SimpleNamespace(
        start=AsyncMock(),
        _refresh_balance=AsyncMock(),
        fetch_all_orders=AsyncMock(),
        fetch_all_positions=AsyncMock(),
        fetch_current_price=AsyncMock(return_value={"price": Decimal("97500.5")}),
        _cached_orders=[{"id": "order-1"}],
        _cached_positions=[{"id": 7}],
        _cached_prices={},
        _balance_with_unsettled_pnl=Mock(return_value=Decimal("100")),
    )
    exchange._max_leverage = max_leverage
    exchange._credentials = SimpleNamespace(account_id="acct-12345678")
    exchange._network = OrderlyNetwork.MAINNET
    exchange._endpoints = SimpleNamespace(rest_url="https://example.invalid")
    exchange._pair_prefix = "Crypto."
    exchange._pair_separator = "/"
    exchange._pair_suffix = ""
    exchange._quote_symbol = "USDC"
    exchange._async_tasks = []
    exchange._watched_positions = []
    return exchange


def _market_bootstrap_http_error(status_code: int) -> HTTPStatusError:
    request = Request("GET", "https://example.invalid/v1/public/info")
    response = Response(status_code, request=request)
    return HTTPStatusError(f"status {status_code}", request=request, response=response)


class OrderlyExchangeParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify Orderly exchange orchestration keeps stable user-facing behavior."""

    def test_validate_secrets_accepts_webui_token_fields_and_optional_testnet(self) -> None:
        """Accept the intentional API-token auth model used by the terminal."""
        # Arrange
        secrets = ["account-id", "webui-token", "secret", "testnet"]

        # Act
        is_valid, message = OrderlyExchange.validate_secrets(secrets)

        # Assert
        assert is_valid is True
        assert message == "Valid orderly credentials."

    def test_validate_secrets_rejects_unknown_network_values(self) -> None:
        """Reject invalid network values while keeping the auth model unchanged."""
        # Arrange
        secrets = ["account-id", "webui-token", "secret", "staging"]

        # Act
        is_valid, message = OrderlyExchange.validate_secrets(secrets)

        # Assert
        assert is_valid is False
        assert message == "Network must be 'mainnet' or 'testnet'."

    def test_constructor_normalizes_webui_token_key_and_reads_testnet_from_keyring(self) -> None:
        """Normalize stored API keys without changing the WebUI-token auth workflow."""
        # Arrange
        app_config = _build_app_config()
        message_bus = _build_message_bus()
        secrets = ["account-id", "webui-token", "secret", "testnet"]

        # Act
        with patch(
            "plutus_terminal.core.exchange.orderly.exchange.keyring_manager.get_exchange_password",
            return_value=secrets,
        ):
            exchange = OrderlyExchange(message_bus, object(), app_config)

        # Assert
        expected_secret = "sec" + "ret"
        assert exchange._credentials.account_id == "account-id"
        assert exchange._credentials.orderly_key == "ed25519:webui-token"
        assert exchange._credentials.orderly_secret == expected_secret
        assert exchange._network is OrderlyNetwork.TESTNET

    async def test_init_async_uses_fallback_market_symbols_when_bootstrap_times_out(self) -> None:
        """Keep exchange startup stable when the market bootstrap endpoint is unavailable."""
        # Arrange
        exchange = _build_exchange()
        market_registry = SimpleNamespace(load_fallback_symbols=Mock(), pairs=set())
        public_rest_client = SimpleNamespace()
        private_rest_client = SimpleNamespace()
        fetcher = SimpleNamespace()
        trader = SimpleNamespace()
        ws_manager = SimpleNamespace()

        # Act
        with (
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyRestClient",
                side_effect=[public_rest_client, private_rest_client],
            ) as rest_client_cls,
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyMarketRegistry",
                return_value=market_registry,
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyFetcher",
                return_value=fetcher,
            ) as fetcher_cls,
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyTrader",
                return_value=trader,
            ) as trader_cls,
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyWebsocketManager",
                return_value=ws_manager,
            ) as ws_cls,
            patch.object(
                exchange,
                "_refresh_market_registry_with_retry",
                AsyncMock(side_effect=TimeoutException("bootstrap timeout")),
            ),
            patch.object(exchange, "_fetch_max_leverage", AsyncMock(return_value=33)),
        ):
            await exchange.init_async()

        # Assert
        assert rest_client_cls.call_count == 2
        market_registry.load_fallback_symbols.assert_called_once()
        fetcher_cls.assert_called_once_with(
            rest_client=private_rest_client,
            websocket_manager=ws_manager,
            market_registry=market_registry,
            message_bus=exchange.message_bus,
        )
        trader_cls.assert_called_once_with(private_rest_client, market_registry)
        ws_cls.assert_called_once_with(exchange._endpoints, exchange._credentials)
        assert exchange._fetcher is fetcher
        assert exchange._trader is trader
        assert exchange._max_leverage == 33

    async def test_init_async_uses_fallback_market_symbols_for_http_failures(self) -> None:
        """Use fallback symbols when bootstrap fails with retried HTTP status errors."""
        # Arrange
        exchange = _build_exchange()
        market_registry = SimpleNamespace(load_fallback_symbols=Mock(), pairs=set())

        # Act
        with (
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyRestClient",
                side_effect=[SimpleNamespace(), SimpleNamespace()],
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyMarketRegistry",
                return_value=market_registry,
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyFetcher",
                return_value=SimpleNamespace(),
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyTrader",
                return_value=SimpleNamespace(),
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyWebsocketManager",
                return_value=SimpleNamespace(),
            ),
            patch.object(
                exchange,
                "_refresh_market_registry_with_retry",
                AsyncMock(side_effect=_market_bootstrap_http_error(503)),
            ),
            patch.object(exchange, "_fetch_max_leverage", AsyncMock(return_value=33)),
        ):
            await exchange.init_async()

        # Assert
        market_registry.load_fallback_symbols.assert_called_once()

    async def test_init_async_uses_fallback_market_symbols_for_api_failures(self) -> None:
        """Use fallback symbols when bootstrap fails with Orderly API-level errors."""
        # Arrange
        exchange = _build_exchange()
        market_registry = SimpleNamespace(load_fallback_symbols=Mock(), pairs=set())

        # Act
        with (
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyRestClient",
                side_effect=[SimpleNamespace(), SimpleNamespace()],
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyMarketRegistry",
                return_value=market_registry,
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyFetcher",
                return_value=SimpleNamespace(),
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyTrader",
                return_value=SimpleNamespace(),
            ),
            patch(
                "plutus_terminal.core.exchange.orderly.exchange.OrderlyWebsocketManager",
                return_value=SimpleNamespace(),
            ),
            patch.object(
                exchange,
                "_refresh_market_registry_with_retry",
                AsyncMock(side_effect=OrderlyRequestError("gateway rejected request")),
            ),
            patch.object(exchange, "_fetch_max_leverage", AsyncMock(return_value=33)),
        ):
            await exchange.init_async()

        # Assert
        market_registry.load_fallback_symbols.assert_called_once()

    async def test_set_leverage_clamps_to_pair_maximum_and_updates_config(self) -> None:
        """Clamp leverage to the effective pair limit before sending the request."""
        # Arrange
        app_config = _build_app_config()
        trader = SimpleNamespace(set_leverage=AsyncMock())
        exchange = _build_exchange(app_config=app_config, trader=trader)

        # Act
        await exchange.set_leverage("BTC", 100)

        # Assert
        trader.set_leverage.assert_awaited_once_with("PERP_BTC_USDC", 20)
        assert app_config.leverage == 20

    async def test_set_leverage_keeps_existing_config_when_the_request_fails(self) -> None:
        """Do not mutate local leverage config when Orderly rejects the update."""
        # Arrange
        app_config = _build_app_config()
        trader = SimpleNamespace(
            set_leverage=AsyncMock(side_effect=TransactionFailedError("[429] too many requests")),
        )
        exchange = _build_exchange(app_config=app_config, trader=trader)

        # Act / Assert
        with self.assertRaisesRegex(TransactionFailedError, "too many requests"):
            await exchange.set_leverage("BTC", 100)

        assert app_config.leverage == 5

    async def test_create_order_refreshes_orders_positions_and_emits_info_message(self) -> None:
        """Refresh caches after successful order creation and notify the user."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(create_order=AsyncMock(return_value={"order_id": "abc"}))
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(),
            fetch_all_positions=AsyncMock(),
            fetch_current_price=AsyncMock(return_value={"price": Decimal("97500.5")}),
            _cached_orders=[{"id": "abc"}],
            _cached_positions=[{"id": 1}],
            _cached_prices={},
            _balance_with_unsettled_pnl=Mock(return_value=Decimal("100")),
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)

        # Act
        await exchange.create_order(
            pair="Crypto.BTC/USDC",
            amount=Decimal("10"),
            trade_direction=PerpsTradeDirection.LONG,
            trade_type=PerpsTradeType.LIMIT,
            execution_price=Decimal("97500.5"),
        )

        # Assert
        trader.create_order.assert_awaited_once()
        trade_arguments = trader.create_order.await_args.args[0]
        assert trade_arguments["symbol"] == "PERP_BTC_USDC"
        assert trade_arguments["size_stable"] == Decimal("50")
        fetcher.fetch_all_orders.assert_awaited_once()
        fetcher.fetch_all_positions.assert_awaited_once()
        message = message_bus.send_message.emit.call_args.args[0]
        assert message.level is MessageLevel.INFO
        assert message.text == "Creating LIMIT order for Crypto.BTC/USDC"
        message_bus.orders_fetched.emit.assert_called_once_with(fetcher._cached_orders)
        message_bus.positions_fetched.emit.assert_called_once_with(fetcher._cached_positions)

    async def test_create_order_does_not_apply_min_notional_before_leverage(self) -> None:
        """Defer Orderly notional validation until the final leveraged payload is built."""
        # Arrange
        market_registry = _build_market_registry(min_notional=Decimal("25"))
        trader = SimpleNamespace(create_order=AsyncMock(return_value={"order_id": "abc"}))
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(),
            fetch_all_positions=AsyncMock(),
            fetch_current_price=AsyncMock(return_value={"price": Decimal("97500.5")}),
            _cached_orders=[{"id": "abc"}],
            _cached_positions=[{"id": 1}],
            _cached_prices={},
            _balance_with_unsettled_pnl=Mock(return_value=Decimal("100")),
        )
        exchange = _build_exchange(market_registry=market_registry, trader=trader)
        exchange._fetcher = fetcher

        # Act
        await exchange.create_order(
            pair="Crypto.BTC/USDC",
            amount=Decimal("10"),
            trade_direction=PerpsTradeDirection.LONG,
            trade_type=PerpsTradeType.LIMIT,
            execution_price=Decimal("97500.5"),
        )

        # Assert
        trader.create_order.assert_awaited_once()
        trade_arguments = trader.create_order.await_args.args[0]
        assert trade_arguments["size_stable"] == Decimal("50")

    async def test_create_order_surfaces_auth_context_in_user_message_and_skips_refresh(
        self,
    ) -> None:
        """Keep actionable auth failures visible to the caller-facing message bus."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(
            create_order=AsyncMock(side_effect=TransactionFailedError("[401] invalid api key")),
        )
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(),
            fetch_all_positions=AsyncMock(),
            fetch_current_price=AsyncMock(return_value={"price": Decimal("97500.5")}),
            _cached_orders=[],
            _cached_positions=[],
            _cached_prices={},
            _balance_with_unsettled_pnl=Mock(return_value=Decimal("100")),
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)

        # Act
        await exchange.create_order(
            pair="Crypto.BTC/USDC",
            amount=Decimal("10"),
            trade_direction=PerpsTradeDirection.LONG,
            trade_type=PerpsTradeType.LIMIT,
            execution_price=Decimal("97500.5"),
        )

        # Assert
        message = message_bus.send_message.emit.call_args.args[0]
        assert message.level is MessageLevel.ERROR
        assert message.text == "Failed to create order: [401] invalid api key"
        fetcher.fetch_all_orders.assert_not_awaited()
        fetcher.fetch_all_positions.assert_not_awaited()
        message_bus.orders_fetched.emit.assert_not_called()
        message_bus.positions_fetched.emit.assert_not_called()

    async def test_create_order_warns_when_primary_succeeds_but_tp_sl_attach_fails(self) -> None:
        """Report partial success without surfacing the entry as a full failure."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(
            create_order=AsyncMock(
                return_value={
                    "primary": {"order_id": "abc"},
                    "tp_sl": None,
                    "partial_success": True,
                    "tp_sl_error": "[429] too many requests",
                },
            ),
        )
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(),
            fetch_all_positions=AsyncMock(),
            fetch_current_price=AsyncMock(return_value={"price": Decimal("97500.5")}),
            _cached_orders=[{"id": "abc"}],
            _cached_positions=[{"id": 1}],
            _cached_prices={},
            _balance_with_unsettled_pnl=Mock(return_value=Decimal("100")),
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)

        # Act
        await exchange.create_order(
            pair="Crypto.BTC/USDC",
            amount=Decimal("10"),
            trade_direction=PerpsTradeDirection.LONG,
            trade_type=PerpsTradeType.LIMIT,
            execution_price=Decimal("97500.5"),
        )

        # Assert
        message = message_bus.send_message.emit.call_args.args[0]
        assert message.level is MessageLevel.WARNING
        assert message.text == (
            "Created LIMIT order for Crypto.BTC/USDC, but failed to attach TP/SL: "
            "[429] too many requests"
        )
        fetcher.fetch_all_orders.assert_awaited_once()
        fetcher.fetch_all_positions.assert_awaited_once()

    async def test_create_order_warns_when_refresh_fails_after_successful_submission(self) -> None:
        """Preserve a successful order submission even if the follow-up refresh crashes."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(create_order=AsyncMock(return_value={"success": True}))
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(side_effect=RuntimeError("refresh exploded")),
            fetch_all_positions=AsyncMock(),
            fetch_current_price=AsyncMock(return_value={"price": Decimal("97500.5")}),
            _cached_orders=[],
            _cached_positions=[],
            _cached_prices={},
            _balance_with_unsettled_pnl=Mock(return_value=Decimal("100")),
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)

        # Act
        await exchange.create_order(
            pair="Crypto.BTC/USDC",
            amount=Decimal("10"),
            trade_direction=PerpsTradeDirection.LONG,
            trade_type=PerpsTradeType.LIMIT,
            execution_price=Decimal("97500.5"),
        )

        # Assert
        assert message_bus.send_message.emit.call_count == 2
        refresh_message = message_bus.send_message.emit.call_args_list[-1].args[0]
        assert refresh_message.level is MessageLevel.WARNING
        assert "failed to refresh Orderly data" in refresh_message.text
        message_bus.orders_fetched.emit.assert_not_called()

    async def test_cancel_order_warns_when_refresh_fails_after_successful_cancel(self) -> None:
        """Preserve successful cancels even if the order refresh fails afterward."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(cancel_order=AsyncMock(return_value={"success": True}))
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(side_effect=RuntimeError("cancel refresh exploded")),
            _cached_orders=[],
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)
        order_data = {
            "id": "ui-fallback-id",
            "pair": "Crypto.BTC/USDC",
            "trigger_price": Decimal("97500.5"),
            "size_stable": Decimal("50"),
            "trade_direction": PerpsTradeDirection.LONG,
            "order_type": PerpsTradeType.LIMIT,
            "reduce_only": False,
            "extra": {"symbol": "PERP_BTC_USDC", "native_order_id": "70001"},
        }

        # Act
        await exchange.cancel_order(order_data)

        # Assert
        trader.cancel_order.assert_awaited_once_with(
            {"order_id": "70001", "symbol": "PERP_BTC_USDC", "trade_type": PerpsTradeType.LIMIT},
        )
        assert message_bus.send_message.emit.call_count == 1
        refresh_message = message_bus.send_message.emit.call_args.args[0]
        assert refresh_message.level is MessageLevel.WARNING
        assert "failed to refresh Orderly data" in refresh_message.text
        message_bus.orders_fetched.emit.assert_not_called()

    async def test_edit_order_refreshes_open_orders_after_successful_native_edit(self) -> None:
        """Refresh open orders after Orderly accepts a native edit request."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(edit_order=AsyncMock(return_value={"success": True}))
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(),
            _cached_orders=[{"id": "edit-1"}],
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)
        order_data = {
            "id": "edit-1",
            "pair": "Crypto.BTC/USDC",
            "trade_direction": PerpsTradeDirection.LONG,
            "order_type": PerpsTradeType.LIMIT,
            "reduce_only": False,
            "extra": {},
        }

        # Act
        await exchange.edit_order(order_data, Decimal("50"), Decimal("98000"))

        # Assert
        trader.edit_order.assert_awaited_once()
        trade_arguments = trader.edit_order.await_args.args[0]
        assert trade_arguments["symbol"] == "PERP_BTC_USDC"
        assert trade_arguments["size_stable"] == Decimal("50")
        assert trade_arguments["price"] == Decimal("98000")
        fetcher.fetch_all_orders.assert_awaited_once()
        message_bus.orders_fetched.emit.assert_called_once_with(fetcher._cached_orders)

    async def test_edit_order_builds_root_tp_sl_edit_with_sibling_targets(self) -> None:
        """Edit TP/SL orders through the root algo order while preserving sibling triggers."""
        # Arrange
        trader = SimpleNamespace(edit_order=AsyncMock(return_value={"success": True}))
        fetcher = SimpleNamespace(
            fetch_all_orders=AsyncMock(),
            _cached_orders=[
                {
                    "id": "tp-child",
                    "pair": "Crypto.BTC/USDC",
                    "trade_direction": PerpsTradeDirection.LONG,
                    "order_type": PerpsTradeType.TRIGGER_TP,
                    "trigger_price": Decimal("99000"),
                    "size_stable": Decimal("50"),
                    "reduce_only": True,
                    "extra": {"root_algo_order_id": "root-1", "symbol": "PERP_BTC_USDC"},
                },
                {
                    "id": "sl-child",
                    "pair": "Crypto.BTC/USDC",
                    "trade_direction": PerpsTradeDirection.LONG,
                    "order_type": PerpsTradeType.TRIGGER_SL,
                    "trigger_price": Decimal("94000"),
                    "size_stable": Decimal("50"),
                    "reduce_only": True,
                    "extra": {"root_algo_order_id": "root-1", "symbol": "PERP_BTC_USDC"},
                },
            ],
        )
        exchange = _build_exchange(trader=trader, fetcher=fetcher)
        order_data = fetcher._cached_orders[0]

        # Act
        await exchange.edit_order(order_data, Decimal("50"), Decimal("99500"))

        # Assert
        trader.edit_order.assert_awaited_once()
        trade_arguments = trader.edit_order.await_args.args[0]
        assert trade_arguments["order_id"] == "root-1"
        assert trade_arguments["take_profit"] == Decimal("99500")
        assert trade_arguments["stop_loss"] == Decimal("94000")

    async def test_edit_order_surfaces_rate_limit_context_in_user_message(self) -> None:
        """Report rate-limit failures without emitting stale refreshed order state."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(
            edit_order=AsyncMock(side_effect=TransactionFailedError("[429] too many requests")),
        )
        fetcher = SimpleNamespace(fetch_all_orders=AsyncMock(), _cached_orders=[])
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)
        order_data = {
            "id": "edit-1",
            "pair": "Crypto.BTC/USDC",
            "trade_direction": PerpsTradeDirection.LONG,
            "order_type": PerpsTradeType.LIMIT,
            "reduce_only": False,
            "extra": {},
        }

        # Act
        await exchange.edit_order(order_data, Decimal("50"), Decimal("98000"))

        # Assert
        message = message_bus.send_message.emit.call_args.args[0]
        assert message.level is MessageLevel.ERROR
        assert message.text == "Failed to edit order: [429] too many requests"
        fetcher.fetch_all_orders.assert_not_awaited()
        message_bus.orders_fetched.emit.assert_not_called()

    async def test_close_position_preserves_native_base_size_and_refreshes_positions(self) -> None:
        """Forward native base size when closing positions and refresh resulting state."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(close_position=AsyncMock(return_value={"success": True}))
        fetcher = SimpleNamespace(
            _refresh_balance=AsyncMock(),
            fetch_all_positions=AsyncMock(),
            _cached_positions=[{"id": 99}],
        )
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)
        position = {
            "pair": "Crypto.BTC/USDC",
            "open_price": Decimal("97500.5"),
            "position_size_stable": Decimal("100"),
            "trade_direction": PerpsTradeDirection.LONG,
            "extra": {"base_size": "0.00102564"},
        }

        # Act
        await exchange.close_position(position)

        # Assert
        trader.close_position.assert_awaited_once()
        trade_arguments = trader.close_position.await_args.args[0]
        assert trade_arguments["symbol"] == "PERP_BTC_USDC"
        assert trade_arguments["trade_type"] is PerpsTradeType.MARKET
        assert trade_arguments["base_size"] == "0.00102564"
        fetcher._refresh_balance.assert_awaited_once()
        fetcher.fetch_all_positions.assert_awaited_once()
        message_bus.positions_fetched.emit.assert_called_once_with(fetcher._cached_positions)

    async def test_close_position_surfaces_temporary_server_failure_in_user_message(self) -> None:
        """Map temporary server failures to stable user-visible error messaging."""
        # Arrange
        message_bus = _build_message_bus()
        trader = SimpleNamespace(
            close_position=AsyncMock(
                side_effect=TransactionFailedError("[500] temporary server failure")
            ),
        )
        fetcher = SimpleNamespace(fetch_all_positions=AsyncMock(), _cached_positions=[])
        exchange = _build_exchange(message_bus=message_bus, trader=trader, fetcher=fetcher)
        position = {
            "pair": "Crypto.BTC/USDC",
            "open_price": Decimal("97500.5"),
            "position_size_stable": Decimal("100"),
            "trade_direction": PerpsTradeDirection.LONG,
            "extra": {},
        }

        # Act
        await exchange.close_position(position)

        # Assert
        message = message_bus.send_message.emit.call_args.args[0]
        assert message.level is MessageLevel.ERROR
        assert message.text == "Failed to close position: [500] temporary server failure"
        fetcher.fetch_all_positions.assert_not_awaited()
        message_bus.positions_fetched.emit.assert_not_called()

    def test_calculate_pnl_uses_unrealized_base_and_fee_adjusted_close_now_value(self) -> None:
        """Show unrealized PnL in the tooltip and derive close-now value after explicit fees."""
        # Arrange
        fetcher = SimpleNamespace(
            fetch_opening_fee=Mock(return_value=Decimal("0.582")),
            fetch_funding_fee=Mock(return_value=Decimal("0.75")),
            calculate_sdk_unsettled_pnl=Mock(return_value=Decimal("3.673")),
            calculate_close_fee=Mock(return_value=Decimal("0.61")),
            calculate_unrealized_pnl=Mock(return_value=Decimal("5.005")),
        )
        exchange = _build_exchange(fetcher=fetcher)
        position = {
            "pair": "Crypto.BTC/USDC",
            "id": 77,
            "position_size_stable": Decimal("970"),
            "collateral_stable": Decimal("97"),
            "open_price": Decimal("97000"),
            "trade_direction": PerpsTradeDirection.LONG,
            "leverage": Decimal("10"),
            "liquidation_price": Decimal("87456.12"),
            "extra": {"unsettled_pnl": "4.255"},
        }

        # Act
        pnl_details = exchange.calculate_pnl(position, None)

        # Assert
        assert pnl_details["pnl_usd_before_fees"] == Decimal("5.005")
        assert pnl_details["funding_fee_usd"] == Decimal("0.75")
        assert pnl_details["opening_fee_usd"] == Decimal("0.582")
        assert pnl_details["closing_fee_usd"] == Decimal("0.61")
        assert pnl_details["pnl_usd_after_fees"] == Decimal("3.063")
        assert pnl_details["pnl_label"] == "Unrealized PnL"
        assert pnl_details["net_pnl_label"] == "Close-now PnL"
        assert pnl_details["show_closing_fee"] is True
        assert "funding_fee_included_in_pnl" not in pnl_details
        assert "opening_fee_included_in_pnl" not in pnl_details

    def test_account_info_exposes_free_and_unsettled_adjusted_balances(self) -> None:
        """Expose the balance breakdown needed by the trading UI."""
        # Arrange
        fetcher = SimpleNamespace(
            available_balance=Mock(return_value=Decimal("100")),
            available_balance_with_unsettled_pnl=Mock(return_value=Decimal("112.5")),
            unsettled_pnl_total=Mock(return_value=Decimal("12.5")),
            trading_balance=Mock(return_value=Decimal("87.5")),
        )
        exchange = _build_exchange(fetcher=fetcher)

        # Act
        account_info = exchange.account_info

        # Assert
        assert account_info["Free Balance"] == Decimal("87.5")
        assert account_info["Available Balance"] == Decimal("100")
        assert account_info["Available Balance + Unsettled PnL"] == Decimal("112.5")
        assert account_info["Unsettled PnL"] == Decimal("12.5")
