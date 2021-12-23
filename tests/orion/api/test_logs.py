from datetime import datetime

import pendulum
import pytest

from prefect.orion import models
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.sorting import LogSort


@pytest.fixture
def log_data():
    now = pendulum.now("UTC")
    log_data = {
        "logs": [
            {
                "name": "prefect.flow_run",
                "level": 20,
                "message": "Ahoy, captain",
                "timestamp": now.timestamp(),
                "extra_attributes": {"flow_id": 1},
            },
            {
                "name": "prefect.flow_run",
                "level": 50,
                "message": "Black flag ahead, captain!",
                "timestamp": now.timestamp(),
                "extra_attributes": {"flow_id": 1},
            },
        ]
    }
    yield log_data


class TestCreateLogs:
    async def test_create_logs_with_extra_attributes(self, session, client, log_data):
        response = await client.post("/logs/", json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(**{"name": {"any_": ["prefect.flow_run"]}})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.TIMESTAMP_ASC
        )
        assert len(logs) == 2

        for i, log in enumerate(logs):
            assert log.name == log_data["logs"][i]["name"]
            assert log.level == log_data["logs"][i]["level"]
            assert log.message == log_data["logs"][i]["message"]
            assert log.timestamp == pendulum.from_timestamp(
                log_data["logs"][i]["timestamp"]
            ).astimezone(pendulum.timezone("UTC"))
            assert log.extra_attributes == log_data["logs"][i]["extra_attributes"]

    async def test_create_logs_without_extra_attributes(
        self, session, client, log_data
    ):
        log_data["logs"][0].pop("extra_attributes")
        log_data["logs"][1].pop("extra_attributes")

        response = await client.post("/logs/", json=log_data)
        assert response.status_code == 201
        assert response.json() == {"created": 2}

        log_filter = LogFilter(**{"name": {"any_": ["prefect.flow_run"]}})
        logs = await models.logs.read_logs(
            session=session, log_filter=log_filter, sort=LogSort.TIMESTAMP_ASC
        )
        assert len(logs) == 2

        for i, log in enumerate(logs):
            assert log.name == log_data["logs"][i]["name"]
            assert log.level == log_data["logs"][i]["level"]
            assert log.message == log_data["logs"][i]["message"]
            assert log.timestamp == pendulum.from_timestamp(
                log_data["logs"][i]["timestamp"]
            ).astimezone(pendulum.timezone("UTC"))
            assert log.extra_attributes == {}
