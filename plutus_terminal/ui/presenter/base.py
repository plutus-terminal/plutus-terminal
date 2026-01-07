"""Base classes for MVP architecture."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

V = TypeVar("V")


class BaseView(ABC):
    """Base interface for all Views."""


class BasePresenter(ABC, Generic[V]):
    """Base class for all Presenters.

    The Presenter holds a reference to the View and interacts with the Model.
    """

    def __init__(self, view: V) -> None:
        """Initialize with view."""
        self.view = view

    @abstractmethod
    def start(self) -> None:
        """Start the presenter.

        Subscribe to events, load initial data, etc.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the presenter.

        Unsubscribe from events, cleanup, etc.
        """
        ...
