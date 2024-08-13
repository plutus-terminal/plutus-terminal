"""Utilities for UI."""

from functools import partial
import math
from typing import Any, Optional, TypeVar

from PySide6.QtCore import QDir
from PySide6.QtWidgets import QWidget
from qasync import contextlib

from plutus_terminal.core.exchange.types import PerpsTradeDirection

T = TypeVar("T", bound=QWidget)


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
