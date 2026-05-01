"""Integration tests for PrefectDbtRunner against a real DuckDB dbt project."""

import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from dbt.cli.main import dbtRunner

duckdb = pytest.importorskip("duckdb", reason="duckdb required for integration tests")
pytest.importorskip(
    "dbt.adapters.duckdb", reason="dbt-duckdb required for integration tests"
)

from prefect_dbt.core.runner import PrefectDbtRunner  # noqa: E402
from prefect_dbt.core.settings import PrefectDbtSettings  # noqa: E402

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
