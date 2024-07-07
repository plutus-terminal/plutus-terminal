"""Types for news."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from datetime import datetime


class NewsData(TypedDict):
    """News data dict from news source."""

    title: str
    link: str
    body: str
    image: str
    is_quote: bool
    quote: str
    quoter: str
    quote_image: str
    icon: str
    source: str
    time: datetime
    coin: set[str]
    feed: str
    sfx: str
    ignored: bool
