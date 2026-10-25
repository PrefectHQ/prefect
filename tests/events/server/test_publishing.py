from typing import AsyncGenerator
from uuid import uuid4

import pytest
import sqlalchemy as sa
from docket import Docket, Worker
from docket.testing import assert_task_scheduled

from prefect.server.database import PrefectDBInterface
from prefect.server.events._publishing import publish_after_commit, publish_event
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.schemas.events import Event, Resource
from prefect.server.utilities._docket import serving_docket
from prefect.types._datetime import now


@pytest.fixture
def event() -> Event:
    return Event(
        id=uuid4(),
        occurred=now("UTC"),
        event="prefect.flow-run.Running",
        resource=Resource({"prefect.resource.id": f"prefect.flow-run.{uuid4()}"}),
    )


@pytest.fixture
async def docket() -> AsyncGenerator[Docket, None]:
    async with Docket(name=f"test-docket-{uuid4().hex[:8]}", url="memory://") as docket:
        docket.register(publish_event)
        yield docket


async def test_publishing_in_line_without_a_docket(
    db: PrefectDBInterface, event: Event
):
    async with db.session_context(begin_transaction=True) as session:
        await session.execute(sa.text("SELECT 1"))
        publish_after_commit(session, event)

        assert not AssertingEventsClient.all

    assert AssertingEventsClient.last
    assert AssertingEventsClient.last.events == [event]


async def test_publishing_with_a_docket_task(
    db: PrefectDBInterface, docket: Docket, event: Event
):
    with serving_docket(docket):
        async with db.session_context(begin_transaction=True) as session:
            await session.execute(sa.text("SELECT 1"))
            publish_after_commit(session, event)

    # the commit only enqueues the task, so nothing has been published yet
    assert not AssertingEventsClient.all
    await assert_task_scheduled(docket, publish_event, key=f"publish-event:{event.id}")

    async with Worker(docket) as worker:
        await worker.run_until_finished()

    assert AssertingEventsClient.last
    assert AssertingEventsClient.last.events == [event]


async def test_rolled_back_transitions_are_never_enqueued(
    db: PrefectDBInterface, docket: Docket, event: Event
):
    with serving_docket(docket):
        async with db.session_context() as session:
            await session.execute(sa.text("SELECT 1"))
            publish_after_commit(session, event)
            await session.rollback()
            await session.commit()

    async with Worker(docket) as worker:
        await worker.run_until_finished()

    assert not AssertingEventsClient.all


async def test_failing_to_enqueue_does_not_fail_the_commit(
    db: PrefectDBInterface,
    docket: Docket,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
):
    def explode(*args: object, **kwargs: object) -> None:
        raise ConnectionError("docket is unreachable")

    monkeypatch.setattr(docket, "add", explode)

    flow_id = uuid4()
    with serving_docket(docket):
        async with db.session_context(begin_transaction=True) as session:
            await session.execute(
                sa.insert(db.Flow).values(id=flow_id, name=f"flow-{flow_id}")
            )
            publish_after_commit(session, event)

    # the state, or whatever else the transaction wrote, is still committed
    async with db.session_context() as session:
        assert await session.get(db.Flow, flow_id)

    assert not AssertingEventsClient.all
