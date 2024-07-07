"""Table to visualize options available to buy."""

from __future__ import annotations

from typing import Any, Optional

import pandas
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

HEADER_MAP = {
    "percent": "%",
    "duration": "Time",
    "rate": "Rate",
    "available": "Available",
}

PERCENT_MAP = {
    1000000100000000000: "Up",
    1001000000000000000: "0.10%",
    1002500000000000000: "0.25%",
    1005000000000000000: "0.50%",
    1010000000000000000: "1.00%",
    1030000000000000000: "3.00%",
    1050000000000000000: "5.00%",
    999999900000000000: "Down",
    999000000000000000: "0.10%",
    997500000000000000: "0.25%",
    995000000000000000: "0.50%",
    990000000000000000: "1.00%",
    970000000000000000: "3.00%",
    950000000000000000: "5.00%",
}

DURATION_MAP = {
    15 * 60: "15m",
    30 * 60: "30m",
    60 * 60: "1h",
    2 * 60 * 60: "2h",
    4 * 60 * 60: "4h",
    8 * 60 * 60: "8h",
    24 * 60 * 60: "1d",
}


class OptionsTableModel(QAbstractTableModel):
    """Table model for options available to buy."""

    def __init__(self, data: Optional[pandas.DataFrame] = None) -> None:
        """Initialize table model."""
        QAbstractTableModel.__init__(self)
        self._data = data if data else pandas.DataFrame()
        self.headers_source = list(HEADER_MAP.keys())

    def rowCount(self, parent) -> int:  # type: ignore
        """Get row count."""
        return self._data.shape[0]

    def columnCount(self, parent):  # type: ignore
        """Get column count."""
        return len(self.headers_source)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore  # noqa: PLR0911
        """Define how data is displayed."""
        current_header = self.headers_source[index.column()]
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole:
                if current_header == "percent":
                    return PERCENT_MAP[self._data.iloc[index.row()][current_header]]
                if current_header == "duration":
                    return DURATION_MAP[self._data.iloc[index.row()][current_header]]
                if current_header == "rate":
                    return f"{1 + self._data.iloc[index.row()][current_header] / 10**18:.2f}"
                if current_header == "available":
                    return f"${self._data.iloc[index.row()][current_header] / 10**6:.2f}"

            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None
        return None

    def headerData(self, section, orientation, role):
        """Define header data."""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return HEADER_MAP[self.headers_source[section]]
        return None

    def update_data(self, data: pandas.DataFrame) -> None:
        """Update table data."""
        if not self._data.empty and data.equals(self._data):
            return
        self.beginResetModel()
        self._data = data
        self.endResetModel()


class OptionsTableView(QTableView):
    """Table view to display options available to buy."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize table view."""
        super().__init__(parent=parent)
        self._setup_style()
        self.setMinimumSize(self.sizeHint())

    def _setup_style(self) -> None:
        """Set table style."""
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
