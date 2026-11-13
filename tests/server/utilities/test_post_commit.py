import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.utilities._post_commit import call_after_commit


async def test_hooks_are_called_after_the_commit(session: AsyncSession):
    called: list[str] = []

    async def hook() -> None:
        called.append("hook")

    call_after_commit(session, hook)

    assert called == []

    await session.commit()

    assert called == ["hook"]


async def test_hooks_are_called_in_order_and_only_once(session: AsyncSession):
    called: list[int] = []

    def hook_for(i: int):
        async def hook() -> None:
            called.append(i)

        return hook

    for i in range(3):
        call_after_commit(session, hook_for(i))

    await session.commit()
    await session.commit()

    assert called == [0, 1, 2]


async def test_hooks_are_discarded_on_rollback(session: AsyncSession):
    called: list[str] = []

    async def hook() -> None:
        called.append("hook")

    await session.execute(sa.text("SELECT 1"))
    call_after_commit(session, hook)

    await session.rollback()
    await session.commit()

    assert called == []


async def test_hooks_are_called_when_a_transaction_context_commits(
    db: PrefectDBInterface,
):
    called: list[str] = []

    async def hook() -> None:
        called.append("hook")

    async with db.session_context(begin_transaction=True) as session:
        call_after_commit(session, hook)
        assert called == []

    assert called == ["hook"]


async def test_failing_hooks_do_not_fail_the_commit(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
):
    called: list[str] = []

    async def exploding_hook() -> None:
        raise ValueError("nope")

    async def hook() -> None:
        called.append("hook")

    call_after_commit(session, exploding_hook)
    call_after_commit(session, hook)

    await session.commit()

    assert called == ["hook"]
    assert "Error while running post-commit hook" in caplog.text


async def test_hooks_wait_for_the_enclosing_transaction_of_a_savepoint(
    db: PrefectDBInterface,
):
    called: list[str] = []

    async def hook() -> None:
        called.append("hook")

    async with db.session_context(begin_transaction=True) as session:
        async with session.begin_nested():
            await session.execute(sa.text("SELECT 1"))
            call_after_commit(session, hook)

        # releasing the savepoint is not durable on its own
        assert called == []

    assert called == ["hook"]


async def test_hooks_are_discarded_when_their_savepoint_rolls_back(
    db: PrefectDBInterface,
):
    called: list[str] = []

    async def hook() -> None:
        called.append("hook")

    async with db.session_context(begin_transaction=True) as session:
        nested = await session.begin_nested()
        await session.execute(sa.text("SELECT 1"))
        call_after_commit(session, hook)
        await nested.rollback()

    assert called == []


async def test_hooks_survive_the_rollback_of_a_later_savepoint(
    db: PrefectDBInterface,
):
    called: list[str] = []

    async def hook() -> None:
        called.append("hook")

    async with db.session_context(begin_transaction=True) as session:
        await session.execute(sa.text("SELECT 1"))
        call_after_commit(session, hook)

        nested = await session.begin_nested()
        await session.execute(sa.text("SELECT 1"))
        await nested.rollback()

    assert called == ["hook"]
