"""Deploy CLI package entry."""

from ._commands import deploy_app, init  # noqa: F401

__all__ = ["deploy_app", "init"]
