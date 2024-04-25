from unittest.mock import MagicMock

import pytest
from dbt.cli.main import dbtRunnerResult
from dbt.contracts.files import FileHash
from dbt.contracts.graph.nodes import ModelNode
from dbt.contracts.results import RunExecutionResult, RunResult
from prefect_dbt.cli.tasks import dbt_build_task

from prefect import flow
from prefect.artifacts import Artifact


@pytest.fixture
async def mock_dbt_runner_invoke_success():
    return dbtRunnerResult(
        success=True,
        exception=None,
        result=RunExecutionResult(
            results=[
                RunResult(
                    status="pass",
                    timing=None,
                    thread_id="'Thread-1 (worker)'",
                    message="CREATE TABLE (1.0 rows, 0 processed)",
                    failures=None,
                    node=ModelNode(
                        database="test-123",
                        schema="prefect_dbt_example",
                        name="my_first_dbt_model",
                        resource_type="model",
                        package_name="prefect_dbt_bigquery",
                        path="example/my_first_dbt_model.sql",
                        original_file_path="models/example/my_first_dbt_model.sql",
                        unique_id="model.prefect_dbt_bigquery.my_first_dbt_model",
                        fqn=["prefect_dbt_bigquery", "example", "my_first_dbt_model"],
                        alias="my_first_dbt_model",
                        checksum=FileHash(name="sha256", checksum="123456789"),
                    ),
                    execution_time=0.0,
                    adapter_response=None,
                )
            ],
            elapsed_time=0.0,
        ),
    )


@pytest.fixture()
def dbt_runner_result(monkeypatch, mock_dbt_runner_invoke_success):
    _mock_dbt_runner_invoke_success = MagicMock(
        return_value=mock_dbt_runner_invoke_success
    )
    monkeypatch.setattr(
        "dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_invoke_success
    )


@pytest.fixture
def profiles_dir(tmp_path):
    return tmp_path / ".dbt"


@pytest.mark.usefixtures("dbt_runner_result")
def test_dbt_build_task_creates_artifact(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return dbt_build_task(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            artifact_key="foo",
            create_artifact=True,
        )

    test_flow()
    assert (a := Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# DBT Build Task Summary")
    assert "my_first_dbt_model" in a.data
