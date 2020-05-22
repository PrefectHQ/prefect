# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio

import pendulum
import pytest
from prefect_server.database import models


class TestWriteRunLogs:
    mutation = """
        mutation($input: write_run_logs_input!) {
            write_run_logs(input: $input) {
                success
            }
        }
    """

    async def test_create_flow_run_logs(self, run_query, flow_run_id):

        logs = [dict(flow_run_id=flow_run_id, message="test") for _ in range(10)]
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(logs=logs)),
        )

        assert result.data.write_run_logs.success

        await asyncio.sleep(0.5)
        logs = await models.Log.where({"flow_run_id": {"_eq": flow_run_id}}).get(
            {"message", "task_run_id"}
        )
        assert len(logs) == 10
        assert all(log.message == "test" for log in logs)
        assert all(log.task_run_id is None for log in logs)

    async def test_create_task_run_logs(self, run_query, flow_run_id, task_run_id):
        logs = [
            dict(flow_run_id=flow_run_id, task_run_id=task_run_id, message="test")
            for _ in range(14)
        ]
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(logs=logs)),
        )
        assert result.data.write_run_logs.success

        await asyncio.sleep(0.5)
        logs = await models.Log.where({"task_run_id": {"_eq": task_run_id}}).get(
            {"message"}
        )
        assert len(logs) == 14
        assert all(log.message == "test" for log in logs)

    async def test_create_logs_with_options(self, run_query, flow_run_id):
        level = "CRITICAL"
        name = "test-logger"
        timestamp = pendulum.datetime(2019, 1, 1, 1, 1, 1)
        info = {"a": [1, 2, 3]}

        payload = dict(
            flow_run_id=flow_run_id,
            message="test",
            level=level,
            name=name,
            info=info,
            timestamp=timestamp.isoformat(),
        )
        logs = [payload for _ in range(6)]
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(logs=logs)),
        )

        assert result.data.write_run_logs.success

        await asyncio.sleep(0.5)
        logs = await models.Log.where({"flow_run_id": {"_eq": flow_run_id}}).get(
            {"message", "info", "timestamp", "name", "level"}
        )
        assert len(logs) == 6
        assert all(log.message == "test" for log in logs)
        assert all(log.info == info for log in logs)
        assert all(log.timestamp == timestamp for log in logs)
        assert all(log.name == name for log in logs)
        assert all(log.level == level for log in logs)

    async def test_create_logs_with_invalid_level_fails(self, run_query, flow_run_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    logs=[
                        dict(flow_run_id=flow_run_id, message="test", level="bad-level")
                    ]
                )
            ),
        )

        assert "got invalid value 'bad-level'" in result.errors[0].message

    async def test_diverse_payloads(self, run_query, flow_run_id):
        levels = ["ERROR", "CRITICAL", "INFO", "INFO"]
        names = ["test-logger", "foo", "bar", "chris"]
        timestamps = [
            pendulum.datetime(2019, i + 1, 1, 1, 1, 1).isoformat() for i in range(4)
        ]
        infos = [{let: list(range(i + 1))} for i, let in enumerate("abcd")]
        messages = ["do", "rae", "me", "fa"]

        payloads = [
            dict(
                flow_run_id=flow_run_id,
                message=messages[i],
                level=levels[i],
                name=names[i],
                info=infos[i],
                timestamp=timestamps[i],
            )
            for i in range(4)
        ]
        await run_query(
            query=self.mutation, variables=dict(input=dict(logs=payloads)),
        )

        await asyncio.sleep(0.5)
        logs = await models.Log.where({"flow_run_id": {"_eq": flow_run_id}}).get(
            {"message", "info", "timestamp", "name", "level"}
        )
        assert len(logs) == 4
        assert set([log.message for log in logs]) == set(messages)
        assert set([log.level for log in logs]) == set(levels)
        assert set([log.name for log in logs]) == set(names)
        assert set([log.timestamp.isoformat() for log in logs]) == set(timestamps)
        stored_infos = [log.info for log in logs]
        assert all(info in stored_infos for info in infos)

    async def test_create_flow_run_logs_requires_flow_run_id_for_all_logs(
        self, run_query, flow_run_id
    ):
        logs_count = await models.Log.where().count()

        logs = [dict(flow_run_id=flow_run_id, message="test") for _ in range(9)]
        logs.append(dict(flow_run_id=None, message="test"))
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(logs=logs)),
        )

        assert result.errors
        assert "Expected non-nullable type UUID!" in result.errors[0].message

        await asyncio.sleep(0.5)
        new_count = await models.Log.where().count()
        assert new_count == logs_count
