"""Module to manage app configuration."""

from typing import Any, Self

import keyring
import orjson
from PySide6.QtCore import QObject, Signal

from plutus_terminal.core.db.models import (
    DATABASE,
    DATABASE_PATH,
    GUISettings,
    KeyringAccount,
    TradeConfig,
    UserFilter,
    Web3RPC,
    create_database,
)
from plutus_terminal.core.types_ import ExchangeType


class GUISettingsService:
    """Manages GUISettings CRUD and caching."""

    def __init__(self) -> None:
        """Initialize GUISettingsService state."""
        self._cache: dict[str, Any] = {}

    @staticmethod
    def initialize_defaults(defaults: dict[str, Any]) -> None:
        """Initialize GUISettings with default values."""
        with DATABASE.atomic():
            for key, default in defaults.items():
                GUISettings.get_or_create(
                    key=key,
                    defaults={"value": orjson.dumps(default)},
                )

    def get(self, key: str) -> str | bool | int:
        """Get GUISettings value by key.

        Args:
            key (str): GUISettings key.

        Returns:
            str|bool|int: GUISettings value.
        """
        if key not in self._cache:
            raw = GUISettings.get(GUISettings.key == key).value
            self._cache[key] = orjson.loads(raw)
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Set GUISettings value by key.

        Args:
            key (str): GUISettings key.
            value (Any): GUISettings value.
        """
        self._cache[key] = value
        raw = orjson.dumps(value)
        GUISettings.update(value=raw).where(GUISettings.key == key).execute()


class AccountService:
    """Handles KeyringAccount and TradeConfig creation/deletion."""

    @staticmethod
    def get_all() -> list[KeyringAccount]:
        """Get all KeyringAccounts."""
        return list(KeyringAccount.select())

    @staticmethod
    def create(username: str, exchange_type: ExchangeType, exchange_name: str) -> KeyringAccount:
        """Create KeyringAccount and TradeConfig."""
        with DATABASE.atomic():
            acct = KeyringAccount.create(
                username=username,
                exchange_type=exchange_type,
                exchange_name=exchange_name,
            )
            TradeConfig.create(account=acct)
        return acct

    @staticmethod
    def delete(account_id: int) -> None:
        """Delete KeyringAccount and TradeConfig."""
        with DATABASE.atomic():
            account = KeyringAccount.get_by_id(account_id)
            keyring.delete_password(AppConfig.SERVICE_NAME, str(account.username))
            TradeConfig.delete().where(TradeConfig.account == account_id).execute()
            KeyringAccount.delete().where(KeyringAccount.id == account_id).execute()


class RPCService:
    """Manages Web3RPC defaults and queries."""

    DEFAULT_RPCS: dict[str, list[str]] = {  # noqa: RUF012
        "Arbitrum One Fetcher": [
            "https://arbitrum-one-rpc.publicnode.com",
            "https://arbitrum.blockpi.network/v1/rpc/public",
            "https://arbitrum-one.public.blastapi.io/",
        ],
        "Arbitrum One Trader": ["https://arb1.arbitrum.io/rpc"],
    }

    def initialize_defaults(self) -> None:
        """Initialize Web3RPC with default values."""
        with DATABASE.atomic():
            for name, urls in self.DEFAULT_RPCS.items():
                Web3RPC.get_or_create(
                    chain_name=name,
                    defaults={"rpc_urls": orjson.dumps(urls)},
                )

    @staticmethod
    def get_by_name(chain_name: str) -> Web3RPC:
        """Get Web3RPC by chain name.

        Args:
            chain_name (str): Web3RPC chain name.

        Returns:
            Web3RPC: Web3RPC object.
        """
        return Web3RPC.get(Web3RPC.chain_name == chain_name)

    @staticmethod
    def get_all() -> list[Web3RPC]:
        """Get all Web3RPCs.

        Returns:
            list[Web3RPC]: List of Web3RPC objects.
        """
        return list(Web3RPC.select())


class TradeConfigService:
    """Manages retrieval and updates of TradeConfig for a given account."""

    def __init__(self, account_id: int) -> None:
        """Initialize TradeConfigService state."""
        self.account_id = account_id

    def load(self) -> TradeConfig:
        """Load TradeConfig for a given account.

        Returns:
            TradeConfig: TradeConfig object.
        """
        return TradeConfig.get(TradeConfig.account == self.account_id)

    def update(self, field: str, value: Any) -> None:  # noqa: ANN401
        """Update TradeConfig for a given account.

        Args:
            field (str): TradeConfig field.
            value (Any): TradeConfig value.
        """
        TradeConfig.update(**{field: value}).where(TradeConfig.account == self.account_id).execute()


class ConfigField:
    """Descriptor that manages a single TradeConfig field.

      - Persists changes via TradeConfigService.update()
      - Updates the in-memory private attribute
      - Emits a per-field Qt signal when modified

    Args:
        field (str): Name of the TradeConfig attribute this descriptor controls.
    """

    def __init__(self, field: str) -> None:
        """Initialize ConfigField state."""
        self.field: str = field

    def __get__(self, instance: "AppConfig | None", owner: type[Any]) -> Any:  # noqa: ANN401
        """Retrieve the value of the associated TradeConfig field.

        Args:
            instance (AppConfig): The AppConfig instance invoking the change.
            owner (Any): The AppConfig class.

        Returns:
            Any: The value of the field.
        """
        if instance is None:
            return self
        return getattr(instance, f"_{self.field}")

    def __set__(self, instance: "AppConfig", value: Any) -> None:  # noqa: ANN401
        """Persist and broadcast a change to the associated TradeConfig field.

        Args:
            instance (AppConfig): The AppConfig instance invoking the change.
            value (Any): The new value for the field.
        """
        instance._trade_service.update(self.field, value)  # noqa: SLF001
        setattr(instance, f"_{self.field}", value)
        getattr(instance, f"{self.field}_changed").emit(value)


class AppConfig(QObject):
    """Singleton configuration object with shared state, per-field signals, and services.

    Attributes:
           leverage (int): current leverage setting (descriptor-injected)
           stop_loss (float): current stop-loss setting
           take_profit (float): current take-profit setting
           trade_value_lowest (int)
           trade_value_low (int)
           trade_value_medium (int)
           trade_value_high (int)
    """

    _instance: Self | None = None

    # Declare attributes for type checkers
    leverage: int
    stop_loss: float
    take_profit: float
    trade_value_lowest: int
    trade_value_low: int
    trade_value_medium: int
    trade_value_high: int
    current_account_id: int

    SERVICE_NAME = "plutus-terminal"

    # Trade Config Signals
    leverage_changed = Signal(int)
    stop_loss_changed = Signal(float)
    take_profit_changed = Signal(float)
    trade_value_lowest_changed = Signal(int)
    trade_value_low_changed = Signal(int)
    trade_value_medium_changed = Signal(int)
    trade_value_high_changed = Signal(int)
    current_account_id_changed = Signal(int)

    # GUI Settings Signals
    first_run_changed = Signal(bool)
    password_validation_changed = Signal(str)
    news_show_images_changed = Signal(bool)
    news_desktop_notifications_changed = Signal(bool)
    minimize_to_tray_changed = Signal(bool)
    window_geometry_changed = Signal(dict)
    toast_position_changed = Signal(str)

    # Other Signals
    account_deleted = Signal()
    account_created = Signal()

    DEFAULT_GUI_SETTINGS: dict[str, Any] = {  # noqa: RUF012
        "first_run": True,
        "password_validation": "",
        "current_account_id": 1,
        "news_show_images": True,
        "news_desktop_notifications": True,
        "minimize_to_tray": True,
        "window_geometry": {},
        "toast_position": "bottom_left",
    }

    _trade_fields = [  # noqa: RUF012
        "leverage",
        "stop_loss",
        "take_profit",
        "trade_value_lowest",
        "trade_value_low",
        "trade_value_medium",
        "trade_value_high",
    ]

    # Attach descriptors dynamically
    for _field in _trade_fields:
        locals()[_field] = ConfigField(_field)

    def __new__(cls) -> Self:
        """Singleton implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize AppConfig state."""
        # Initialize only once
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True

        # Services
        self.gui_settings_service = GUISettingsService()
        self.account_service = AccountService()
        self.rpc_service = RPCService()

        # Database and defaults
        self._ensure_database()
        self.gui_settings_service.initialize_defaults(self.DEFAULT_GUI_SETTINGS)
        self.rpc_service.initialize_defaults()

    def _ensure_database(self) -> None:
        if not DATABASE_PATH.exists():
            create_database()

    def _load_services_for_account(self) -> None:
        current_id = self.gui_settings_service.get("current_account_id")
        self._trade_service = TradeConfigService(current_id)  # type: ignore

    def load_all_configs(self) -> None:
        """Loads GUI and trade settings into memory."""
        # Load current account and trade config
        self._load_services_for_account()
        trade = self._trade_service.load()
        for f in self._trade_fields:
            setattr(self, f"_{f}", getattr(trade, f))

    @property
    def current_keyring_account(self) -> KeyringAccount:
        """Returns: Current KeyringAccount."""
        return KeyringAccount.get_by_id(self.gui_settings_service.get("current_account_id"))

    @current_keyring_account.setter
    def current_keyring_account(self, new_acct: KeyringAccount) -> None:
        """Sets the current KeyringAccount.

        Args:
            new_acct (KeyringAccount): New KeyringAccount.
        """
        if new_acct not in self.account_service.get_all():
            msg = f"Invalid account: {new_acct}"
            raise ValueError(msg)

        self.gui_settings_service.set("current_account_id", new_acct.id)  # type: ignore
        self._load_services_for_account()
        self.load_all_configs()
        self.current_account_id_changed.emit(new_acct.id)  # type: ignore

    def get_gui_settings(self, key: str) -> str | bool | int:
        """Returns: GUISettings value by key."""
        return self.gui_settings_service.get(key)

    def set_gui_settings(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Set GUISettings value by key.

        Args:
            key (str): GUISettings key.
            value (Any): GUISettings value.
        """
        self.gui_settings_service.set(key, value)

        signal = getattr(self, f"{key}_changed")
        signal.emit(value)

    def delete_account(self, account_id: int) -> None:
        """Delete an account from the database.

        Args:
            account_id (int): Account ID.
        """
        current_id = self.current_keyring_account.id  # type: ignore

        self.account_service.delete(account_id)
        self.account_deleted.emit()

        if account_id == current_id:
            self.current_keyring_account = self.account_service.get_all()[0]

    def create_account(
        self, username: str, exchange_type: ExchangeType, exchange_name: str
    ) -> KeyringAccount:
        """Create a new account and trade config.

        Args:
            username (str): Account username.
            exchange_type (ExchangeType): Exchange type.
            exchange_name (str): Exchange name.

        Returns:
            KeyringAccount: Created KeyringAccount.
        """
        account = self.account_service.create(username, exchange_type, exchange_name)
        self.account_created.emit()
        return account

    # Static wrappers
    get_all_accounts = staticmethod(AccountService.get_all)
    get_all_user_filters = staticmethod(lambda: list(UserFilter.select()))
    delete_user_filter = staticmethod(
        lambda uid: UserFilter.delete().where(UserFilter.id == uid).execute()  # type: ignore
    )
    get_web3_rpc_by_name = staticmethod(RPCService.get_by_name)
    get_all_web3_rpc = staticmethod(RPCService.get_all)
    write_model_to_db = staticmethod(lambda model: model.save())
