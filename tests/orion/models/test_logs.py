from datetime import timedelta
from uuid import uuid4

import pendulum
import pytest
from sqlalchemy import select

from prefect.orion import models
from prefect.orion.schemas.actions import LogCreate
from prefect.orion.schemas.core import Log
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.sorting import LogSort

NOW = pendulum.now("UTC")


@pytest.fixture
def flow_run_id():
    yield uuid4()


@pytest.fixture
def task_run_id():
    yield uuid4()


@pytest.fixture
def other_flow_run_id():
    yield uuid4()


@pytest.fixture
def log_data(client, flow_run_id, task_run_id, other_flow_run_id):
    yield [
        LogCreate(
            name="prefect.flow_run",
            level=10,
            message="Ahoy, captain",
            timestamp=NOW,
            flow_run_id=flow_run_id,
        ),
        LogCreate(
            name="prefect.flow_run",
            level=20,
            message="Aye-aye, captain!",
            timestamp=(NOW + timedelta(minutes=1)),
            flow_run_id=flow_run_id,
        ),
        LogCreate(
            name="prefect.task_run",
            level=50,
            message="Black flag ahead, captain!",
            timestamp=(NOW + timedelta(hours=1)),
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
        ),
    ]


@pytest.fixture
async def logs(log_data, session):
    await models.logs.create_logs(session=session, logs=log_data)


class TestCreateLogs:
    async def test_create_logs_succeeds(self, session, flow_run_id, log_data, logs, db):
        query = select(db.Log).order_by(db.Log.timestamp.asc())
        result = await session.execute(query)
        read_logs = result.scalars().unique().all()

        for i, log in enumerate(read_logs):
            assert (
                Log.from_orm(log).dict(exclude={"created", "id", "updated"})
                == log_data[i]
            )


class TestReadLogs:
    async def test_read_logs_level(self, session, logs):
        log_filter = LogFilter(level={"le_": 40})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.LEVEL_ASC
        )
        assert len(logs) == 2
        assert [10, 20] == [log.level for log in logs]

    async def test_read_logs_timestamp_after_inclusive(self, session, logs, log_data):
        after = log_data[1].timestamp
        log_filter = LogFilter(timestamp={"after_": after})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.TIMESTAMP_ASC
        )
        assert len(logs) == 2

        # We get a log with the same timestamp as the given timestamp.
        assert logs[0].timestamp == after
        # We get a log with a timestamp after the given timestamp.
        assert logs[1].timestamp > after

    async def test_read_logs_timestamp_before_inclusive(self, session, logs, log_data):
        before = log_data[1].timestamp
        log_filter = LogFilter(timestamp={"before_": before})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.TIMESTAMP_ASC
        )
        assert len(logs) == 2

        # We get a log with a timestamp before the given timestamp.
        assert logs[0].timestamp < before
        # We get a log with the same timestamp as the given timestamp.
        assert logs[1].timestamp == before

    async def test_read_logs_flow_run_id(self, session, logs, flow_run_id):
        log_filter = LogFilter(flow_run_id={"any_": [flow_run_id]})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)

        assert len(logs) == 3
        assert all([log.flow_run_id == flow_run_id for log in logs])

    async def test_read_logs_task_run_id(self, session, logs, task_run_id):
        log_filter = LogFilter(task_run_id={"any_": [task_run_id]})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)

        assert len(logs) == 1
        assert all([log.task_run_id == task_run_id for log in logs])
