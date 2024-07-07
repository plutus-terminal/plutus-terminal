"""Utilities for UI."""

import math

from PySide6.QtCore import QDir, QResource


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


def list_resources_from_prefix(prefix: str) -> list[str]:
    """List all resources of the given prefix."""
    qdir = QDir(":/")
    qdir.setFilter(QDir.Filter.Files | QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)

    qdir.setPath(qdir.filePath(prefix))

    entries = qdir.entryList()

    resources = []
    for entry in entries:
        path = f":/{prefix}/{entry}"
        if QResource(path).isFile():
            resources.append(path)
        elif QResource(path).isDir():
            resources.extend(list_resources_from_prefix(f"{prefix}/{entry}"))

    return resources
