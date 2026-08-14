"""Genomic reference and resource compatibility reasoning."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("refcompat")
except PackageNotFoundError:  # pragma: no cover - source-tree fallback outside an installed env
    __version__ = "0+unknown"

__all__ = ["__version__"]
