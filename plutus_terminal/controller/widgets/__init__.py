"""Widget-specific controllers for UI MVC orchestration."""

from plutus_terminal.controller.widgets.account_info_controller import AccountInfoController
from plutus_terminal.controller.widgets.perps_trade_controller import PerpsTradeController
from plutus_terminal.controller.widgets.trade_table_controller import TradeTableController
from plutus_terminal.controller.widgets.trading_chart_controller import TradingChartController

__all__ = [
    "AccountInfoController",
    "PerpsTradeController",
    "TradeTableController",
    "TradingChartController",
]
