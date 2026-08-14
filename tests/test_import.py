"""Package-level smoke tests."""

from refcompat import __version__


def test_package_exposes_version() -> None:
    assert __version__
