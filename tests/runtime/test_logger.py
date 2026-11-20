import logging

import pytest

from prefect import flow, runtime, task


def test_runtime_logger_outside_a_run(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="prefect"):
        runtime.get_logger().info("Outside a run")

    record = next(r for r in caplog.records if r.getMessage() == "Outside a run")
    assert record.name == "prefect"
    assert not hasattr(record, "flow_run_id")


def test_runtime_logger_attaches_run_ids(caplog: pytest.LogCaptureFixture):
    @task
    def log_from_task() -> str | None:
        runtime.get_logger().info("Inside a task")
        return runtime.task_run.id

    @flow
    def log_from_flow() -> tuple[str | None, str | None]:
        runtime.get_logger().info("Inside a flow")
        return runtime.flow_run.id, log_from_task()

    with caplog.at_level(logging.INFO, logger="prefect"):
        flow_run_id, task_run_id = log_from_flow()

    assert flow_run_id and task_run_id
    records = {record.getMessage(): record for record in caplog.records}
    flow_record = records["Inside a flow"]
    assert flow_record.name == "prefect.flow_runs"
    assert flow_record.__dict__["flow_run_id"] == flow_run_id
    assert not hasattr(flow_record, "task_run_id")

    task_record = records["Inside a task"]
    assert task_record.name == "prefect.task_runs"
    assert task_record.__dict__["flow_run_id"] == flow_run_id
    assert task_record.__dict__["task_run_id"] == task_run_id
