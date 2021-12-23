import logging
from datetime import timedelta

import pendulum
import sqlalchemy as sa


async def test_create_log_with_extras(session, db):
    now = pendulum.now("UTC")
    fifteen_mins_ago = now - timedelta(minutes=15)

    log = db.Log(
        name="prefect.flow_run",
        level=logging.INFO,
        message="Ahoy, captain",
        timestamp=now,
        extra_attributes={"flow_id": 1}
    )

    session.add(log)
    await session.flush()

    query = (
        sa.select(db.Log)
        .where(db.Log.timestamp > fifteen_mins_ago)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    assert result.scalar() == log


async def test_create_log_without_extras(session, db):
    now = pendulum.now("UTC")
    fifteen_mins_ago = now - timedelta(minutes=15)

    log = db.Log(
        name="prefect.flow_run",
        level=logging.WARNING,
        message="Black flag ahead, captain!",
        timestamp=now
    )

    session.add(log)
    await session.flush()

    query = (
        sa.select(db.Log)
        .where(db.Log.timestamp > fifteen_mins_ago)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    assert result.scalar() == log
