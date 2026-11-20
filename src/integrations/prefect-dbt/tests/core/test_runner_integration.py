"""Integration tests for PrefectDbtRunner against a real DuckDB dbt project."""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from dbt.cli.main import dbtRunner
from dbt.contracts.results import NodeStatus

duckdb = pytest.importorskip("duckdb", reason="duckdb required for integration tests")
pytest.importorskip(
    "dbt.adapters.duckdb", reason="dbt-duckdb required for integration tests"
)

from prefect_dbt.core.runner import PrefectDbtRunner  # noqa: E402
from prefect_dbt.core.settings import PrefectDbtSettings  # noqa: E402

from prefect import flow  # noqa: E402
from prefect.client.orchestration import get_client  # noqa: E402
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId  # noqa: E402
from prefect.client.schemas.objects import StateType  # noqa: E402
from prefect.context import get_run_context  # noqa: E402

pytestmark = pytest.mark.integration

DBT_TEST_PROJECT = Path(__file__).resolve().parent.parent / "dbt_test_project"


@pytest.fixture
def dbt_project(tmp_path):
    project_dir = tmp_path / "dbt_project"
    shutil.copytree(DBT_TEST_PROJECT, project_dir)

    profiles = {
        "test": {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": str(project_dir / "warehouse.duckdb"),
                    "schema": "main",
                    "threads": 1,
                }
            },
        }
    }
    (project_dir / "profiles.yml").write_text(yaml.dump(profiles))

    schema_path = project_dir / "models" / "staging" / "schema.yml"
    schema = yaml.safe_load(schema_path.read_text())
    for model in schema["models"]:
        if model["name"] == "stg_customers":
            model["config"] = {"tags": ["hooked"]}
    schema_path.write_text(yaml.dump(schema))

    runner = dbtRunner()
    result = runner.invoke(
        ["parse", "--project-dir", str(project_dir), "--profiles-dir", str(project_dir)]
    )
    assert result.success, f"dbt parse failed: {result.exception}"

    return project_dir


def test_runner_lifecycle_hooks_with_real_dbt_invocation(dbt_project, caplog):
    settings = PrefectDbtSettings(project_dir=dbt_project, profiles_dir=dbt_project)
    runner = PrefectDbtRunner(settings=settings)
    run_starts: list[dict[str, Any]] = []
    post_models: list[dict[str, Any]] = []
    selected_post_models: list[str | None] = []
    run_ends: list[dict[str, Any]] = []

    @runner.on_run_start
    def run_start(ctx):
        run_starts.append(
            {
                "event": ctx.event,
                "command": ctx.command,
                "args": ctx.args,
                "owner": ctx.owner,
            }
        )

    @runner.post_model
    def post_model(ctx):
        post_models.append(
            {
                "event": ctx.event,
                "node_id": ctx.node_id,
                "node": ctx.node,
                "status": ctx.status,
            }
        )

    @runner.post_model(select="tag:hooked")
    def selected_post_model(ctx):
        selected_post_models.append(ctx.node_id)

    @runner.post_model
    def broken_post_model(ctx):
        raise RuntimeError("expected hook failure")

    @runner.on_run_end(select="tag:hooked")
    def run_end(ctx):
        run_ends.append(
            {
                "event": ctx.event,
                "status": ctx.status,
                "run_results": ctx.run_results,
                "node_ids": ctx.node_ids,
            }
        )

    with caplog.at_level(logging.WARNING, logger="prefect_dbt.core._hooks"):
        result = runner.invoke(["build"])

    assert result.success is True
    assert run_starts == [
        {"event": "run_start", "command": "build", "args": ("build",), "owner": runner}
    ]

    post_model_ids = {event["node_id"] for event in post_models}
    assert "model.test_project.stg_customers" in post_model_ids
    assert selected_post_models == ["model.test_project.stg_customers"]
    assert all(event["event"] == "post_model" for event in post_models)
    assert all(event["node_id"] == event["node"].unique_id for event in post_models)
    assert all(event["status"] == "success" for event in post_models)

    assert len(run_ends) == 1
    run_end_event = run_ends[0]
    assert run_end_event["event"] == "run_end"
    assert run_end_event["status"] == "success"
    assert run_end_event["run_results"]
    assert run_end_event["node_ids"]
    assert "model.test_project.stg_customers" in run_end_event["node_ids"]
    assert set(run_end_event["node_ids"]) == set(run_end_event["run_results"])

    assert any(
        "dbt hook broken_post_model failed during post_model." in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.skipif(
    not hasattr(NodeStatus, "PartialSuccess"), reason="microbatch requires dbt>=1.9"
)
@pytest.mark.parametrize(
    "failing_batch_id, expected_state",
    [(None, StateType.COMPLETED), (2, StateType.FAILED)],
)
def test_runner_microbatch_model_creates_single_terminal_task_run(
    dbt_project, failing_batch_id, expected_state
):
    """dbt emits a `NodeStart`/`NodeFinished` pair per microbatch batch, all with
    the model's `unique_id`; the model must still map to one task run that
    reaches a terminal state."""
    models_dir = dbt_project / "models" / "microbatch"
    models_dir.mkdir()
    (models_dir / "source_events.sql").write_text(
        "{{ config(materialized='table', event_time='event_at') }}\n"
        "select i as id, timestamp '2026-01-01' + to_days(i) as event_at\n"
        "from range(3) as t(i)\n"
    )
    failing_expr = (
        f"case when id = {failing_batch_id} then error('boom') end"
        if failing_batch_id is not None
        else "null"
    )
    (models_dir / "events_microbatch.sql").write_text(
        "{{ config(\n"
        "    materialized='incremental',\n"
        "    incremental_strategy='microbatch',\n"
        "    event_time='event_at',\n"
        "    begin='2026-01-01',\n"
        "    batch_size='day',\n"
        ") }}\n"
        f"select *, {failing_expr} as failure from {{{{ ref('source_events') }}}}\n"
    )

    settings = PrefectDbtSettings(project_dir=dbt_project, profiles_dir=dbt_project)
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)
    post_model_node_ids: list[str | None] = []

    @runner.post_model
    def post_model(ctx):
        post_model_node_ids.append(ctx.node_id)

    @flow
    def run_microbatch():
        runner.invoke(
            [
                "build",
                "--select",
                "+events_microbatch",
                "--event-time-start",
                "2026-01-01",
                "--event-time-end",
                "2026-01-04",
            ]
        )
        return get_run_context().flow_run.id

    flow_run_id = run_microbatch()

    async def read_task_runs():
        async with get_client() as client:
            return await client.read_task_runs(
                flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id]))
            )

    task_runs = asyncio.run(read_task_runs())
    microbatch_task_runs = [
        task_run for task_run in task_runs if "events_microbatch" in task_run.name
    ]
    assert len(microbatch_task_runs) == 1
    assert microbatch_task_runs[0].state.type == expected_state
    assert all(task_run.state.is_final() for task_run in task_runs)
    assert post_model_node_ids.count("model.test_project.events_microbatch") == 1
