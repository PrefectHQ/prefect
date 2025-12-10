"""Tests for the pause_expirations docket task functions."""

from datetime import datetime, timedelta, timezone

import pytest

from prefect.server import models, schemas
from prefect.server.services.pause_expirations import fail_expired_pause

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


async def test_fails_expired_pause(session, expired_pause, db):
    assert expired_pause.state.type == "PAUSED"
    await fail_expired_pause(expired_pause.id, str(THE_PAST), db=db)
    await session.refresh(expired_pause)
    assert expired_pause.state.type == "FAILED"


async def test_does_not_fail_active_pause(session, active_pause, db):
    assert active_pause.state.type == "PAUSED"
    await fail_expired_pause(active_pause.id, str(THE_FUTURE), db=db)
    await session.refresh(active_pause)
    assert active_pause.state.type == "PAUSED"


async def test_fails_multiple_expired_pauses(
    session, expired_pause, expired_pause_2, db
):
    assert expired_pause.state.type == "PAUSED"
    assert expired_pause_2.state.type == "PAUSED"

    await fail_expired_pause(expired_pause.id, str(THE_PAST), db=db)
    await fail_expired_pause(expired_pause_2.id, str(THE_PAST), db=db)

    await session.refresh(expired_pause)
    await session.refresh(expired_pause_2)

    assert expired_pause.state.type == "FAILED"
    assert expired_pause_2.state.type == "FAILED"


async def test_handles_deleted_flow_run(db):
    """Test that fail_expired_pause handles missing flow runs gracefully."""
    from uuid import uuid4

    # Should not raise an error
    await fail_expired_pause(uuid4(), str(THE_PAST), db=db)


async def test_ignores_non_paused_flow_run(session, flow, db):
    """Test that fail_expired_pause ignores flow runs that are not paused."""
    async with session.begin():
        running_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Running(),
            ),
        )

    await fail_expired_pause(running_flow_run.id, str(THE_PAST), db=db)
    await session.refresh(running_flow_run)
    assert running_flow_run.state.type == "RUNNING"
