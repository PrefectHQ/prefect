import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml
from dbt.artifacts.resources.v1.components import FreshnessThreshold, Time
from dbt.cli.main import DbtUsageException, dbtRunnerResult
from dbt.contracts.files import FileHash
from dbt.contracts.graph.nodes import ModelNode, SourceDefinition
from dbt.contracts.results import (
    FreshnessMetadata,
    FreshnessResult,
    RunExecutionResult,
    RunResult,
    SourceFreshnessResult,
)
from prefect_dbt.cli.commands import (
    DbtCoreOperation,
    run_dbt_build,
    run_dbt_model,
    run_dbt_seed,
    run_dbt_snapshot,
    run_dbt_source_freshness,
    run_dbt_test,
    trigger_dbt_cli_command,
)
from prefect_dbt.cli.credentials import DbtCliProfile

from prefect import flow
from prefect.artifacts import Artifact
from prefect.testing.utilities import AsyncMock


@pytest.fixture
async def mock_dbt_runner_model_success():
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


@pytest.fixture
async def mock_dbt_runner_model_error():
    return dbtRunnerResult(
        success=False,
        exception=None,
        result=RunExecutionResult(
            results=[
                RunResult(
                    status="error",
                    timing=None,
                    thread_id="'Thread-1 (worker)'",
                    message="Runtime Error",
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


@pytest.fixture
async def mock_dbt_runner_freshness_success():
    return dbtRunnerResult(
        success=True,
        exception=None,
        result=FreshnessResult(
            results=[
                SourceFreshnessResult(
                    status="pass",
                    thread_id="Thread-1 (worker)",
                    execution_time=0.0,
                    adapter_response={},
                    message=None,
                    failures=None,
                    max_loaded_at=datetime.datetime.now(),
                    snapshotted_at=datetime.datetime.now(),
                    timing=[],
                    node=SourceDefinition(
                        database="test-123",
                        schema="prefect_dbt_example",
                        name="my_first_dbt_model",
                        resource_type="source",
                        package_name="prefect_dbt_bigquery",
                        path="example/my_first_dbt_model.yml",
                        original_file_path="models/example/my_first_dbt_model.yml",
                        unique_id="source.prefect_dbt_bigquery.my_first_dbt_model",
                        fqn=["prefect_dbt_bigquery", "example", "my_first_dbt_model"],
                        source_name="prefect_dbt_source",
                        source_description="",
                        description="",
                        loader="my_loader",
                        identifier="my_identifier",
                        freshness=FreshnessThreshold(
                            warn_after=Time(count=12, period="hour"),
                            error_after=Time(count=24, period="hour"),
                            filter=None,
                        ),
                    ),
                    age=0.0,
                )
            ],
            elapsed_time=0.0,
            metadata=FreshnessMetadata(
                dbt_schema_version="https://schemas.getdbt.com/dbt/sources/v3.json",
                dbt_version="1.1.1",
                generated_at=datetime.datetime.now(),
                invocation_id="invocation_id",
                env={},
            ),
        ),
    )


@pytest.fixture
async def mock_dbt_runner_freshness_error():
    return dbtRunnerResult(
        success=False,
        exception=None,
        result=FreshnessResult(
            results=[
                SourceFreshnessResult(
                    status="error",
                    thread_id="Thread-1 (worker)",
                    execution_time=0.0,
                    adapter_response={},
                    message=None,
                    failures=None,
                    max_loaded_at=datetime.datetime.now(),
                    snapshotted_at=datetime.datetime.now(),
                    timing=[],
                    node=SourceDefinition(
                        database="test-123",
                        schema="prefect_dbt_example",
                        name="my_first_dbt_model",
                        resource_type="source",
                        package_name="prefect_dbt_bigquery",
                        path="example/my_first_dbt_model.yml",
                        original_file_path="models/example/my_first_dbt_model.yml",
                        unique_id="source.prefect_dbt_bigquery.my_first_dbt_model",
                        fqn=["prefect_dbt_bigquery", "example", "my_first_dbt_model"],
                        source_name="my_first_dbt_source",
                        source_description="",
                        description="",
                        loader="my_loader",
                        identifier="my_identifier",
                        freshness=FreshnessThreshold(
                            warn_after=Time(count=12, period="hour"),
                            error_after=Time(count=24, period="hour"),
                            filter=None,
                        ),
                    ),
                    age=0.0,
                )
            ],
            elapsed_time=0.0,
            metadata=FreshnessMetadata(
                dbt_schema_version="https://schemas.getdbt.com/dbt/sources/v3.json",
                dbt_version="1.1.1",
                generated_at=datetime.datetime.now(),
                invocation_id="invocation_id",
                env={},
            ),
        ),
    )


@pytest.fixture
async def mock_dbt_runner_ls_success():
    return dbtRunnerResult(
        success=True, exception=None, result=["example.example.test_model"]
    )


@pytest.fixture
def dbt_runner_model_result(
    monkeypatch: pytest.MonkeyPatch, mock_dbt_runner_model_success: dbtRunnerResult
) -> None:
    _mock_dbt_runner_invoke_success = MagicMock(
        return_value=mock_dbt_runner_model_success
    )
    monkeypatch.setattr(
        "dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_invoke_success
    )


@pytest.fixture
def dbt_runner_ls_result(
    monkeypatch: pytest.MonkeyPatch, mock_dbt_runner_ls_success: dbtRunnerResult
) -> None:
    _mock_dbt_runner_ls_result = MagicMock(return_value=mock_dbt_runner_ls_success)
    monkeypatch.setattr("dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_ls_result)


@pytest.fixture
def dbt_runner_freshness_error(
    monkeypatch: pytest.MonkeyPatch, mock_dbt_runner_freshness_error: dbtRunnerResult
) -> None:
    _mock_dbt_runner_freshness_error = MagicMock(
        return_value=mock_dbt_runner_freshness_error
    )
    monkeypatch.setattr(
        "dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_freshness_error
    )


@pytest.fixture
def dbt_runner_freshness_success(
    monkeypatch: pytest.MonkeyPatch, mock_dbt_runner_freshness_success: dbtRunnerResult
) -> None:
    _mock_dbt_runner_freshness_success = MagicMock(
        return_value=mock_dbt_runner_freshness_success
    )
    monkeypatch.setattr(
        "dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_freshness_success
    )
    return _mock_dbt_runner_freshness_success


@pytest.fixture
def dbt_runner_failed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_dbt_runner_invoke_failed = MagicMock(
        return_value=dbtRunnerResult(
            success=False,
            exception=DbtUsageException("No such command 'weeeeeee'."),
            result=None,
        )
    )
    monkeypatch.setattr("dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_invoke_failed)


@pytest.fixture
def profiles_dir(tmp_path: Path) -> str:
    return str(tmp_path) + "/.dbt"


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            command="dbt ls",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
        )

    result = test_flow()
    assert isinstance(result, dbtRunnerResult)


def test_trigger_dbt_cli_command_cli_argument_list(
    profiles_dir, dbt_cli_profile_bare, dbt_runner_freshness_success
):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            command="dbt source freshness",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
        )

    test_flow()
    dbt_runner_freshness_success.assert_called_with(
        ["source", "freshness", "--profiles-dir", profiles_dir]
    )


@pytest.mark.usefixtures("dbt_runner_freshness_error")
def test_trigger_dbt_cli_command_failed(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            command="dbt source freshness",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
        )

    with pytest.raises(
        Exception, match="dbt task result success: False with exception: None"
    ):
        test_flow()


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_run_twice_overwrite(
    profiles_dir, dbt_cli_profile, dbt_cli_profile_bare
):
    @flow
    def test_flow():
        trigger_dbt_cli_command(
            command="dbt ls", profiles_dir=profiles_dir, dbt_cli_profile=dbt_cli_profile
        )
        run_two = trigger_dbt_cli_command(
            command="dbt ls",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            overwrite_profiles=True,
        )
        return run_two

    result = test_flow()
    assert isinstance(result, dbtRunnerResult)
    with open(profiles_dir + "/profiles.yml", "r") as f:
        actual = yaml.safe_load(f)
    expected = {
        "config": {},
        "prefecto": {
            "target": "testing",
            "outputs": {
                "testing": {
                    "type": "custom",
                    "schema": "my_schema",
                    "threads": 4,
                    "account": "fake",
                }
            },
        },
    }
    assert actual == expected


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_run_twice_exists(
    profiles_dir, dbt_cli_profile, dbt_cli_profile_bare
):
    @flow
    def test_flow():
        trigger_dbt_cli_command(
            "dbt ls", profiles_dir=profiles_dir, dbt_cli_profile=dbt_cli_profile
        )
        run_two = trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
        )
        return run_two

    with pytest.raises(ValueError, match="Since overwrite_profiles is False"):
        test_flow()


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_missing_profile(profiles_dir):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
        )

    with pytest.raises(
        ValueError, match="Profile not found. Provide `dbt_cli_profile` or"
    ):
        test_flow()


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_find_home(dbt_cli_profile_bare):
    home_dbt_dir = Path.home() / ".dbt"
    if (home_dbt_dir / "profiles.yml").exists():
        dbt_cli_profile = None
    else:
        dbt_cli_profile = dbt_cli_profile_bare

    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "ls", dbt_cli_profile=dbt_cli_profile, overwrite_profiles=False
        )

    result = test_flow()
    assert isinstance(result, dbtRunnerResult)


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_find_env(
    profiles_dir, dbt_cli_profile_bare, monkeypatch
):
    @flow
    def test_flow():
        return trigger_dbt_cli_command("ls", dbt_cli_profile=dbt_cli_profile_bare)

    monkeypatch.setenv("DBT_PROFILES_DIR", str(profiles_dir))
    result = test_flow()
    assert isinstance(result, dbtRunnerResult)


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_project_dir(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
            project_dir="project",
            dbt_cli_profile=dbt_cli_profile_bare,
        )

    result = test_flow()
    assert isinstance(result, dbtRunnerResult)


@pytest.mark.usefixtures("dbt_runner_ls_result")
def test_trigger_dbt_cli_command_extra_command_args(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            extra_command_args=["--return_all", "True"],
        )

    result = test_flow()
    assert isinstance(result, dbtRunnerResult)


class TestDbtCoreOperation:
    @pytest.fixture
    def mock_open_process(self, monkeypatch):
        open_process = MagicMock(name="open_process")
        open_process.return_value = AsyncMock(name="returned open_process")
        monkeypatch.setattr("prefect_shell.commands.open_process", open_process)
        return open_process

    @pytest.fixture
    def mock_shell_process(self, monkeypatch):
        shell_process = MagicMock()
        opened_shell_process = AsyncMock()
        shell_process.return_value = opened_shell_process
        monkeypatch.setattr("prefect_shell.commands.ShellProcess", shell_process)
        return shell_process

    @pytest.fixture
    def dbt_cli_profile(self):
        return DbtCliProfile(
            name="my_name",
            target="my_target",
            target_configs={"type": "my_type", "threads": 4, "schema": "my_schema"},
        )

    def test_find_valid_profiles_dir_default_env(
        self, tmp_path, mock_open_process, mock_shell_process, monkeypatch
    ):
        monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))
        (tmp_path / "profiles.yml").write_text("test")
        DbtCoreOperation(commands=["dbt debug"]).run()
        actual = str(mock_open_process.call_args_list[0][1]["env"]["DBT_PROFILES_DIR"])
        expected = str(tmp_path)
        assert actual == expected

    def test_find_valid_profiles_dir_input_env(
        self, tmp_path, mock_open_process, mock_shell_process
    ):
        (tmp_path / "profiles.yml").write_text("test")
        DbtCoreOperation(
            commands=["dbt debug"], env={"DBT_PROFILES_DIR": str(tmp_path)}
        ).run()
        actual = str(mock_open_process.call_args_list[0][1]["env"]["DBT_PROFILES_DIR"])
        expected = str(tmp_path)
        assert actual == expected

    def test_find_valid_profiles_dir_overwrite_without_profile(
        self, tmp_path, mock_open_process, mock_shell_process
    ):
        with pytest.raises(ValueError, match="Since overwrite_profiles is True"):
            DbtCoreOperation(
                commands=["dbt debug"], profiles_dir=tmp_path, overwrite_profiles=True
            ).run()

    def test_find_valid_profiles_dir_overwrite_with_profile(
        self, tmp_path, dbt_cli_profile, mock_open_process, mock_shell_process
    ):
        DbtCoreOperation(
            commands=["dbt debug"],
            profiles_dir=tmp_path,
            overwrite_profiles=True,
            dbt_cli_profile=dbt_cli_profile,
        ).run()
        assert (tmp_path / "profiles.yml").exists()

    def test_find_valid_profiles_dir_not_overwrite_with_profile(
        self, tmp_path, dbt_cli_profile, mock_open_process, mock_shell_process
    ):
        (tmp_path / "profiles.yml").write_text("test")
        with pytest.raises(ValueError, match="Since overwrite_profiles is False"):
            DbtCoreOperation(
                commands=["dbt debug"],
                profiles_dir=tmp_path,
                overwrite_profiles=False,
                dbt_cli_profile=dbt_cli_profile,
            ).run()

    def test_find_valid_profiles_dir_path_without_profile(self):
        with pytest.raises(ValueError, match="Since overwrite_profiles is True"):
            DbtCoreOperation(commands=["dbt debug"], profiles_dir=Path("fake")).run()

    def test_append_dirs_to_commands(
        self,
        tmp_path,
        dbt_cli_profile,
        mock_open_process,
        mock_shell_process,
        monkeypatch,
    ):
        mock_named_temporary_file = MagicMock(name="tempfile")
        monkeypatch.setattr("tempfile.NamedTemporaryFile", mock_named_temporary_file)
        try:
            with DbtCoreOperation(
                commands=["dbt debug"],
                profiles_dir=tmp_path,
                project_dir=tmp_path,
                dbt_cli_profile=dbt_cli_profile,
            ) as op:
                op.run()
        except (FileNotFoundError, TypeError):  # py37 raises TypeError
            pass  # we're mocking the tempfile; this is expected

        mock_write = mock_named_temporary_file.return_value.write
        assert (
            mock_write.call_args_list[0][0][0]
            == f'dbt debug --profiles-dir "{tmp_path}" --project-dir "{tmp_path}"'.encode()
        )


@pytest.mark.usefixtures("dbt_runner_freshness_success")
def test_sync_dbt_cli_command_creates_artifact(
    profiles_dir: str, dbt_cli_profile: Any
) -> None:
    @flow
    def test_flow() -> None:
        trigger_dbt_cli_command(
            command="dbt source freshness",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    test_flow()
    assert (a := Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert isinstance(a.data, str) and a.data.startswith(
        "#  dbt source freshness Task Summary"
    )
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_model_result")
async def test_run_dbt_build_creates_artifact(profiles_dir, dbt_cli_profile_bare):
    @flow
    async def test_flow():
        return await run_dbt_build(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt build Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_model_result")
async def test_run_dbt_test_creates_artifact(profiles_dir, dbt_cli_profile_bare):
    @flow
    async def test_flow():
        return await run_dbt_test(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt test Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_model_result")
async def test_run_dbt_snapshot_creates_artifact(profiles_dir, dbt_cli_profile_bare):
    @flow
    async def test_flow():
        return await run_dbt_snapshot(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt snapshot Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_model_result")
async def test_run_dbt_seed_creates_artifact(profiles_dir, dbt_cli_profile_bare):
    @flow
    async def test_flow():
        return await run_dbt_seed(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt seed Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_model_result")
async def test_run_dbt_model_creates_artifact(profiles_dir, dbt_cli_profile_bare):
    @flow
    async def test_flow():
        return await run_dbt_model(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt run Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_freshness_success")
async def test_run_dbt_source_freshness_creates_artifact(
    profiles_dir, dbt_cli_profile_bare
):
    @flow
    async def test_flow():
        return await run_dbt_source_freshness(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt source freshness Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Successful Nodes" in a.data


@pytest.fixture
def dbt_runner_model_error(monkeypatch, mock_dbt_runner_model_error):
    _mock_dbt_runner_invoke_error = MagicMock(return_value=mock_dbt_runner_model_error)
    monkeypatch.setattr("dbt.cli.main.dbtRunner.invoke", _mock_dbt_runner_invoke_error)


@pytest.mark.usefixtures("dbt_runner_model_error")
async def test_run_dbt_model_creates_unsuccessful_artifact(
    profiles_dir, dbt_cli_profile_bare
):
    @flow
    async def test_flow():
        return await run_dbt_model(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    with pytest.raises(
        Exception, match="dbt task result success: False with exception: None"
    ):
        await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt run Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Unsuccessful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_freshness_error")
async def test_run_dbt_source_freshness_creates_unsuccessful_artifact(
    profiles_dir, dbt_cli_profile_bare
):
    @flow
    async def test_flow():
        return await run_dbt_source_freshness(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    with pytest.raises(
        Exception, match="dbt task result success: False with exception: None"
    ):
        await test_flow()
    assert (a := await Artifact.get(key="foo"))
    assert a.type == "markdown"
    assert a.data.startswith("# dbt source freshness Task Summary")
    assert "my_first_dbt_model" in a.data
    assert "Unsuccessful Nodes" in a.data


@pytest.mark.usefixtures("dbt_runner_failed_result")
async def test_run_dbt_model_throws_error(profiles_dir, dbt_cli_profile_bare):
    @flow
    async def test_flow():
        return await run_dbt_model(
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            summary_artifact_key="foo",
            create_summary_artifact=True,
        )

    with pytest.raises(DbtUsageException, match="No such command 'weeeeeee'."):
        await test_flow()
