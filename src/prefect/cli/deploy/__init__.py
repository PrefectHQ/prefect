"""Deploy CLI package entry.

Exports the public CLI commands and a minimal set of compatibility shims.
"""

from .commands import deploy, init  # noqa: F401
from .storage import _PullStepStorage  # noqa: F401 (compat import used in tests)

__all__ = ["deploy", "init", "_PullStepStorage"]
