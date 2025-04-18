"""Peewee models."""

from pathlib import Path

from peewee import (
    CharField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

DATABASE_PATH = Path(__file__).parent.joinpath("plutus_terminal.db")
DATABASE = SqliteDatabase(DATABASE_PATH)


class BaseModel(Model):
    """Base class for Models."""

    class Meta:  # noqa: D106
        database = DATABASE


class KeyringAccount(BaseModel):
    """Model to hold account information."""

    username = CharField(unique=True)
    exchange_type = IntegerField()
    exchange_name = CharField()


class TradeConfig(BaseModel):
    """TradeConfig model."""

    account = ForeignKeyField(KeyringAccount, backref="trade_config")
    leverage = IntegerField(default=10)
    stop_loss = FloatField(default=0)
    take_profit = FloatField(default=0)
    trade_value_lowest = IntegerField(default=100)
    trade_value_low = IntegerField(default=250)
    trade_value_medium = IntegerField(default=500)
    trade_value_high = IntegerField(default=1000)


class UserFilter(BaseModel):
    """FilterConfig model."""

    filter_type = IntegerField()
    match_pattern = TextField()
    action_type = IntegerField()
    action_args = TextField()


class GUISettings(BaseModel):
    """Model for GUI settings.

    Expected keys:
        current_account_id
        window_size
        news_show_images
        news_desktop_notifications
    """

    key = CharField(unique=True)
    value = TextField()


class Web3RPC(BaseModel):
    """Model for Web3 RPC settings.

    Expected keys:
        rpc_url
    """

    chain_name = CharField(unique=True)
    rpc_urls = TextField()


def create_database() -> None:
    """Create database tables."""
    if DATABASE_PATH.exists():
        return
    with DATABASE:
        DATABASE.create_tables(
            [
                KeyringAccount,
                TradeConfig,
                GUISettings,
                UserFilter,
                Web3RPC,
            ],
        )
