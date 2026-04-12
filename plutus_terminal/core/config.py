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
            account.delete_instance()


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
           leverage_button_1..leverage_button_7 (int): leverage preset buttons
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
    leverage_button_1: int
    leverage_button_2: int
    leverage_button_3: int
    leverage_button_4: int
    leverage_button_5: int
    leverage_button_6: int
    leverage_button_7: int
    current_account_id: int

    LEVERAGE_BUTTON_FIELDS = (
        "leverage_button_1",
        "leverage_button_2",
        "leverage_button_3",
        "leverage_button_4",
        "leverage_button_5",
        "leverage_button_6",
        "leverage_button_7",
    )

    SERVICE_NAME = "plutus-terminal"

    # Trade Config Signals
    leverage_changed = Signal(int)
    stop_loss_changed = Signal(float)
    take_profit_changed = Signal(float)
    trade_value_lowest_changed = Signal(int)
    trade_value_low_changed = Signal(int)
    trade_value_medium_changed = Signal(int)
    trade_value_high_changed = Signal(int)
    leverage_button_1_changed = Signal(int)
    leverage_button_2_changed = Signal(int)
    leverage_button_3_changed = Signal(int)
    leverage_button_4_changed = Signal(int)
    leverage_button_5_changed = Signal(int)
    leverage_button_6_changed = Signal(int)
    leverage_button_7_changed = Signal(int)
    current_account_id_changed = Signal(int)

    # GUI Settings Signals
    first_run_changed = Signal(bool)
    password_validation_changed = Signal(str)
    news_show_images_changed = Signal(bool)
    news_desktop_notifications_changed = Signal(bool)
    minimize_to_tray_changed = Signal(bool)
    window_geometry_changed = Signal(dict)
    toast_message_position_changed = Signal(str)
    toast_widget_position_changed = Signal(str)
    toast_message_duration_changed = Signal(int)
    toast_widget_duration_changed = Signal(int)

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
        "toast_message_position": "bottom_left",
        "toast_widget_position": "bottom_left",
        "toast_message_duration": 10,
        "toast_widget_duration": 35,
    }

    TERMINAL_GUI_SETTINGS: tuple[str, ...] = (
        "news_show_images",
        "news_desktop_notifications",
        "minimize_to_tray",
    )

    TOAST_GUI_SETTINGS: tuple[str, ...] = (
        "toast_message_position",
        "toast_widget_position",
        "toast_message_duration",
        "toast_widget_duration",
    )

    TRADE_CONFIG_DEFAULTS: dict[str, Any] = {  # noqa: RUF012
        "leverage": 10,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "trade_value_lowest": 100,
        "trade_value_low": 250,
        "trade_value_medium": 500,
        "trade_value_high": 1000,
        "leverage_button_1": 2,
        "leverage_button_2": 5,
        "leverage_button_3": 10,
        "leverage_button_4": 20,
        "leverage_button_5": 25,
        "leverage_button_6": 50,
        "leverage_button_7": 100,
    }

    EXPORTABLE_GUI_SETTINGS: tuple[str, ...] = (
        *TERMINAL_GUI_SETTINGS,
        *TOAST_GUI_SETTINGS,
    )

    _trade_fields = [  # noqa: RUF012
        "leverage",
        "stop_loss",
        "take_profit",
        "trade_value_lowest",
        "trade_value_low",
        "trade_value_medium",
        "trade_value_high",
        *LEVERAGE_BUTTON_FIELDS,
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

        # Database and defaults
        self._ensure_database()
        self.gui_settings_service.initialize_defaults(self.DEFAULT_GUI_SETTINGS)

    def _ensure_database(self) -> None:
        if not DATABASE_PATH.exists():
            create_database()
            return
        from plutus_terminal.core.db.models import ensure_trade_config_columns

        ensure_trade_config_columns()

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
    def leverage_button_values(self) -> list[int]:
        """Return configured leverage preset button values."""
        return [getattr(self, field_name) for field_name in self.LEVERAGE_BUTTON_FIELDS]

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

    def reset_current_trade_config(self) -> None:
        """Reset the current account trade configuration to defaults."""
        for field_name, default_value in self.TRADE_CONFIG_DEFAULTS.items():
            setattr(self, field_name, default_value)

    def reset_terminal_gui_settings(self) -> None:
        """Reset the terminal-facing GUI settings to defaults."""
        for key in self.TERMINAL_GUI_SETTINGS:
            self.set_gui_settings(key, self.DEFAULT_GUI_SETTINGS[key])

    def reset_toast_gui_settings(self) -> None:
        """Reset the toast-facing GUI settings to defaults."""
        for key in self.TOAST_GUI_SETTINGS:
            self.set_gui_settings(key, self.DEFAULT_GUI_SETTINGS[key])

    def export_settings_snapshot(self) -> dict[str, Any]:
        """Export the current local settings snapshot.

        Secret-bearing data such as account credentials and API keys are excluded.
        """
        return {
            "version": 1,
            "gui_settings": {
                key: self.get_gui_settings(key) for key in self.EXPORTABLE_GUI_SETTINGS
            },
            "trade_config": {
                field_name: getattr(self, field_name) for field_name in self._trade_fields
            },
            "user_filters": [
                {
                    "filter_type": int(user_filter.filter_type),
                    "match_pattern": str(user_filter.match_pattern),
                    "action_type": int(user_filter.action_type),
                    "action_args": str(user_filter.action_args),
                }
                for user_filter in UserFilter.select()
            ],
        }

    def _import_gui_settings(
        self,
        gui_settings: Any,  # noqa: ANN401
        warnings: list[str],
    ) -> None:
        """Import GUI settings from a snapshot payload."""
        if not isinstance(gui_settings, dict):
            warnings.append("GUI settings were skipped because the payload format is invalid.")
            return

        for key in self.EXPORTABLE_GUI_SETTINGS:
            if key in gui_settings:
                self.set_gui_settings(key, gui_settings[key])

    def _import_trade_config(
        self,
        trade_config: Any,  # noqa: ANN401
        warnings: list[str],
    ) -> None:
        """Import trade settings from a snapshot payload."""
        if not isinstance(trade_config, dict):
            warnings.append("Trade settings were skipped because the payload format is invalid.")
            return

        for field_name in self._trade_fields:
            if field_name in trade_config:
                setattr(self, field_name, trade_config[field_name])

    def _create_imported_user_filter(self, raw_filter: Any) -> str | None:  # noqa: ANN401
        """Create one imported user filter and return an optional warning."""
        if not isinstance(raw_filter, dict):
            return "One imported filter entry was skipped because it is invalid."

        try:
            UserFilter.create(
                filter_type=int(raw_filter["filter_type"]),
                match_pattern=str(raw_filter["match_pattern"]),
                action_type=int(raw_filter["action_type"]),
                action_args=str(raw_filter["action_args"]),
            )
        except (KeyError, TypeError, ValueError):
            return "One imported filter entry was skipped because it is incomplete."
        return None

    def _import_user_filters(
        self,
        user_filters: Any,  # noqa: ANN401
        warnings: list[str],
    ) -> None:
        """Import news filters from a snapshot payload."""
        if not isinstance(user_filters, list):
            warnings.append("News filters were skipped because the payload format is invalid.")
            return

        with DATABASE.atomic():
            UserFilter.delete().execute()
            for raw_filter in user_filters:
                warning = self._create_imported_user_filter(raw_filter)
                if warning is not None:
                    warnings.append(warning)

    def import_settings_snapshot(self, snapshot: dict[str, Any]) -> list[str]:
        """Import a previously exported local settings snapshot."""
        warnings: list[str] = []

        self._import_gui_settings(snapshot.get("gui_settings", {}), warnings)
        self._import_trade_config(snapshot.get("trade_config", {}), warnings)
        self._import_user_filters(snapshot.get("user_filters", []), warnings)

        return warnings

    # Static wrappers
    get_all_accounts = staticmethod(AccountService.get_all)
    get_all_user_filters = staticmethod(lambda: list(UserFilter.select()))
    delete_user_filter = staticmethod(
        lambda uid: UserFilter.delete().where(UserFilter.id == uid).execute()  # type: ignore
    )
    delete_all_user_filters = staticmethod(lambda: UserFilter.delete().execute())
    write_model_to_db = staticmethod(lambda model: model.save())
