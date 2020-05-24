# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio

import pendulum
import pytest

from prefect_server import api, config, utilities
from prefect_server.database import models
from prefect_server.utilities.exceptions import Unauthorized


async def test_create_logs(flow_run_id):

    where_clause = {
        "flow_run_id": {"_eq": flow_run_id},
    }
    logs_count = await models.Log.where(where_clause).count()

    dt = pendulum.now()
    await api.logs.create_logs([dict(flow_run_id=flow_run_id)])

    assert await models.Log.where(where_clause).count() == logs_count + 1
    log = await models.Log.where(where_clause).first(
        {"timestamp", "level", "task_run_id"}
    )

    assert log.timestamp > dt
    assert log.level == "INFO"
    assert log.task_run_id is None


async def test_create_logs_with_task_run_id(flow_run_id, task_run_id):

    where_clause = {
        "flow_run_id": {"_eq": flow_run_id},
        "task_run_id": {"_eq": task_run_id},
    }
    logs_count = await models.Log.where(where_clause).count()

    await api.logs.create_logs(
        [dict(flow_run_id=flow_run_id, task_run_id=task_run_id,)]
    )

    assert await models.Log.where(where_clause).count() == logs_count + 1
    log = await models.Log.where(where_clause).first({"task_run_id"})

    assert log.task_run_id == task_run_id


async def test_create_logs_with_info(flow_run_id):

    where_clause = {
        "flow_run_id": {"_eq": flow_run_id},
    }
    logs_count = await models.Log.where(where_clause).count()

    timestamp = pendulum.datetime(2018, 1, 1)
    info = {"lineno": 5}
    level = "ERROR"
    name = "Test"
    message = "test message"

    pendulum.now()
    await api.logs.create_logs(
        [
            dict(
                flow_run_id=flow_run_id,
                timestamp=timestamp,
                info=info,
                level=level,
                name=name,
                message=message,
            )
        ]
    )

    assert await models.Log.where(where_clause).count() == logs_count + 1
    log = await models.Log.where(where_clause).first(
        {"timestamp", "level", "name", "message", "info"}
    )

    assert log.timestamp == timestamp
    assert log.level == level
    assert log.info == info
    assert log.message == message
    assert log.name == name


async def test_create_logs_with_bad_flow_run_ids_still_inserts_good_logs(flow_run_id):
    where_clause = {
        "flow_run_id": {"_eq": flow_run_id},
    }
    logs_count = await models.Log.where(where_clause).count()

    dt = pendulum.now()
    await api.logs.create_logs(
        [
            dict(flow_run_id=flow_run_id),
            dict(flow_run_id=""),
            dict(flow_run_id=flow_run_id, message="foo"),
            dict(flow_run_id=None),
        ]
    )

    assert await models.Log.where(where_clause).count() == logs_count + 2
