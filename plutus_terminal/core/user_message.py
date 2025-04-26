"""User message."""

from dataclasses import dataclass, field
from enum import Enum, auto
import os


class MessageLevel(Enum):
    """Message level."""

    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()


def create_id() -> bytes:
    """Create message id."""
    return os.urandom(8)


@dataclass(frozen=True, slots=True)
class UserMessage:
    """Message to send.

    Args:
        text (str): Message text.
        level (MessageLevel, optional): Message level. Defaults to Level.INFO.
        message_id (bytes, optional): Message token. Defaults to create_id().
        timeout_ms (int, optional): Message timeout in milliseconds. Defaults to 10_000.
        desktop (bool, optional): Show on desktop. Defaults to False.
    """

    text: str
    level: MessageLevel = MessageLevel.INFO
    message_id: bytes | None = field(default_factory=create_id)
    timeout_ms: int = 10_000
    desktop: bool = False
