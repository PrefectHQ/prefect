"""
Tests for the logs API.

NOTE: These tests use UUID1 to generate UUIDs with a stable sorted
order. This is purely so that we can test sorting by flow run and
task run ID with a stable order across test machines.
"""

from datetime import timedelta
from unittest import mock
from unittest.mock import patch
from uuid import uuid1

import pytest
from sqlalchemy.orm.exc import FlushError

from prefect.server import models
from prefect.server.schemas.actions import LogCreate
from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import LogFilter
from prefect.types._datetime import now

NOW = now("UTC")
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
        ).model_dump(mode="json"),
        LogCreate(
            name="prefect.task_run",
            level=50,
            message="Black flag ahead, captain!",
            timestamp=(NOW + timedelta(hours=1)),
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
        ).model_dump(mode="json"),
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
                Log.model_validate(log, from_attributes=True).model_dump(
                    mode="json", exclude={"created", "id", "updated"}
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
            Log.model_validate(logs[0], from_attributes=True).model_dump(
                mode="json", exclude={"created", "id", "updated"}
            )
            == log_data[1]
        )

    async def test_database_failure(
        self, client_without_exceptions, session, flow_run_id, task_run_id, log_data
    ):
        with mock.patch("prefect.server.models.logs.create_logs") as mock_create_logs:

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
            ).model_dump(mode="json")
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
            ).model_dump(mode="json")
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


class TestLogSchemaConversionAPI:
    """Test the API endpoint converts LogCreate to Log objects for messaging"""

    async def test_post_logs_api_converts_logcreate_to_log_for_messaging(
        self, client, flow_run_id
    ):
        """Test posting LogCreate to API results in Log objects passed to publish_logs"""
        log_create_data = LogCreate(
            name="test.api.logger",
            level=20,
            message="API test message",
            timestamp=NOW,
            flow_run_id=flow_run_id,
        ).model_dump(mode="json")

        # Mock publish_logs to capture what gets passed to messaging
        with patch("prefect.server.logs.messaging.publish_logs") as mock_publish:
            response = await client.post(CREATE_LOGS_URL, json=[log_create_data])

            # API should succeed
            assert response.status_code == 201

            # Verify publish_logs was called with Log objects that have IDs
            mock_publish.assert_called_once()
            published_logs = mock_publish.call_args[0][0]

            assert len(published_logs) == 1
            published_log = published_logs[0]

            # This was the key issue: API accepts LogCreate but messaging needs Log with ID
            assert isinstance(published_log, Log)
            assert published_log.id is not None

            # Core fields should match the original API input
            assert published_log.name == "test.api.logger"
            assert published_log.level == 20
            assert published_log.message == "API test message"
            assert published_log.flow_run_id == flow_run_id
