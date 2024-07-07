"""News filters actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol

from plutus_terminal.core.news.filter.types import ActionType

if TYPE_CHECKING:
    from textsearch import TSResult

    from plutus_terminal.core.types_ import NewsData


class FilterAction(Protocol):
    """Protocol for news filter actions."""

    def __call__(
        self,
        news_data: NewsData,
        text_data_key: str,
        search_result: Optional[TSResult],
        **kwargs: dict,
    ) -> Any: ...  # noqa: ANN401


def coin_association_action(
    news_data: NewsData,
    text_data_key: str,
    search_result: Optional[TSResult],
    **kwargs: dict[Any, Any],
) -> NewsData:
    """Associate coin with news if found.

    Add coin symbol to news data and modify text to be shown with color if
    text_data_key is provided.

    Args:
        news_data (NewsData): News data to be modified.
        text_data_key (str): Key in news data of text being modified.
        search_result (Optional[TSResult]): Text search results used for text substitution.
        **kwargs: Keyword arguments. Valid arguments are:
            * coin (str): Coin symbol
            * color (tuple[int, int, int]): RGB color for text.
    """
    news_data["coin"].add(kwargs["coin"])
    # Only replace text if this key is provided
    if text_data_key and search_result:
        text = news_data[text_data_key]  # type: ignore
        # Ensure color keyword is a tuple
        text = (
            f"{text[:search_result.start]}<span style='color: rgb{tuple(kwargs['color'])};'>"
            f"{search_result.match}</span>{text[search_result.end:]}"
        )
        news_data[text_data_key] = text  # type: ignore
    return news_data


def sound_association_action(
    news_data: NewsData,
    text_data_key: str,
    search_result: Optional[TSResult],
    **kwargs: dict[Any, Any],
) -> NewsData:
    """Associate sound with news if found.

    Add sound to news data and modify text to be shown with color if
    text_data_key is provided.

    Args:
        news_data (NewsData): News data to be modified.
        text_data_key (str): Key in news data of text being modified.
        search_result (Optional[TSResult]): Text search results used for text substitution.
        text_part (str): Text part to be modified.
        **kwargs: Keyword arguments. Valid arguments are:
            * sound_path (str): QResources path to sound.
            * color (tuple[int, int, int]): RGB color for text.
    """
    news_data["sfx"] = kwargs["sound_path"]
    # Only replace text if this key is provided
    if text_data_key and search_result:
        text = news_data[text_data_key]  # type: ignore
        # Ensure color keyword is a tuple
        text = (
            f"{text[:search_result.start]}<span style='color: rgb{tuple(kwargs['color'])};'>"
            f"{search_result.match}</span>{text[search_result.end:]}"
        )
        news_data[text_data_key] = text  # type: ignore
    return news_data


def ignore_action(
    news_data: NewsData,
    text_data_key: str,  # noqa: ARG001
    search_result: Optional[TSResult],  # noqa: ARG001
    **kwargs: dict[Any, Any],  # noqa: ARG001
) -> NewsData:
    """Ignore news.

    Args:
        news_data (NewsData): News data to be ignored.
        text_data_key (str): Argument not used!
        search_result (Optional[TSResult]): Argument not used!
        **kwargs: Argument not used!
    """
    news_data["ignored"] = True
    return news_data


FILTER_ACTIONS_MAP = {
    ActionType.COIN_ASSOCIATION: coin_association_action,
    ActionType.SOUND_ASSOCIATION: sound_association_action,
    ActionType.IGNORE: ignore_action,
}
