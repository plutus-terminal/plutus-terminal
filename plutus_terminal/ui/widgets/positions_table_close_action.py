"""Close action menu used by the positions table actions cell."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QWidget,
    QWidgetAction,
)

from plutus_terminal.core.exchange.types import PerpsPosition, PerpsTradeType
from plutus_terminal.ui.widgets.decimal_spin_box import DecimalSpinBox


class PositionCloseAction(QWidgetAction):
    """Widget action used to reduce or close a position."""

    reduce_clicked = Signal(dict)
    set_price_clicked = Signal()

    def __init__(self, position: PerpsPosition, parent: Optional[QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)  # type: ignore[arg-type]
        self._position = position

        self._default_widget = QWidget(parent)
        self._main_layout = QGridLayout()
        self.type_group = QButtonGroup()
        self.market_button = QRadioButton("Market")
        self.limit_button = QRadioButton("Limit")
        self.type_group_layout = QHBoxLayout()

        self._amount_label = QLabel("Amount:")
        self._amount_box = DecimalSpinBox()
        self._amount_group = QButtonGroup()
        self._amount_group_layout = QHBoxLayout()
        for value in ("25%", "50%", "75%", "100%"):
            button = QRadioButton(value)
            self._amount_group.addButton(button)
            self._amount_group.setId(button, int(value[:-1]))
            self._amount_group_layout.addWidget(button)
        self._amount_group.buttonClicked.connect(self._set_amount_from_button)

        self._price_label = QLabel("Price:")
        self._price_box = DecimalSpinBox()
        self._price_box.setDecimals(8)
        self._price_refresh_button = QPushButton()
        self._close_button = QPushButton("Close Trade")
        self._close_button.setProperty("class", "gray")
        self._close_button.setMinimumSize(50, 30)

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.type_group.addButton(self.limit_button)
        self.type_group.addButton(self.market_button)
        self.type_group_layout.addWidget(self.market_button)
        self.type_group_layout.addWidget(self.limit_button)
        self.type_group.buttonClicked.connect(self._type_change)
        self.market_button.click()

        self._amount_box.setDecimals(8)
        self._amount_box.decimalValueChanged.connect(self._update_amount_buttons)
        self._amount_box.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._price_box.setRange(Decimal(0), Decimal(100_000_000))
        self._price_box.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._price_refresh_button.setProperty("class", "borderless")
        self._price_refresh_button.setIcon(QIcon(":/icons/focus_icon"))
        self._price_refresh_button.setFixedWidth(25)
        self._price_refresh_button.clicked.connect(self.set_price_clicked.emit)

        self._close_button.clicked.connect(self._reduce_position)
        self.set_position(self._position)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addLayout(self.type_group_layout, 0, 0, 1, 3)
        self._main_layout.addWidget(self._amount_label, 1, 0)
        self._main_layout.addWidget(self._amount_box, 1, 1, 1, 2)
        self._main_layout.addLayout(self._amount_group_layout, 2, 0, 1, 3)
        self._main_layout.addWidget(self._price_label, 3, 0)
        self._main_layout.addWidget(self._price_box, 3, 1)
        self._main_layout.addWidget(self._price_refresh_button, 3, 2)
        self._main_layout.addWidget(self._close_button, 4, 0, 1, 3)

        self._default_widget.setLayout(self._main_layout)
        self.setDefaultWidget(self._default_widget)

    def set_position(self, position: PerpsPosition) -> None:
        """Update the action to target a different position."""
        self._position = position
        self._amount_box.blockSignals(True)
        self._amount_box.setRange(Decimal(1), self._position["position_size_stable"])
        self._amount_group.button(100).setChecked(True)
        self._amount_box.setValue(self._position["position_size_stable"])
        self._amount_box.blockSignals(False)

    def _type_change(self, button: QRadioButton) -> None:
        """Handle type change."""
        is_limit = button == self.limit_button
        self._price_box.setEnabled(is_limit)
        self._price_refresh_button.setEnabled(is_limit)
        if is_limit:
            self.set_price_clicked.emit()
            return
        self._price_box.setValue(Decimal(0))

    def _set_amount_spinbox(self, amount: Decimal) -> None:
        """Set amount on spinbox."""
        self._amount_box.blockSignals(True)
        self._amount_box.setValue(amount)
        self._amount_box.blockSignals(False)

    def _update_amount_buttons(self, amount: Decimal) -> None:
        """Update amount buttons if value on spinbox matches."""
        if amount == self._position["position_size_stable"] * Decimal("0.25"):
            self._amount_group.button(25).setChecked(True)
        elif amount == self._position["position_size_stable"] * Decimal("0.5"):
            self._amount_group.button(50).setChecked(True)
        elif amount == self._position["position_size_stable"] * Decimal("0.75"):
            self._amount_group.button(75).setChecked(True)
        elif amount == self._position["position_size_stable"]:
            self._amount_group.button(100).setChecked(True)
        else:
            button = self._amount_group.checkedButton()
            if button is None:
                return
            self._amount_group.setExclusive(False)
            button.setChecked(False)
            self._amount_group.setExclusive(True)

    def _set_amount_from_button(self, button: QRadioButton) -> None:
        """Set amount from button."""
        self._set_amount_spinbox(
            Decimal(self._amount_group.id(button))
            / Decimal("100")
            * self._position["position_size_stable"],
        )

    def _reduce_position(self) -> None:
        """Reduce position."""
        reduce_args: dict[str, Any] = {
            "pair": self._position["pair"],
            "size": Decimal(self._amount_box.value()),
            "trade_direction": self._position["trade_direction"],
        }
        if self.limit_button.isChecked():
            reduce_args["trade_type"] = PerpsTradeType.LIMIT
            reduce_args["execution_price"] = Decimal(self._price_box.value())
        else:
            reduce_args["trade_type"] = PerpsTradeType.MARKET
            reduce_args["execution_price"] = None

        self.reduce_clicked.emit(reduce_args)

    def set_price_limit(self, price: Decimal) -> None:
        """Set price for limit trade."""
        self._price_box.setValue(price)
