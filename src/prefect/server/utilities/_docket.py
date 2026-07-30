"""Access to the running server's `Docket` for code without a request or task context."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from docket import Docket
from docket.dependencies import current_docket

_server_docket: Docket | None = None


@contextmanager
def serving_docket(docket: Docket) -> Generator[None, None, None]:
    """Publish `docket` as the docket this process uses for background work."""
    global _server_docket

    previous, _server_docket = _server_docket, docket
    try:
        yield
    finally:
        _server_docket = previous


def get_docket() -> Docket | None:
    """The docket this process should use for background work, if it has one.

    Inside a docket task this is the docket that scheduled the task; otherwise it's the
    docket that the server, if one is running in this process, is serving. Code that may
    also run outside of a server (for example, the orchestration engine driven directly
    against a session) has to handle `None`.
    """
    return current_docket.get(None) or _server_docket
