"""Regression tests for the small Python 3.10 compatibility surface."""

from __future__ import annotations

import json
from enum import auto

import pytest

from refcompat._compat import StrEnum


class _Example(StrEnum):
    VALUE = "value"


def test_internal_str_enum_matches_required_stdlib_behavior() -> None:
    member = _Example.VALUE

    assert isinstance(member, str)
    assert member == "value"
    assert str(member) == "value"
    assert f"{member}" == "value"
    assert json.dumps(member) == '"value"'


def test_internal_str_enum_rejects_non_string_member_values() -> None:
    with pytest.raises(TypeError, match="is not a string"):

        class _Invalid(StrEnum):
            VALUE = 1


def test_internal_str_enum_auto_matches_stdlib_behavior() -> None:
    class _Automatic(StrEnum):
        FIRST_VALUE = auto()
        SECOND_VALUE = auto()

    assert _Automatic.FIRST_VALUE.value == "first_value"
    assert _Automatic.SECOND_VALUE.value == "second_value"
