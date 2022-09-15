"""
Tests for the logs API.

NOTE: These tests use UUID1 to generate UUIDs with a stable sorted
order. This is purely so that we can test sorting by flow run and
task run ID with a stable order across test machines.
"""

from datetime import timedelta
from unittest import mock
from uuid import UUID, uuid1

import pendulum
import pytest
from sqlalchemy.orm.exc import FlushError

from prefect.orion import models
from prefect.orion.schemas.actions import LogCreate
from prefect.orion.schemas.core import Log
from prefect.orion.schemas.filters import LogFilter

NOW = pendulum.now("UTC")
CREATE_LOGS_URL = "/logs/"
READ_LOGS_URL = "/logs/filter"


@pytest.fixture
def flow_run_id():
    yield uuid1()


@pytest.fixture
def task_run_id():
    yield uuid1()


@pytest.fixture
def log_data(client, flow_run_id, task_run_id):
    yield [
        LogCreate(
            name="prefect.flow_run",
            level=20,
            message="Ahoy, captain",
            timestamp=NOW,
            flow_run_id=flow_run_id,
        ).dict(json_compatible=True),
        LogCreate(
            name="prefect.task_run",
            level=50,
            message="Black flag ahead, captain!",
            timestamp=(NOW + timedelta(hours=1)),
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
        ).dict(json_compatible=True),
    ]


class TestCreateLogs:
    async def test_create_logs_with_flow_run_id_and_returns_number_created(
        self, session, client, log_data, flow_run_id
    ):
        response = await client.post(CREATE_LOGS_URL, json=log_data)
        assert response.status_code == 201

        log_filter = LogFilter(flow_run_id={"any_": [flow_run_id]})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)
        assert len(logs) == 2

        for i, log in enumerate(logs):
            assert (
                Log.from_orm(log).dict(
                    json_compatible=True, exclude={"created", "id", "updated"}
                )
                == log_data[i]
            )

    async def test_create_logs_with_task_run_id_and_returns_number_created(
        self, session, client, flow_run_id, task_run_id, log_data
    ):
        response = await client.post(CREATE_LOGS_URL, json=log_data)
        assert response.status_code == 201

        log_filter = LogFilter(task_run_id={"any_": [task_run_id]})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)
        assert len(logs) == 1

        assert (
            Log.from_orm(logs[0]).dict(
                json_compatible=True, exclude={"created", "id", "updated"}
            )
            == log_data[1]
        )

    async def test_database_failure(
        self, client_without_exceptions, session, flow_run_id, task_run_id, log_data
    ):
        with mock.patch("prefect.orion.models.logs.create_logs") as mock_create_logs:

            def raise_error(*args, **kwargs):
                raise FlushError

            mock_create_logs.side_effect = raise_error
            response = await client_without_exceptions.post(
                CREATE_LOGS_URL, json=log_data
            )
            assert response.status_code == 500


class TestReadLogs:
    @pytest.fixture()
    async def logs(self, client, log_data):
        await client.post(CREATE_LOGS_URL, json=log_data)

    @pytest.fixture()
    async def single_flow_run_log(self, client):
        flow_run_logs = [
            LogCreate(
                name="prefect.flow_run",
                level=80,
                message="Full speed ahead!",
                timestamp=NOW,
                flow_run_id=uuid1(),
            ).dict(json_compatible=True)
        ]
        await client.post(CREATE_LOGS_URL, json=flow_run_logs)
        yield flow_run_logs[0]

    @pytest.fixture()
    async def single_task_run_log(self, client):
        flow_run_logs = [
            LogCreate(
                name="prefect.flow_run",
                level=80,
                message="Full speed ahead!",
                timestamp=NOW,
                flow_run_id=uuid1(),
                task_run_id=uuid1(),
            ).dict(json_compatible=True)
        ]
        await client.post(CREATE_LOGS_URL, json=flow_run_logs)
        yield flow_run_logs[0]

    async def test_read_logs(self, client, logs):
        response = await client.post(READ_LOGS_URL)
        assert len(response.json()) == 2

    async def test_read_logs_applies_log_filter(
        self, logs, log_data, client, task_run_id
    ):
        log_filter = {"logs": {"task_run_id": {"any_": [str(task_run_id)]}}}
        response = await client.post(READ_LOGS_URL, json=log_filter)
        data = response.json()
        assert len(data) == 1
        for log in data:
            assert log["task_run_id"] == str(task_run_id)

    async def test_read_logs_offset(self, client, logs):
        response = await client.post(READ_LOGS_URL, json={"offset": 1, "limit": 1})
        data = response.json()
        assert len(data) == 1

    async def test_read_logs_returns_empty_list(self, client):
        response = await client.post(READ_LOGS_URL)
        data = response.json()
        assert data == []

    async def test_read_logs_sort_by_timestamp_asc(self, client, logs):
        response = await client.post(READ_LOGS_URL, json={"sort": "TIMESTAMP_ASC"})
        api_logs = [Log(**log_data) for log_data in response.json()]
        assert api_logs[0].timestamp < api_logs[1].timestamp
        assert api_logs[0].message == "Ahoy, captain"

    async def test_read_logs_sort_by_timestamp_desc(self, client, logs):
        response = await client.post(READ_LOGS_URL, json={"sort": "TIMESTAMP_DESC"})
        api_logs = [Log(**log_data) for log_data in response.json()]
        assert api_logs[0].timestamp > api_logs[1].timestamp
        assert api_logs[0].message == "Black flag ahead, captain!"

    async def test_read_logs_sort_by_level_asc(self, client, logs):
        response = await client.post(READ_LOGS_URL, json={"sort": "LEVEL_ASC"})
        data = response.json()
        assert data[0]["level"] < data[1]["level"]
        assert data[0]["message"] == "Ahoy, captain"

    async def test_read_logs_sort_by_level_desc(self, client, logs):
        response = await client.post(READ_LOGS_URL, json={"sort": "LEVEL_DESC"})
        data = response.json()
        assert data[0]["level"] > data[1]["level"]
        assert data[0]["message"] == "Black flag ahead, captain!"

    async def test_read_logs_sort_by_flow_run_id_asc(
        self, client, logs, flow_run_id, single_flow_run_log
    ):
        response = await client.post(READ_LOGS_URL, json={"sort": "FLOW_RUN_ID_ASC"})
        api_logs = [Log(**log_data) for log_data in response.json()]
        assert api_logs[0].flow_run_id == flow_run_id
        assert api_logs[-1].flow_run_id == UUID(single_flow_run_log["flow_run_id"])
        assert api_logs[0].flow_run_id < api_logs[-1].flow_run_id

    async def test_read_logs_sort_by_flow_run_id_desc(
        self, client, logs, flow_run_id, single_flow_run_log
    ):
        response = await client.post(READ_LOGS_URL, json={"sort": "FLOW_RUN_ID_DESC"})
        api_logs = [Log(**log_data) for log_data in response.json()]
        assert api_logs[0].flow_run_id == UUID(single_flow_run_log["flow_run_id"])
        assert api_logs[-1].flow_run_id == flow_run_id
        assert api_logs[0].flow_run_id > api_logs[-1].flow_run_id

    async def test_read_logs_sort_by_task_run_id_asc(
        self, client, logs, task_run_id, single_task_run_log
    ):
        log_filter = {
            "logs": {
                "task_run_id": {
                    "any_": [str(task_run_id), single_task_run_log["task_run_id"]]
                }
            },
            "sort": "TASK_RUN_ID_ASC",
        }
        response = await client.post(READ_LOGS_URL, json=log_filter)
        api_logs = [Log(**log_data) for log_data in response.json()]
        assert api_logs[0].task_run_id == task_run_id
        assert api_logs[-1].task_run_id == UUID(single_task_run_log["task_run_id"])
        assert api_logs[0].task_run_id < api_logs[-1].task_run_id

    async def test_read_logs_sort_by_task_run_id_desc(
        self, client, logs, task_run_id, single_task_run_log
    ):
        log_filter = {
            "logs": {
                "task_run_id": {
                    "any_": [str(task_run_id), single_task_run_log["task_run_id"]]
                }
            },
            "sort": "TASK_RUN_ID_DESC",
        }
        response = await client.post(READ_LOGS_URL, json=log_filter)
        api_logs = [Log(**log_data) for log_data in response.json()]
        assert api_logs[0].task_run_id == UUID(single_task_run_log["task_run_id"])
        assert api_logs[-1].task_run_id == task_run_id
        assert api_logs[0].task_run_id > api_logs[-1].task_run_id
