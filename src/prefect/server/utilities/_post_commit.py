"""Utilities for deferring asynchronous work until a session's transaction commits."""

from __future__ import annotations

from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.util import await_only

from prefect.logging import get_logger

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

PostCommitHook = Callable[[], Coroutine[Any, Any, None]]

_HOOKS: str = "prefect_post_commit_hooks"


def call_after_commit(session: AsyncSession, hook: PostCommitHook) -> None:
    """Call `hook` after the session's transaction commits.

    Hooks are awaited on the session's event loop as the commit unwinds, so anything
    they observe or publish reflects the committed data. Hooks registered against a
    transaction that is rolled back or never committed are never called.

    Args:
        session: the session whose commit the hook should follow
        hook: a no-argument coroutine function to await after the commit
    """
    sync_session = session.sync_session

    hooks: list[PostCommitHook] | None = sync_session.info.get(_HOOKS)
    if hooks is None:
        hooks = sync_session.info[_HOOKS] = []
        event.listen(sync_session, "after_commit", _call_hooks)
        event.listen(sync_session, "after_soft_rollback", _discard_hooks)

    hooks.append(hook)


def _call_hooks(session: Session) -> None:
    if session.in_nested_transaction():
        # releasing a savepoint isn't durable until the enclosing transaction commits
        return

    hooks: list[PostCommitHook] = session.info.get(_HOOKS, [])
    while hooks:
        hook = hooks.pop(0)
        try:
            # `after_commit` is emitted from within the greenlet that the async
            # session used to commit, so the hook runs on the original event loop
            await_only(hook())
        except Exception:
            logger.exception("Error while running post-commit hook %r", hook)


def _discard_hooks(session: Session, previous_transaction: SessionTransaction) -> None:
    if previous_transaction.nested:
        # rolling back to a savepoint leaves the enclosing transaction intact
        return
    session.info.get(_HOOKS, []).clear()
