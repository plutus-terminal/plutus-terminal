"""Core utilities."""

from datetime import datetime
import math

import pandas

LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo
DEFAULT_BAR_NUMBERS = 500


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


def convert_timestamp_to_local_timezone(
    timestamp: pandas.Timestamp,
) -> pandas.Timestamp:
    """Convert pandas Timestamp target timeonze.

    The given Timestamp unit is seconds and it's UTC.

    Args:
        timestamp (pandas.Timestamp): Timestamp to convert.
        target_timezone (tzinfo): Target timezone.

    Returns :
        pandas.Timestamp: Converted timestamp.
    """
    utc_timestamp = pandas.to_datetime(timestamp, unit="s", utc=True)
    # Convert to local timezone and stripping timezone information
    # because of lightweight charts
    return utc_timestamp.tz_convert(LOCAL_TIMEZONE).tz_localize(None)


def convert_timestamp_from_local_to_utc(timestamp: pandas.Timestamp) -> pandas.Timestamp:
    """Convert pandas Timestamp from local timeonze to UTC.

    The given Timestamp unit is seconds and it's UTC.

    Args:
        timestamp (pandas.Timestamp): Timestamp to convert.
        target_timezone (tzinfo): Target timezone.

    Returns :
        pandas.Timestamp: Converted timestamp.
    """
    local_timestamp = pandas.to_datetime(timestamp, unit="s")
    # Convert to local timezone and stripping timezone information
    # because of lightweight charts
    return local_timestamp.tz_localize(LOCAL_TIMEZONE).tz_convert("UTC")
