from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.sorting import LogSort


NOW = pendulum.now("UTC")


@pytest.fixture
def flow_id():
    yield str(uuid4())
    

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

    async def test_create_logs_with_flow_id_and_returns_number_created(self, session, client, flow_id):
        log_data = {
            "logs": [
                {
                    "name": "prefect.flow_run",
                    "level": 20,
                    "message": "Ahoy, captain",
                    "timestamp": NOW.timestamp(),
                    "flow_id": str(flow_id),
                },
                {
                    "name": "prefect.flow_run",
                    "level": 50,
                    "message": "Black flag ahead, captain!",
                    "timestamp": NOW.timestamp(),
                    "flow_id": flow_id,
                },
            ]
        }
        response = await client.post("/logs/", json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(**{"flow_id": {"any_": [flow_id]}})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)
        assert len(logs) == 2

        for i, log in enumerate(logs):
            self.assert_is_same_log(log, log_data["logs"][i])

    async def test_create_logs_with_task_id_and_returns_number_created(self, session, client, flow_id):
        task_id = str(uuid4())
        log_data = {
            "logs": [
                {
                    "name": "prefect.flow_run",
                    "level": 50,
                    "message": "Black flag ahead, captain!",
                    "timestamp": NOW.timestamp(),
                    "flow_id": flow_id,
                    "task_id": task_id
                }
            ]
        }
        response = await client.post("/logs/", json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 1}

        log_filter = LogFilter(**{"task_id": {"any_": [task_id]}})
        logs = await models.logs.read_logs(session=session, log_filter=log_filter)
        assert len(logs) == 1

        self.assert_is_same_log(logs[0], log_data["logs"][0])
