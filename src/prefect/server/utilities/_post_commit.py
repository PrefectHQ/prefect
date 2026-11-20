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
    they observe or publish reflects the committed data. A hook belongs to the
    transaction that is active when it is registered, and is discarded if that
    transaction, or any transaction enclosing it, is rolled back.

    Args:
        session: the session whose commit the hook should follow
        hook: a no-argument coroutine function to await after the commit
    """
    sync_session = session.sync_session

    hooks = _hooks(sync_session)
    if hooks is None:
        hooks = sync_session.info[_HOOKS] = []
        event.listen(sync_session, "after_commit", _call_hooks)
        event.listen(sync_session, "after_soft_rollback", _discard_hooks)

    transaction = (
        sync_session.get_nested_transaction() or sync_session.get_transaction()
    )
    hooks.append((transaction, hook))


def _hooks(
    session: Session,
) -> list[tuple[SessionTransaction | None, PostCommitHook]] | None:
    return session.info.get(_HOOKS)


def _call_hooks(session: Session) -> None:
    if session.in_nested_transaction():
        # releasing a savepoint isn't durable until the enclosing transaction commits
        return

    hooks = _hooks(session) or []
    while hooks:
        _, hook = hooks.pop(0)
        try:
            # `after_commit` is emitted from within the greenlet that the async
            # session used to commit, so the hook runs on the original event loop
            await_only(hook())
        except Exception:
            logger.exception("Error while running post-commit hook %r", hook)


def _discard_hooks(session: Session, previous_transaction: SessionTransaction) -> None:
    hooks = _hooks(session)
    if not hooks:
        return

    hooks[:] = [
        (transaction, hook)
        for transaction, hook in hooks
        if not _within(transaction, previous_transaction)
    ]


def _within(
    transaction: SessionTransaction | None, ancestor: SessionTransaction
) -> bool:
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False
