"""Small standard-library compatibility helpers for supported Python versions."""

from __future__ import annotations

from enum import Enum
from typing import NoReturn


class StrEnum(str, Enum):
    """Python 3.10-compatible subset of the standard-library ``StrEnum``."""

    def __new__(cls, value: object) -> StrEnum:
        if not isinstance(value, str):
            raise TypeError(f"{value!r} is not a string")
        member = str.__new__(cls, value)
        member._value_ = value
        return member

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[object]) -> str:
        return name.lower()

    def __str__(self) -> str:
        return str.__str__(self)


def assert_never(value: NoReturn) -> NoReturn:
    """Fail at runtime while preserving exhaustive-branch checking under mypy."""

    raise AssertionError(f"expected unreachable value, got {value!r}")
