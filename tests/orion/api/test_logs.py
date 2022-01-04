from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.sorting import LogSort


NOW = pendulum.now("UTC")
CREATE_LOGS_URL = "/logs/"
READ_LOGS_URL = "/logs/filter"


@pytest.fixture
def flow_run_id():
    yield str(uuid4())


@pytest.fixture
def task_run_id():
    yield str(uuid4())


@pytest.fixture
def log_data(client, flow_run_id, task_run_id):
    yield [
        {
            "name": "prefect.flow_run",
            "level": 20,
            "message": "Ahoy, captain",
            "timestamp": NOW.timestamp(),
            "flow_run_id": flow_run_id,
        },
        {
            "name": "prefect.task_run",
            "level": 50,
            "message": "Black flag ahead, captain!",
            "timestamp": NOW.timestamp(),
            "flow_run_id": flow_run_id,
            "task_run_id": task_run_id,
        },
    ]


def assert_is_same_log(model, api_data):
    assert model.name == api_data["name"]
    assert model.level == api_data["level"]
    assert model.message == api_data["message"]
    assert model.timestamp == pendulum.from_timestamp(api_data["timestamp"]).astimezone(
        pendulum.timezone("UTC")
    )
    assert str(model.flow_run_id) == api_data["flow_run_id"]

    if model.task_run_id:
        assert str(model.task_run_id) == api_data["task_run_id"]


class TestCreateLogs:
    async def test_create_logs_with_flow_run_id_and_returns_number_created(
        self, session, client, log_data, flow_run_id
    ):
        response = await client.post(CREATE_LOGS_URL, json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(flow_run_id={"any_": [flow_run_id]})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)
        assert len(logs) == 2

        for i, log in enumerate(logs):
            assert_is_same_log(log, log_data[i])

    async def test_create_logs_with_task_run_id_and_returns_number_created(
        self, session, client, flow_run_id, task_run_id, log_data
    ):
        response = await client.post(CREATE_LOGS_URL, json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(task_run_id={"any_": [task_run_id]})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)
        assert len(logs) == 1

        assert_is_same_log(logs[0], log_data[1])


class TestReadLogs:
    @pytest.fixture()
    async def logs(self, client, log_data):
        await client.post(CREATE_LOGS_URL, json=log_data)

    async def test_read_logs(self, client, logs):
        response = await client.post(READ_LOGS_URL)
        assert len(response.json()) == 2

    async def test_read_logs_applies_log_filter(
        self, logs, log_data, client, task_run_id
    ):
        log_filter = {"logs": {"task_run_id": {"any_": [task_run_id]}}}
        response = await client.post(READ_LOGS_URL, json=log_filter)
        data = response.json()
        assert len(data) == 1
        for log in data:
            assert log["task_run_id"] == task_run_id

    async def test_read_logs_offset(self, client, logs):
        response = await client.post(READ_LOGS_URL, json={"offset": 1, "limit": 1})
        data = response.json()
        assert len(data) == 1

    async def test_read_logs_returns_empty_list(self, client):
        response = await client.post(READ_LOGS_URL)
        data = response.json()
        assert data == []
