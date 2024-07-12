"""Useful log utilities."""

from collections.abc import Callable
from datetime import datetime, timezone
import logging.config
from pathlib import Path
import sys
from types import TracebackType
from typing import Any

from tenacity import RetryCallState

CURRENT_DIR = Path(__file__).parent
CONFIG_PATH = CURRENT_DIR.parent.joinpath("log_config.ini")


def setup_logging() -> None:
    """Set logging for the app based on config."""
    if not CONFIG_PATH.exists():
        create_default_config()

    log_path = Path(
        CONFIG_PATH.parent.joinpath("logs").joinpath(
            datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S.log"),
        ),
    )
    logging.config.fileConfig(
        CONFIG_PATH,
        defaults={
            "log_path": f"{log_path.absolute()}",
        },
        disable_existing_loggers=False,
    )

    sys.excepthook = log_uncaught_exceptions


def create_default_config() -> None:
    """Create default logging config."""
    config_content = """[loggers]
keys=root,plutus_terminal

[handlers]
keys=consoleHandler, fileHandler

[logger_root]
level=ERROR
handlers=consoleHandler

[logger_plutus_terminal]
level=DEBUG
handlers=consoleHandler, fileHandler
qualname=plutus_terminal
propagate=0

[formatters]
keys=detailed, sampleFormatter

[formatter_detailed]
format=%(asctime)s [%(levelname)s] %(name)s: %(message)s

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=detailed
args=(sys.stdout,)
encoding=utf-8

[handler_fileHandler]
class=FileHandler
level=DEBUG
formatter=sampleFormatter
args=(r"%(log_path)s", "a", "utf-8")

[formatter_sampleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
"""

    with Path.open(CONFIG_PATH, "w") as f:
        f.write(config_content)

    if not CONFIG_PATH.parent.joinpath("logs").exists():
        Path.mkdir(CONFIG_PATH.parent.joinpath("logs"), parents=True)


def log_uncaught_exceptions(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> Any:  # noqa: ANN401
    """Log uncaught exceptions.

    Args:
        exc_type (type[BaseException]): Exception type.
        exc_value (BaseException): Exception value.
        exc_traceback (TracebackType): Exception traceback.
    """
    logger = logging.getLogger("plutus_terminal")
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def log_retry(logger: logging.Logger) -> Callable[[RetryCallState], None]:
    """Log warning after a retry happens.

    Returns:
        Callable[[RetryCallState], None]: Logging function.
    """

    def _log_retry(retry_state: RetryCallState) -> None:
        logger.warning(
            f"{retry_state.fn} failed after {retry_state.attempt_number} attempts"  # noqa: G004
            f"with exception: {retry_state.outcome.exception()}.",  # type: ignore
        )

    return _log_retry
