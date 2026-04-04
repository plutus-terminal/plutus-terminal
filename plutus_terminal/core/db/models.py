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
    leverage_button_1 = IntegerField(default=2)
    leverage_button_2 = IntegerField(default=5)
    leverage_button_3 = IntegerField(default=10)
    leverage_button_4 = IntegerField(default=20)
    leverage_button_5 = IntegerField(default=25)
    leverage_button_6 = IntegerField(default=50)
    leverage_button_7 = IntegerField(default=100)


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


def create_database() -> None:
    """Create database tables."""
    if DATABASE_PATH.exists():
        ensure_trade_config_columns()
        return
    with DATABASE:
        DATABASE.create_tables(
            [
                KeyringAccount,
                TradeConfig,
                GUISettings,
                UserFilter,
            ],
        )
    ensure_trade_config_columns()


def ensure_trade_config_columns() -> None:
    """Backfill new TradeConfig columns for existing local databases."""
    trade_config_table_name = "tradeconfig"
    if not DATABASE_PATH.exists() or not DATABASE.table_exists(trade_config_table_name):
        return

    column_defaults = {
        "leverage_button_1": 2,
        "leverage_button_2": 5,
        "leverage_button_3": 10,
        "leverage_button_4": 20,
        "leverage_button_5": 25,
        "leverage_button_6": 50,
        "leverage_button_7": 100,
    }
    existing_columns = {
        row[1]
        for row in DATABASE.execute_sql(
            f'PRAGMA table_info("{trade_config_table_name}")',
        ).fetchall()
    }

    with DATABASE.atomic():
        for column_name, default_value in column_defaults.items():
            if column_name in existing_columns:
                continue
            DATABASE.execute_sql(
                f'ALTER TABLE "{trade_config_table_name}" '
                f'ADD COLUMN "{column_name}" INTEGER DEFAULT {default_value}',
            )
