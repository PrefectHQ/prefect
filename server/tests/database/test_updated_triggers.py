# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Tests that updating rows in various table update the `updated` column
"""
import pendulum
import pytest

from prefect_server.database import models as m


async def test_flow_updated(flow_id):
    obj = await m.Flow.where(id=flow_id).first({"updated"})
    await m.Flow.where(id=flow_id).update(set={"name": "new-name"})
    obj_2 = await m.Flow.where(id=flow_id).first({"updated"})
    assert obj_2.updated > obj.updated


async def test_task_updated(task_id):
    obj = await m.Task.where(id=task_id).first({"updated"})
    await m.Task.where(id=task_id).update(set={"name": "new-name"})
    obj_2 = await m.Task.where(id=task_id).first({"updated"})
    assert obj_2.updated > obj.updated


async def test_flow_run_updated(flow_run_id):
    obj = await m.FlowRun.where(id=flow_run_id).first({"updated"})
    await m.FlowRun.where(id=flow_run_id).update(set={"version": 2})
    obj_2 = await m.FlowRun.where(id=flow_run_id).first({"updated"})
    assert obj_2.updated > obj.updated


async def test_task_run_updated(task_run_id):
    obj = await m.TaskRun.where(id=task_run_id).first({"updated"})
    await m.TaskRun.where(id=task_run_id).update(set={"version": 2})
    obj_2 = await m.TaskRun.where(id=task_run_id).first({"updated"})
    assert obj_2.updated > obj.updated
