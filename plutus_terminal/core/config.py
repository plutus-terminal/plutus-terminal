"""Class to manage app config."""

from typing import Any

import keyring
import orjson
from peewee import ModelBase

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


class AppConfig:
    """Manage app config."""

    SERVICE_NAME = "plutus_terminal"

    def __init__(self) -> None:
        """Initialize shared variables."""
        self._current_keyring_account: KeyringAccount
        self._gui_settings_cache: dict[str, Any] = {}

        self._leverage = 0
        self._stop_loss = 0.0
        self._take_profit = 0.0
        self._trade_value_lowest = 0
        self._trade_value_low = 0
        self._trade_value_medium = 0
        self._trade_value_high = 0

        self._validate_database()

        # create default GUI settings
        self.create_default_gui_settings()
        # create default web3
        self.create_default_rpcs()

    @property
    def current_keyring_account(self) -> KeyringAccount:
        """Returns current account set in the terminal."""
        return self._current_keyring_account

    @current_keyring_account.setter
    def current_keyring_account(self, new_account: KeyringAccount) -> None:
        """Set new current account."""
        if new_account not in self.get_all_keyring_accounts():
            msg = f"Invalid account: {new_account}"
            raise ValueError(msg)
        with DATABASE.atomic():
            self.set_gui_settings("current_account_id", new_account.id)  # type: ignore

        self._current_keyring_account = new_account
        self.load_config()

    @property
    def leverage(self) -> int:
        """Returns leverage to be used in the terminal.

        This value is associated with the current account.
        """
        return self._leverage

    @leverage.setter
    def leverage(self, new_value: int) -> None:
        """Set new leverage value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"leverage": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._leverage = new_value

    @property
    def stop_loss(self) -> float:
        """Returns stop_loss to be used in the terminal.

        This value is associated with the current account.
        """
        return self._stop_loss

    @stop_loss.setter
    def stop_loss(self, new_value: float) -> None:
        """Set new stop_loss value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"stop_loss": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._stop_loss = new_value

    @property
    def take_profit(self) -> float:
        """Returns take_profit to be used in the terminal.

        This value is associated with the current account.
        """
        return self._take_profit

    @take_profit.setter
    def take_profit(self, new_value: float) -> None:
        """Set new take_profit value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"take_profit": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._take_profit = new_value

    @property
    def trade_value_lowest(self) -> int:
        """Returns trade_value_lowest to be used in the terminal.

        This value is associated with the current account.
        """
        return self._trade_value_lowest

    @trade_value_lowest.setter
    def trade_value_lowest(self, new_value: int) -> None:
        """Set new trade_value_lowest value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"trade_value_lowest": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._trade_value_lowest = new_value

    @property
    def trade_value_low(self) -> int:
        """Returns trade_value_lowe to be used in the terminal.

        This value is associated with the current account.
        """
        return self._trade_value_low

    @trade_value_low.setter
    def trade_value_low(self, new_value: int) -> None:
        """Set new trade_value_low value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"trade_value_low": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._trade_value_low = new_value

    @property
    def trade_value_medium(self) -> int:
        """Returns trade_value_medium to be used in the terminal.

        This value is associated with the current account.
        """
        return self._trade_value_medium

    @trade_value_medium.setter
    def trade_value_medium(self, new_value: int) -> None:
        """Set new trade_value_medium value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"trade_value_medium": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._trade_value_medium = new_value

    @property
    def trade_value_high(self) -> int:
        """Returns trade_value_high to be used in the terminal.

        This value is associated with the current account.
        """
        return self._trade_value_high

    @trade_value_high.setter
    def trade_value_high(self, new_value: int) -> None:
        """Set new trade_value_high value for current_keyring_account."""
        with DATABASE.atomic():
            self._generic_update(
                TradeConfig,
                {"trade_value_high": new_value},
                self.current_keyring_account.id,  # type: ignore
            )
        self._trade_value_high = new_value

    def _generic_update(
        self,
        model: ModelBase,
        attribute_dict: dict[str, Any],
        model_id: int,
    ) -> None:
        """Update Model attribute with given vallue.

        Args:
            model (Peewee.Model): Model to update value.
            attribute_dict (dict[str, Any]): Dict with attribute name and value.
            model_id (int): Id of the model to update.
        """
        query = model.update(**attribute_dict).where(model.id == model_id)  # type: ignore
        query.execute()

    def load_config(self) -> None:
        """Load config values from database."""
        account_id = GUISettings.get(GUISettings.key == "current_account_id").value

        keyring_account: KeyringAccount = KeyringAccount.get_by_id(account_id)
        self._current_keyring_account = keyring_account

        trade_config = TradeConfig.get(TradeConfig.account == keyring_account.id)  # type: ignore

        self._leverage = trade_config.leverage
        self._stop_loss = trade_config.stop_loss
        self._take_profit = trade_config.take_profit
        self._trade_value_lowest = trade_config.trade_value_lowest
        self._trade_value_low = trade_config.trade_value_low
        self._trade_value_medium = trade_config.trade_value_medium
        self._trade_value_high = trade_config.trade_value_high

    def create_default_gui_settings(self) -> None:
        """Get or create default GUI settings."""
        with DATABASE.atomic():
            GUISettings.get_or_create(
                key="first_run",
                defaults={"value": orjson.dumps(True)},
            )
            GUISettings.get_or_create(
                key="password_validation",
                defaults={"value": orjson.dumps("")},
            )
            GUISettings.get_or_create(
                key="current_account_id",
                defaults={"value": orjson.dumps(1)},
            )
            GUISettings.get_or_create(
                key="news_show_images",
                defaults={"value": orjson.dumps(True)},
            )
            GUISettings.get_or_create(
                key="news_desktop_notifications",
                defaults={"value": orjson.dumps(True)},
            )
            GUISettings.get_or_create(
                key="minimize_to_tray",
                defaults={"value": orjson.dumps(True)},
            )
            GUISettings.get_or_create(
                key="window_geometry",
                defaults={"value": orjson.dumps({})},
            )
            GUISettings.get_or_create(
                key="toast_position",
                defaults={"value": orjson.dumps("bottom_left")},
            )

    def get_gui_settings(self, key: str) -> Any:  # noqa: ANN401
        """Get GUI settings value for key."""
        cached_value = self._gui_settings_cache.get(key, None)
        if cached_value is not None:
            return cached_value

        value = GUISettings.get(GUISettings.key == key).value
        value = orjson.loads(value)
        self._gui_settings_cache[key] = value
        return value

    def set_gui_settings(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Set GUI settings value for key."""
        self._gui_settings_cache[key] = value
        value = orjson.dumps(value)
        GUISettings.update(value=value).where(GUISettings.key == key).execute()

    def _validate_database(self) -> None:
        """Validate database existence and tables."""
        if not DATABASE_PATH.exists():
            create_database()

    @staticmethod
    def get_all_keyring_accounts() -> list[KeyringAccount]:
        """Get all keyring accounts."""
        with DATABASE.atomic():
            return KeyringAccount.select()

    @staticmethod
    def get_all_user_filters() -> list[UserFilter]:
        """Get all user filters from database."""
        with DATABASE.atomic():
            return UserFilter.select()

    @staticmethod
    def write_model_to_db(model: Any) -> None:  # noqa: ANN401
        """Write model to database."""
        with DATABASE.atomic():
            model.save()

    @staticmethod
    def delete_user_filter(user_filter_id: int) -> None:
        """Delete user_filter from database."""
        with DATABASE.atomic():
            UserFilter.delete().where(UserFilter.id == user_filter_id).execute()  # type: ignore

    @staticmethod
    def create_account(
        username: str,
        exchange_type: ExchangeType,
        exchange_name: str,
    ) -> KeyringAccount:
        """Create new account."""
        with DATABASE:
            keyring_account = KeyringAccount.create(
                username=username,
                exchange_type=exchange_type,
                exchange_name=exchange_name,
            )
            TradeConfig.create(account=keyring_account)
        return keyring_account

    @staticmethod
    def delete_account(account_id: int) -> None:
        """Delete account."""
        with DATABASE.atomic():
            keyring_account = KeyringAccount.get_by_id(account_id)
            keyring.delete_password("plutus-terminal", str(keyring_account.username))
            KeyringAccount.delete().where(KeyringAccount.id == account_id).execute()  # type: ignore
            TradeConfig.delete().where(TradeConfig.account == account_id).execute()

    @staticmethod
    def create_default_rpcs() -> None:
        """Create default values for Web3 RPC."""
        with DATABASE.atomic():
            # Arbitrum One
            Web3RPC.get_or_create(
                chain_name="Arbitrum One Fetcher",
                defaults={
                    "rpc_urls": orjson.dumps(
                        [
                            "https://arbitrum-one-rpc.publicnode.com",
                            "https://arbitrum.blockpi.network/v1/rpc/public",
                            "https://rpc.ankr.com/arbitrum",
                            "https://arbitrum-one.public.blastapi.io/",
                            "https://arbitrum.llamarpc.com",
                        ],
                    ),
                },
            )

            Web3RPC.get_or_create(
                chain_name="Arbitrum One Trader",
                defaults={
                    "rpc_urls": orjson.dumps(
                        [
                            "https://arb1.arbitrum.io/rpc",
                        ],
                    ),
                },
            )

    @staticmethod
    def get_web3_rpc_by_name(chain_name: str) -> Web3RPC:
        """Get Web3 RPC by name."""
        with DATABASE.atomic():
            return Web3RPC.get(Web3RPC.chain_name == chain_name)

    @staticmethod
    def get_all_web3_rpc() -> list[Web3RPC]:
        """Get all Web3 RPC."""
        with DATABASE.atomic():
            return Web3RPC.select()


CONFIG = AppConfig()
