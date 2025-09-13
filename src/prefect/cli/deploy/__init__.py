"""Deploy CLI package entry.

Exports the public CLI commands and a minimal set of compatibility shims.
"""

from ._commands import deploy, init  # noqa: F401

__all__ = ["deploy", "init"]
