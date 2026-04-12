"""Utilities for UI."""

from datetime import datetime
import math
from numbers import Real
from typing import Any, Literal, Optional, TypeVar, cast

import pandas
from PySide6.QtCore import QDir
from PySide6.QtWidgets import QWidget
from qasync import contextlib

from plutus_terminal.core.exchange.types import PerpsTradeDirection

T = TypeVar("T", bound=QWidget)

LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo
DEFAULT_BAR_NUMBERS = 500
_SECONDS_TO_MS_THRESHOLD = 10_000_000_000
UnixTimeUnit = Literal["s", "ms"]


def _normalize_unix_unit(timestamp: Real) -> UnixTimeUnit:
    """Return the unix timestamp unit for a numeric timestamp."""
    numeric_timestamp = float(timestamp)
    return "ms" if abs(numeric_timestamp) >= _SECONDS_TO_MS_THRESHOLD else "s"


def _coerce_utc_timestamp(timestamp: Any) -> pandas.Timestamp:  # noqa: ANN401
    """Normalize an exchange timestamp into a timezone-aware UTC timestamp."""
    if isinstance(timestamp, Real) and not isinstance(timestamp, bool):
        numeric_timestamp = cast("float", float(timestamp))
        utc_timestamp = pandas.to_datetime(
            numeric_timestamp,
            unit=_normalize_unix_unit(timestamp),
            utc=True,
        )
    else:
        utc_timestamp = pandas.Timestamp(timestamp)
        if utc_timestamp.tzinfo is None:
            utc_timestamp = utc_timestamp.tz_localize("UTC")
        else:
            utc_timestamp = utc_timestamp.tz_convert("UTC")
    return utc_timestamp.as_unit("ns")


def _coerce_local_timestamp(timestamp: Any) -> pandas.Timestamp:  # noqa: ANN401
    """Normalize a chart-local timestamp into a timezone-aware local timestamp."""
    if isinstance(timestamp, Real) and not isinstance(timestamp, bool):
        numeric_timestamp = cast("float", float(timestamp))
        local_timestamp = pandas.to_datetime(
            numeric_timestamp, unit=_normalize_unix_unit(timestamp)
        )
    else:
        local_timestamp = pandas.Timestamp(timestamp)
    if local_timestamp.tzinfo is None:
        local_timestamp = local_timestamp.tz_localize(LOCAL_TIMEZONE)
    else:
        local_timestamp = local_timestamp.tz_convert(LOCAL_TIMEZONE)
    return local_timestamp.as_unit("ns")


def get_minimal_digits(number: float, figures: int) -> int:
    """Get minimal number of digits to show after dot.

    Args:
        number (float): Number to get minimal digits.
        figures (int): Amount of figures after the first non 0.
    """
    if number == 0:
        return 0
    digits = -math.floor(math.log10(abs(number))) + (figures)
    # If 0, figures amount should be showed after dot
    if digits == 0 or digits < figures:
        digits = figures
    return digits


def list_resources_from_prefix(prefix: str) -> list[str]:
    """List all resources of the given prefix."""
    qdir = QDir(":/")
    qdir.setFilter(QDir.Filter.Files | QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
    qdir.setPath(qdir.filePath(prefix))
    return qdir.entryList()


def create_stored_widget(
    widget: type[T],
    storage: dict,
    pair: str,
    trade_direction: PerpsTradeDirection,
    **kwargs: Any,  # noqa: ANN401
) -> T:
    """Create stored widget.

    Args:
        widget (QtWidget): Widget to store.
        storage (dict): Dict to store created widget.
        pair (str): Pair.
        trade_direction (PerpsTradeDirection): Trade direction.
        **kwargs (Any): Additional kwargs.

    Returns:
        QWidget: Stored widget.
    """
    new_widget = widget(**kwargs)
    storage.setdefault(pair, {})
    old_widget = storage[pair].pop(trade_direction.value, None)
    if old_widget is not None:
        with contextlib.suppress(RuntimeError):
            old_widget.deleteLater()
    storage[pair][trade_direction.value] = new_widget
    return new_widget


def get_stored_widget(
    storage: dict,
    pair: str,
    trade_direction: PerpsTradeDirection,
) -> Optional[QWidget]:
    """Get stored widget.

    Args:
        storage (dict): Dict to store created widget.
        pair (str): Pair.
        trade_direction (PerpsTradeDirection): Trade direction.

    Returns:
        QWidget: Stored widget.
    """
    storage.setdefault(pair, {})
    return storage[pair].get(
        trade_direction.value,
        None,
    )


def get_or_create_stored_widget(
    widget: type[T],
    storage: dict,
    pair: str,
    trade_direction: PerpsTradeDirection,
    **kwargs: Any,  # noqa: ANN401
) -> Optional[QWidget] | T:
    """Get or create stored widget.

    Args:
        widget (QtWidget): Widget to store.
        storage (dict): Dict to store created widget.
        pair (str): Pair.
        trade_direction (PerpsTradeDirection): Trade direction.
        **kwargs (Any): Additional kwargs.

    Returns:
        QWidget: Stored widget.
    """
    stored_widget = get_stored_widget(storage, pair, trade_direction)
    if stored_widget is None:
        stored_widget = create_stored_widget(
            widget,
            storage,
            pair,
            trade_direction,
            **kwargs,
        )
    return stored_widget


def convert_timestamp_to_local_timezone(timestamp: Any) -> pandas.Timestamp:  # noqa: ANN401
    """Convert pandas Timestamp target timeonze.

    The given Timestamp unit is seconds and it's UTC.

    Args:
        timestamp (pandas.Timestamp): Timestamp to convert.
        target_timezone (tzinfo): Target timezone.

    Returns :
        pandas.Timestamp: Converted timestamp.
    """
    utc_timestamp = _coerce_utc_timestamp(timestamp)
    # Convert to local timezone and stripping timezone information
    # because of lightweight charts
    return utc_timestamp.tz_convert(LOCAL_TIMEZONE).tz_localize(None).as_unit("ns")


def convert_timestamp_from_local_to_utc(timestamp: Any) -> pandas.Timestamp:  # noqa: ANN401
    """Convert pandas Timestamp from local timeonze to UTC.

    The given Timestamp unit is seconds and it's UTC.

    Args:
        timestamp (pandas.Timestamp): Timestamp to convert.
        target_timezone (tzinfo): Target timezone.

    Returns :
        pandas.Timestamp: Converted timestamp.
    """
    local_timestamp = _coerce_local_timestamp(timestamp)
    # Convert to local timezone and stripping timezone information
    # because of lightweight charts
    return local_timestamp.tz_convert("UTC").as_unit("ns")
