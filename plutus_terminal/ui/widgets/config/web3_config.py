"""Widget to control web3 configs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets

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

        self._main_layout = QtWidgets.QHBoxLayout()
        self._label = QtWidgets.QLabel()
        self._rpc_field = QtWidgets.QLineEdit()

        self._setup_widgets()
        self._setup_layout()

        self.reset_to_current()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setObjectName("filter")
        self._label.setObjectName("title")

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._label)
        self._main_layout.addWidget(self._rpc_field)
        self.setLayout(self._main_layout)

    def reset_to_current(self) -> None:
        """Reset to current."""
        self._label.setText(str(self._web3_rpc.chain_name))
        self._rpc_field.setText(str(self._web3_rpc.rpc_url))

    def write_to_db(self) -> None:
        """Write web3_rpc to database."""
        self._web3_rpc.rpc_url = self._rpc_field.text()  # type: ignore
        CONFIG.write_model_to_db(self._web3_rpc)
