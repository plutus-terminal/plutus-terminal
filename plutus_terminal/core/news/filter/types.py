"""Types for filters."""

from __future__ import annotations

from enum import IntEnum


class FilterType(IntEnum):
    """Filter types."""

    KEYWORD_MATCHING = 0
    DATA_MATCHING = 1


class ActionType(IntEnum):
    """Filter Action types."""

    COIN_ASSOCIATION = 0
    SOUND_ASSOCIATION = 1
    IGNORE = 2
