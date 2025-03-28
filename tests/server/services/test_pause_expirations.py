from datetime import datetime, timedelta, timezone

import pytest

from prefect.server import models, schemas
from prefect.server.services.pause_expirations import FailExpiredPauses

THE_PAST = datetime.now(timezone.utc) - timedelta(hours=5)
THE_FUTURE = datetime.now(timezone.utc) + timedelta(days=5)


@pytest.fixture
async def expired_pause(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Paused(pause_expiration_time=THE_PAST),
            ),
        )


@pytest.fixture
async def expired_pause_2(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Paused(pause_expiration_time=THE_PAST),
            ),
        )


@pytest.fixture
async def active_pause(session, flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Paused(pause_expiration_time=THE_FUTURE),
            ),
        )


async def test_fails_expired_pause(session, expired_pause):
    assert expired_pause.state.type == "PAUSED"
    await FailExpiredPauses().start(loops=1)
    await session.refresh(expired_pause)
    assert expired_pause.state.type == "FAILED"


async def test_does_not_fail_active_pause(session, active_pause):
    assert active_pause.state.type == "PAUSED"
    await FailExpiredPauses().start(loops=1)
    await session.refresh(active_pause)
    assert active_pause.state.type == "PAUSED"


async def test_fails_multiple_expired_pauses(session, expired_pause, expired_pause_2):
    assert expired_pause.state.type == "PAUSED"
    assert expired_pause_2.state.type == "PAUSED"

    await FailExpiredPauses().start(loops=1)

    await session.refresh(expired_pause)
    await session.refresh(expired_pause_2)

    assert expired_pause.state.type == "FAILED"
    assert expired_pause_2.state.type == "FAILED"
