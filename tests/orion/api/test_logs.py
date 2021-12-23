from datetime import datetime
from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.sorting import LogSort


@pytest.fixture
def log_data():
    now = pendulum.now("UTC")
    flow_id = str(uuid4())
    log_data = {
        "logs": [
            {
                "name": "prefect.flow_run",
                "level": 20,
                "message": "Ahoy, captain",
                "timestamp": now.timestamp(),
                "flow_id": str(flow_id),
            },
            {
                "name": "prefect.flow_run",
                "level": 50,
                "message": "Black flag ahead, captain!",
                "timestamp": now.timestamp(),
                "flow_id": flow_id,
            },
        ]
    }
    yield log_data


class TestCreateLogs:
    @staticmethod
    def assert_is_same_log(model, api_data):
        assert model.name == api_data["name"]
        assert model.level == api_data["level"]
        assert model.message == api_data["message"]
        assert model.timestamp == pendulum.from_timestamp(
            api_data["timestamp"]
        ).astimezone(pendulum.timezone("UTC"))
        assert str(model.flow_id) == api_data["flow_id"]

        if model.task_id:
            assert str(model.task_id) == api_data["task_id"]

    async def test_create_logs_with_flow_id(self, session, client, log_data):
        response = await client.post("/logs/", json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(**{"name": {"any_": ["prefect.flow_run"]}})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.TIMESTAMP_ASC
        )
        assert len(logs) == 2

        for i, log in enumerate(logs):
            self.assert_is_same_log(log, log_data["logs"][i])

    async def test_create_logs_with_task_id(self, session, client, log_data):
        response = await client.post("/logs/", json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(**{"name": {"any_": ["prefect.flow_run"]}})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.TIMESTAMP_ASC
        )
        assert len(logs) == 2

        for i, log in enumerate(logs):
            self.assert_is_same_log(log, log_data["logs"][i])
