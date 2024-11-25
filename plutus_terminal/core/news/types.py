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
    quote_message: str
    quote_user: str
    quote_image: str
    is_reply: bool
    is_self_reply: bool
    reply_user: str
    reply_message: str
    reply_image: str
    is_retweet: bool
    retweet_user: str
    icon: str
    source: str
    time: datetime
    coin: set[str]
    feed: str
    sfx: str
    ignored: bool
