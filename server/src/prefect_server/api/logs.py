# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import pydantic
import asyncio
from typing import Any, List, Dict

import pendulum

from prefect_server import config
from prefect_server.database import models


async def create_logs(logs: List[Dict[str, Any]]) -> str:
    """
    Inserts log record(s) into the database.
    Args:
        - logs (list): a list of log records represented as dictionaries, containing the following keys:
            `flow_run_id` and optionally containing task_run_id, timestamp, message, name, level and info.

    Returns:
        - None
    """
    model_logs = []
    now = pendulum.now("UTC")
    for log in logs:

        ## create model objects
        try:
            mlog = models.Log(
                flow_run_id=log.get("flow_run_id"),
                task_run_id=log.get("task_run_id"),
                timestamp=str(log.get("timestamp") or now),
                message=log.get("message"),
                name=log.get("name"),
                level=log.get("level") or "INFO",
                info=log.get("info"),
            )
        except pydantic.ValidationError:
            continue

        model_logs.append(mlog)

    if model_logs:
        await models.Log.insert_many(model_logs, selection_set={"affected_rows"})
