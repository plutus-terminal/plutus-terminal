"""News Filters."""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Protocol

from textsearch import TextSearch

if TYPE_CHECKING:
    from plutus_terminal.core.news.filter._actions import FilterAction
    from plutus_terminal.core.types_ import NewsData


class FilterBase(Protocol):
    """Protocol for news filters."""

    def add_to_queue(
        self,
        match_pattern: dict[str, str],
        filter_action: FilterAction,
        kwargs: dict,
    ) -> None:
        """Add filter to queue to be executed."""

    def execute(self, news_data: NewsData) -> NewsData:
        """Execute filter on newsData."""
        ...

    def clear_queue(self) -> None:
        """Clear filter queue."""


class KeywordMatchingFilter(FilterBase):
    """Filter news by keywords.

    Go over the text on the body and quote of the news and search for
    provided matches, then execute the associated action.

    """

    def __init__(self) -> None:
        """Initialize shared variables."""
        self._actions_to_execute: dict[str, tuple[FilterAction, dict]] = OrderedDict()
        self.text_search = TextSearch(case="insensitive", returns="object")

    def add_to_queue(
        self,
        match_pattern: dict[str, str],
        filter_action: FilterAction,
        kwargs: dict[str, Any],
    ) -> None:
        """Add filter to queue to be executed.

        Args:
            match_pattern (dict[str, str]): Dict with data to match.
                * KeywordMatchingFilter expects `{"keyword": str}`
            filter_action (FilterAction): Action to execute.
            kwargs (dict): Keyword arguments.
        """
        keyword_match = match_pattern["keyword"].lower()
        self._actions_to_execute[keyword_match] = (filter_action, kwargs)

        # Add all keywords to text search when adding to queue to improve performance.
        self.text_search.add(list(self._actions_to_execute.keys()))

    def execute(self, news_data: NewsData) -> NewsData:
        """Execute filter on newsData."""
        for part in ("body", "quote"):
            search_result = self.text_search.findall(news_data[part])  # type: ignore
            # Inverse to start from the end of text to preserve index
            for result in search_result[::-1]:
                match_action, match_kwargs = self._actions_to_execute[result.match.lower()]
                news_data = match_action(news_data, part, result, **match_kwargs)

                # Return ealier if this news is being ignored.
                if news_data["ignored"]:
                    return news_data

        return news_data

    def clear_queue(self) -> None:
        """Clear filter queue."""
        self._actions_to_execute.clear()


class DataMatchingFilter(FilterBase):
    """Filter news by matching data.

    Go over every added key in the news data and search for provided matches, then
    execute the associated action.
    """

    def __init__(self) -> None:
        """Initialize shared variables."""
        self._actions_by_data_key: dict[str, dict[str, tuple[FilterAction, dict]]] = OrderedDict()

    def add_to_queue(
        self,
        match_pattern: dict[str, str],
        filter_action: FilterAction,
        kwargs: dict[str, Any],
    ) -> None:
        """Add filter to queue to be executed.

        Args:
            match_pattern (dict[str, str]): Dict with data to match.
                * DataMatchingFilter expects `{"keyword": str, "data_key": str}`
            filter_action (FilterAction): Action to execute.
            kwargs (dict): Keyword arguments.
        """
        keyword_match = match_pattern["keyword"].lower()
        data_key = match_pattern["data_key"].lower()
        if data_key not in self._actions_by_data_key:
            self._actions_by_data_key[data_key] = {}

        self._actions_by_data_key[data_key][keyword_match] = (
            filter_action,
            kwargs,
        )

    def execute(self, news_data: NewsData) -> NewsData:
        """Execute filter on newsData."""
        for data_key, actions in self._actions_by_data_key.items():
            data = news_data.get(data_key, None)
            if data is None:
                continue
                # TODO: Log error
                # (f"Key {key} used in filter not found in news data.")

            # Check if data is set due to how coins are stored in NewsData
            if isinstance(data, set):
                data = {item.lower() for item in data}
                for keyword_match in data.intersection(actions.keys()):
                    filter_action, kwargs = actions[keyword_match]
                    news_data = filter_action(news_data, "", None, **kwargs)

                    # Return ealier if this news is being ignored.
                    if news_data["ignored"]:
                        return news_data
            elif isinstance(data, str):
                if data.lower() in actions:
                    filter_action, kwargs = actions[data.lower()]
                    news_data = filter_action(news_data, "", None, **kwargs)

                    # Return ealier if this news is being ignored.
                    if news_data["ignored"]:
                        return news_data
        return news_data

    def clear_queue(self) -> None:
        """Clear filter queue."""
        self._actions_by_data_key.clear()
