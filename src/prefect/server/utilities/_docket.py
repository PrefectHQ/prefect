"""Access to the running server's `Docket` for code without a request or task context."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from docket import Docket
from docket.dependencies import current_docket

_server_dockets: dict[object, Docket] = {}


@contextmanager
def serving_docket(docket: Docket) -> Generator[None, None, None]:
    """Make `docket` available for background work while its server is running."""
    # Lifespans can overlap without exiting in nesting order. Track each entry
    # separately, even when multiple lifespans serve the same docket.
    token = object()
    _server_dockets[token] = docket
    try:
        yield
    finally:
        del _server_dockets[token]


def get_docket() -> Docket | None:
    """The docket this process should use for background work, if it has one.

    Inside a docket task this is the docket that scheduled the task; otherwise it's the
    most recently started docket whose server is still running in this process.
    Code that may also run outside of a server (for example, the orchestration engine
    driven directly against a session) has to handle `None`.
    """
    return current_docket.get(None) or next(reversed(_server_dockets.values()), None)
