"""Widget to control web3 configs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import orjson
from PySide6 import QtCore, QtWidgets

from plutus_terminal.core.config import CONFIG
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import Web3RPC


class Web3Config(QtWidgets.QWidget):
    """Widget to control web3 configs."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)

        self._main_layout = QtWidgets.QVBoxLayout()

        self._web3_rpc_bar = TopBar("Web3 RPCs")
        self._rpcs_layout = QtWidgets.QVBoxLayout()
        self._reset_rpcs_btn = QtWidgets.QPushButton("Reset RPCs")
        self._save_rpcs_btn = QtWidgets.QPushButton("Save RPCs")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._reset_rpcs_btn.setMinimumSize(80, 30)
        self._reset_rpcs_btn.clicked.connect(self._reset_rpcs)

        self._save_rpcs_btn.setProperty("class", "LONG")
        self._save_rpcs_btn.setMinimumSize(80, 30)
        self._save_rpcs_btn.clicked.connect(self._save_rpcs)

        web3_rcps = CONFIG.get_all_web3_rpc()

        for web3_rpc in web3_rcps:
            rpc_config = RPCConfig(web3_rpc=web3_rpc)
            self._rpcs_layout.addWidget(rpc_config)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._web3_rpc_bar)
        self._main_layout.addLayout(self._rpcs_layout)
        rpcs_layout = QtWidgets.QHBoxLayout()
        rpcs_layout.addStretch()
        rpcs_layout.addWidget(self._reset_rpcs_btn)
        rpcs_layout.addWidget(self._save_rpcs_btn)
        self._main_layout.addLayout(rpcs_layout)
        self._main_layout.addStretch()

        self.setLayout(self._main_layout)

    def _save_rpcs(self) -> None:
        """Save RPCs."""
        for index in range(self._rpcs_layout.count()):
            rpc_config = self._rpcs_layout.itemAt(index).widget()
            if isinstance(rpc_config, RPCConfig):
                rpc_config.write_to_db()

        Toast.show_message("RPCs updated", type_=ToastType.SUCCESS)

    def _reset_rpcs(self) -> None:
        """Reset RPCs."""
        for index in range(self._rpcs_layout.count()):
            rpc_config = self._rpcs_layout.itemAt(index).widget()
            if isinstance(rpc_config, RPCConfig):
                rpc_config.reset_to_current()


class RPCConfig(QtWidgets.QFrame):
    """Widget to control RPC configs."""

    def __init__(
        self,
        web3_rpc: Web3RPC,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._web3_rpc = web3_rpc

        self._main_layout = QtWidgets.QGridLayout()
        self._label = QtWidgets.QLabel()
        self._model = QtCore.QStringListModel()
        self._list = QtWidgets.QListView()
        self._input_field = QtWidgets.QLineEdit()
        self._add_button = QtWidgets.QPushButton("Add")
        self._remove_button = QtWidgets.QPushButton("Remove")

        self._setup_widgets()
        self._setup_layout()

        self.reset_to_current()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setObjectName("filter")
        self._label.setObjectName("title")

        self._list.setModel(self._model)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._input_field.setPlaceholderText("Enter new RPC url...")

        self._add_button.setMinimumHeight(30)
        self._add_button.setProperty("class", "LONG")
        self._add_button.clicked.connect(self._add_rpc)
        self._add_button.setToolTip("Add new RPC from input")
        self._remove_button.setMinimumHeight(30)
        self._remove_button.setProperty("class", "SHORT")
        self._remove_button.clicked.connect(self._remove_rpc)
        self._remove_button.setToolTip("Remove selected RPC")

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(
            self._label,
            0,
            0,
            1,
            2,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        self._main_layout.addWidget(self._list, 1, 0, 1, 2)
        self._main_layout.addWidget(self._input_field, 2, 0, 1, 2)
        self._main_layout.addWidget(self._add_button, 3, 0)
        self._main_layout.addWidget(self._remove_button, 3, 1)

        self.setLayout(self._main_layout)

    def reset_to_current(self) -> None:
        """Reset to current."""
        self._label.setText(str(self._web3_rpc.chain_name))
        self._model.setStringList(orjson.loads(str(self._web3_rpc.rpc_urls)))

    def _add_rpc(self) -> None:
        """Add RPC from input to list."""
        current_list = self._model.stringList()
        new_item = self._input_field.text()
        if new_item not in current_list:
            current_list.append(new_item)
            self._model.setStringList(current_list)
        self._input_field.clear()

    def _remove_rpc(self) -> None:
        """Remove selected RPC."""
        selected_indexes = self._list.selectedIndexes()
        if not selected_indexes:
            return
        current_list = self._model.stringList()
        indexes = [sel.row() for sel in selected_indexes]
        for index in sorted(indexes, reverse=True):
            current_list.pop(index)
        self._model.setStringList(current_list)

    def write_to_db(self) -> None:
        """Write web3_rpc to database."""
        current_list = self._model.stringList()
        self._web3_rpc.rpc_urls = orjson.dumps(current_list)  # type: ignore
        CONFIG.write_model_to_db(self._web3_rpc)
