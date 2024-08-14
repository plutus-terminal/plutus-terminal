"""Filter manager."""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from httpx import Client
import orjson

from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.news.filter._actions import FILTER_ACTIONS_MAP
from plutus_terminal.core.news.filter._filters import (
    DataMatchingFilter,
    KeywordMatchingFilter,
)
from plutus_terminal.core.news.filter.types import ActionType, FilterType

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import UserFilter
    from plutus_terminal.core.types_ import NewsData


class FilterManager:
    """Manage all filters."""

    def __init__(self) -> None:
        """Initialize."""
        self._keyword_filters = KeywordMatchingFilter()
        self._data_matching_filters = DataMatchingFilter()

        self._filter_type_map = OrderedDict(
            {
                FilterType.KEYWORD_MATCHING: self._keyword_filters,
                FilterType.DATA_MATCHING: self._data_matching_filters,
            },
        )
        self._all_user_filters: list[UserFilter] = AppConfig.get_all_user_filters()

        self._create_internal_filters()
        self._create_user_filters()

    def _fetch_all_token_data(self) -> dict:
        """Fetch all token data.

        Token map for filtering provided by PhoenixNews API.
        """
        with Client() as client:
            response = client.get("https://api.phoenixnews.io/getAllTokens")
        response.raise_for_status()
        return response.json()

    def _create_internal_filters(self) -> None:
        """Create internal filters."""
        # Coin association with token data from PhoenixNews API
        token_data = self._fetch_all_token_data()
        for item in token_data:
            for word in item["baseCurrencyName"]:
                symbol = item["baseSymbol"].replace("\\", "")
                symbol = symbol.replace("$", "")
                self._keyword_filters.add_to_queue(
                    {"keyword": word.lower()},
                    FILTER_ACTIONS_MAP[ActionType.COIN_ASSOCIATION],
                    {"coin": symbol, "color": (255, 140, 0)},
                )

    def _create_user_filters(self) -> None:
        """Create user filters."""
        for user_filter in self._all_user_filters:
            filter_type = FilterType(user_filter.filter_type)  # type: ignore
            match_pattern = orjson.loads(user_filter.match_pattern)  # type: ignore
            action_type = ActionType(user_filter.action_type)  # type: ignore
            action_args = orjson.loads(user_filter.action_args)  # type: ignore

            self._filter_type_map[filter_type].add_to_queue(
                match_pattern,
                FILTER_ACTIONS_MAP[action_type],
                action_args,
            )

    def update_filters(self) -> None:
        """Re-create all internal and user filters."""
        for filter_type in self._filter_type_map.values():
            filter_type.clear_queue()
        self._all_user_filters: list[UserFilter] = AppConfig.get_all_user_filters()
        self._create_internal_filters()
        self._create_user_filters()

    def filter(self, news_data: NewsData) -> NewsData:
        """Run all created filters on the news data provided.

        Args:
            news_data (NewsData): News data to be filtered.

        Returns:
            NewsData: Filtered news data.
        """
        for filter_type in self._filter_type_map.values():
            news_data = filter_type.execute(news_data)
            # Break ealier if this news is being ignored.
            if news_data["ignored"]:
                break
        return news_data
