"""Cerbos authorization middleware for FastMCP."""

from importlib import metadata as _metadata

from .middleware import (
    CerbosAuthorizationMiddleware,
    PrincipalBuilder,
)

__all__ = [
    "CerbosAuthorizationMiddleware",
    "PrincipalBuilder",
    "__version__",
]

try:  # pragma: no cover - used for packaging metadata
    __version__ = _metadata.version("cerbos-fastmcp")
except _metadata.PackageNotFoundError:  # pragma: no cover - during local dev
    __version__ = "0.0.dev0"
