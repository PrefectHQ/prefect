import json
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from time import sleep
from unittest import mock
from uuid import UUID, uuid4

import httpx
import pytest
import readchar
import respx
import yaml
from typer import Exit

import prefect
from prefect import flow
from prefect._experimental.sla.objects import (
    ServiceLevelAgreement,
    TimeToCompletionSla,
)
from prefect.cli.deploy._sla import (
    _create_slas,
    _initialize_deployment_slas,
)
from prefect.client.base import ServerType
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import WorkPool
from prefect.deployments.base import initialize_project
from prefect.deployments.runner import RunnerDeployment
from prefect.settings import (
    PREFECT_API_URL,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import tmpchdir

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture
def project_dir(tmp_path):
    with tmpchdir(tmp_path):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        initialize_project()
        yield tmp_path


@pytest.fixture
async def docker_work_pool(prefect_client: PrefectClient) -> WorkPool:
    return await prefect_client.create_work_pool(
        work_pool=WorkPoolCreate(
            name="test-docker-work-pool",
            type="docker",
            base_job_template={
                "job_configuration": {"image": "{{ image}}"},
                "variables": {
                    "type": "object",
                    "properties": {
                        "image": {
                            "title": "Image",
                            "type": "string",
                        },
                    },
                },
            },
        )
    )


@pytest.fixture
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.root.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@flow()
def tired_flow():
    print("I am so tired...")

    for _ in range(100):
        print("zzzzz...")
        sleep(5)


class TestSla:
    async def test_create_sla(self):
        sla = ServiceLevelAgreement(
            name="test-sla",
        )
        deployment_id = uuid4()
        sla.set_deployment_id(deployment_id)
        assert sla.owner_resource == f"prefect.deployment.{deployment_id}"


class TestClientApplySla:
    async def test_create_sla_against_cloud(self):
        account_id = uuid4()
        workspace_id = uuid4()
        deployment_id = uuid4()
        prefect_api_url = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/"

        with temporary_settings(
            updates={
                PREFECT_API_URL: prefect_api_url,
            }
        ):
            with respx.mock(
                assert_all_mocked=True,
                assert_all_called=False,
                base_url=prefect_api_url,
                using="httpx",
            ) as router:
                sla_name = "test-sla"

                router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
                router.post(
                    f"/slas/apply-resource-slas/prefect.deployment.{deployment_id}",
                ).mock(
                    return_value=httpx.Response(
                        status_code=201,
                        json={
                            "created": [{"name": sla_name}],
                            "updated": [],
                            "deleted": [],
                        },
                    )
                )
                prefect_client = get_client()

                sla = TimeToCompletionSla(
                    name=sla_name,
                    duration=timedelta(minutes=10).total_seconds(),
                )
                response = await prefect_client.apply_slas_for_deployment(
                    deployment_id, [sla]
                )

                assert response.created[0] == sla.name


class TestRunnerDeploymentApply:
    async def test_runner_deployment_calls_internal_method_on_apply_with_sla(
        self, monkeypatch
    ):
        sla = TimeToCompletionSla(
            name="test-sla",
            duration=timedelta(minutes=10).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            _sla=sla,
        )
        monkeypatch.setattr(
            deployment, "_create_slas", mock.AsyncMock(name="mock_create_slas")
        )

        await deployment.apply()

        assert deployment._create_slas.called

    @pytest.fixture
    def deployment_id(self):
        return UUID("89f0ac57-514a-4eb1-a068-dbbf44d2e199")

    @pytest.fixture
    def client(self, monkeypatch, prefect_client, deployment_id):
        monkeypatch.setattr(prefect_client, "server_type", ServerType.CLOUD)

        monkeypatch.setattr(
            prefect_client,
            "apply_slas_for_deployment",
            mock.AsyncMock(name="mock_apply_slas_for_deployment"),
        )

        monkeypatch.setattr(
            prefect_client,
            "create_deployment",
            mock.AsyncMock(name="mock_create_deployment", return_value=deployment_id),
        )
        return prefect_client

    async def test_create_deployment_with_sla_config_against_cloud(
        self, deployment, client, deployment_id
    ):
        sla = TimeToCompletionSla(
            name="test-sla",
            duration=timedelta(minutes=10).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            _sla=sla,
        )
        await deployment._create_slas(deployment_id, client)
        assert (
            client.apply_slas_for_deployment.await_args_list[0].args[0] == deployment_id
        )
        assert (
            client.apply_slas_for_deployment.await_args_list[0].args[1][0].name
            == sla.name
        )

    async def test_create_deployment_with_multiple_slas_against_cloud(
        self, client, deployment_id
    ):
        sla1 = TimeToCompletionSla(
            name="a little long",
            severity="moderate",
            duration=timedelta(minutes=10).total_seconds(),
        )
        sla2 = TimeToCompletionSla(
            name="whoa this is bad",
            severity="high",
            duration=timedelta(minutes=30).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            _sla=[sla1, sla2],
        )
        await deployment._create_slas(deployment_id, client)
        calls = client.apply_slas_for_deployment.await_args_list
        assert len(calls) == 1
        assert calls[0].args[0] == deployment_id
        assert [sla.name for sla in calls[0].args[1]] == [sla1.name, sla2.name]

    async def test_create_deployment_against_oss_server_produces_error_log(
        self, prefect_client, deployment_id
    ):
        sla = TimeToCompletionSla(
            name="test-sla",
            duration=timedelta(minutes=10).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            _sla=sla,
        )

        with pytest.raises(
            ValueError,
            match="SLA configuration is currently only supported on Prefect Cloud.",
        ):
            await deployment._create_slas(deployment_id, prefect_client)

    async def test_passing_empty_sla_list_calls_client_apply_slas_for_deployment(
        self, client, deployment_id
    ):
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            _sla=[],
        )
        await deployment._create_slas(deployment_id, client)
        assert client.apply_slas_for_deployment.called is True


class TestDeploymentCLI:
    @pytest.fixture
    def deployment_id(self):
        return UUID("89f0ac57-514a-4eb1-a068-dbbf44d2e199")

    class TestClientMethodCall:
        async def test_create_slas(self, prefect_client, monkeypatch, deployment_id):
            monkeypatch.setattr(prefect_client, "server_type", ServerType.CLOUD)

            monkeypatch.setattr(
                prefect_client,
                "apply_slas_for_deployment",
                mock.AsyncMock(name="mock_apply_slas_for_deployment"),
            )

            monkeypatch.setattr(
                prefect_client,
                "create_deployment",
                mock.AsyncMock(
                    name="mock_create_deployment", return_value=deployment_id
                ),
            )

            sla = TimeToCompletionSla(
                name="test-sla",
                duration=timedelta(minutes=10).total_seconds(),
            )
            await _create_slas(prefect_client, deployment_id, [sla])

            assert prefect_client.apply_slas_for_deployment.called is True
            assert (
                prefect_client.apply_slas_for_deployment.await_args_list[0].args[0]
                == deployment_id
            )
            assert (
                prefect_client.apply_slas_for_deployment.await_args_list[0]
                .args[1][0]
                .name
                == sla.name
            )

    class TestSlaSyncing:
        async def test_initialize_slas(self, deployment_id):
            sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            slas = _initialize_deployment_slas(deployment_id, [sla_spec])
            assert slas == [
                TimeToCompletionSla(
                    name="test-sla",
                    duration=1800,
                    severity="high",
                ).set_deployment_id(deployment_id)
            ]

        async def test_initialize_multiple_slas(self):
            sla_spec_1 = {
                "name": "test-sla-1",
                "duration": 1800,
                "severity": "high",
            }
            sla_spec_2 = {
                "name": "test-sla-2",
                "duration": 3600,
                "severity": "critical",
            }

            deployment_id = uuid4()
            slas = _initialize_deployment_slas(deployment_id, [sla_spec_1, sla_spec_2])
            assert slas == [
                TimeToCompletionSla(
                    name="test-sla-1",
                    duration=1800,
                    severity="high",
                ).set_deployment_id(deployment_id),
                TimeToCompletionSla(
                    name="test-sla-2",
                    duration=3600,
                    severity="critical",
                ).set_deployment_id(deployment_id),
            ]

        async def test_create_slas(self):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            deployment_id = uuid4()
            slas = _initialize_deployment_slas(deployment_id, [sla_spec])

            await _create_slas(client, deployment_id, slas)

            assert slas[0]._deployment_id == deployment_id
            assert slas[0].owner_resource == f"prefect.deployment.{deployment_id}"
            client.apply_slas_for_deployment.assert_called_once_with(
                deployment_id, slas
            )

        async def test_sla_creation_orchestrated(
            self,
            project_dir,
            prefect_client,
            work_pool,
        ):
            prefect_file = Path("prefect.yaml")
            with prefect_file.open(mode="r") as f:
                contents = yaml.safe_load(f)

            contents["deployments"] = [
                {
                    "name": "test-name-1",
                    "work_pool": {
                        "name": work_pool.name,
                    },
                    "sla": [
                        {
                            "name": "test-sla",
                            "duration": 1800,
                            "severity": "high",
                        }
                    ],
                }
            ]

            expected_slas = _initialize_deployment_slas(
                uuid4(), contents["deployments"][0]["sla"]
            )

            with prefect_file.open(mode="w") as f:
                yaml.safe_dump(contents, f)

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command="deploy ./flows/hello.py:my_flow -n test-name-1",
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                client, deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)

                for sla in expected_slas:
                    sla.set_deployment_id(deployment_id)

                assert slas == expected_slas

    class TestSlaPassedViaCLI:
        @pytest.mark.usefixtures("project_dir")
        async def test_json_string_sla(self, docker_work_pool):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            expected_slas = [
                TimeToCompletionSla(
                    name="test-sla",
                    duration=1800,
                    severity="high",
                )
            ]

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 --sla"
                        f" '{json.dumps(sla_spec)}' -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                client, called_deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)

                for sla in expected_slas:
                    sla.set_deployment_id(called_deployment_id)

                assert slas == expected_slas

        @pytest.mark.usefixtures("project_dir")
        async def test_passing_an_empty_list_calls_create_sla_method(
            self, docker_work_pool
        ):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 --sla '[]' -p"
                        f" {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1
                _, _, slas = create_slas.call_args[0]
                assert slas == []

        @pytest.mark.usefixtures("project_dir")
        async def test_json_file_sla(self, docker_work_pool):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            with open("sla.json", "w") as f:
                json.dump({"sla": [sla_spec]}, f)

            expected_slas = [
                TimeToCompletionSla(
                    name="test-sla",
                    duration=1800,
                    severity="high",
                )
            ]

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --sla sla.json -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                client, called_deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)

                for sla in expected_slas:
                    sla.set_deployment_id(called_deployment_id)

                assert slas == expected_slas

        @pytest.mark.usefixtures("project_dir")
        async def test_yaml_file_sla(self, docker_work_pool):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD
            sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            with open("sla.yaml", "w") as f:
                yaml.safe_dump({"sla": [sla_spec]}, f)

            expected_slas = [
                TimeToCompletionSla(
                    name="test-sla",
                    duration=1800,
                    severity="high",
                )
            ]

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --sla sla.yaml -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                client, called_deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)

                for sla in expected_slas:
                    sla.set_deployment_id(called_deployment_id)

                assert slas == expected_slas

        @pytest.mark.usefixtures("project_dir")
        async def test_passing_empty_list_to_yaml_file_calls_create_sla_method(
            self, docker_work_pool
        ):
            with open("sla.yaml", "w") as f:
                yaml.safe_dump({"sla": []}, f)

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --sla sla.yaml -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                _, _, slas = create_slas.call_args[0]
                assert slas == []

        @pytest.mark.usefixtures("project_dir")
        async def test_nested_yaml_file_sla(self, docker_work_pool, tmpdir):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            slas_file = tmpdir.mkdir("my_stuff") / "sla.yaml"
            with open(slas_file, "w") as f:
                yaml.safe_dump({"sla": [sla_spec]}, f)

            expected_slas = [
                TimeToCompletionSla(
                    name="test-sla",
                    duration=1800,
                    severity="high",
                )
            ]

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --sla my_stuff/sla.yaml -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                client, called_deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)

                for sla in expected_slas:
                    sla.set_deployment_id(called_deployment_id)

                assert slas == expected_slas

        @pytest.mark.usefixtures("project_dir")
        async def test_multiple_sla_flags(self, docker_work_pool):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            sla_spec_1 = {
                "name": "test-sla-1",
                "duration": 1800,
                "severity": "high",
            }

            sla_spec_2 = {
                "name": "test-sla-2",
                "duration": 3600,
                "severity": "critical",
            }

            with open("sla.yaml", "w") as f:
                yaml.safe_dump({"sla": [sla_spec_2]}, f)

            expected_slas = [
                TimeToCompletionSla(
                    name="test-sla-1",
                    duration=1800,
                    severity="high",
                ),
                TimeToCompletionSla(
                    name="test-sla-2",
                    duration=3600,
                    severity="critical",
                ),
            ]

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 --sla"
                        f" '{json.dumps(sla_spec_1)}' --sla sla.yaml -p"
                        f" {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_slas.call_count == 1

                client, called_deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)

                for sla in expected_slas:
                    sla.set_deployment_id(called_deployment_id)

                assert slas == expected_slas

        @pytest.mark.usefixtures("project_dir")
        async def test_override_on_sla_conflict(self, docker_work_pool):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            cli_sla_spec = {
                "name": "cli-sla",
                "duration": 1800,
                "severity": "high",
            }

            file_sla_spec = {
                "name": "file-sla",
                "duration": 1800,
                "severity": "high",
            }

            expected_slas = [
                TimeToCompletionSla(
                    name="cli-sla",
                    duration=1800,
                    severity="high",
                )
            ]

            prefect_file = Path("prefect.yaml")
            with prefect_file.open(mode="r") as f:
                contents = yaml.safe_load(f)

            contents["deployments"] = [
                {
                    "name": "test-name-1",
                    "work_pool": {
                        "name": docker_work_pool.name,
                    },
                    "slas": [
                        file_sla_spec,
                    ],
                }
            ]

            with prefect_file.open(mode="w") as f:
                yaml.safe_dump(contents, f)

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ) as create_slas:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --sla '{json.dumps(cli_sla_spec)}'"
                    ),
                    expected_code=0,
                )

                client, called_deployment_id, slas = create_slas.call_args[0]
                assert isinstance(client, PrefectClient)
                assert len(slas) == 1

                for sla in expected_slas:
                    sla.set_deployment_id(called_deployment_id)
                assert slas == expected_slas

        @pytest.mark.usefixtures("project_dir")
        async def test_invalid_sla_parsing(self, docker_work_pool):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            invalid_json_str_sla = "{foo: bar, baz: bat}"
            invalid_yaml_sla = "invalid.yaml"

            with open(invalid_yaml_sla, "w") as f:
                f.write("pretty please, let me know if the flow runs for too long")

            for invalid_sla in [invalid_json_str_sla, invalid_yaml_sla]:
                with mock.patch(
                    "prefect.cli.deploy._core._create_slas",
                    mock.AsyncMock(),
                ):
                    await run_sync_in_worker_thread(
                        invoke_and_assert,
                        command=(
                            "deploy ./flows/hello.py:my_flow -n test-name-1"
                            f" -p {docker_work_pool.name} --sla '{invalid_sla}'"
                        ),
                        expected_code=1,
                        expected_output_contains=["Failed to parse SLA"],
                    )

        @pytest.mark.usefixtures("interactive_console")
        async def test_slas_saved_to_prefect_yaml(
            self,
            docker_work_pool,
            project_dir,
        ):
            client = mock.AsyncMock()
            client.server_type = ServerType.CLOUD

            cli_sla_spec = {
                "name": "test-sla",
                "duration": 1800,
                "severity": "high",
            }

            # ensure file is removed for save to occur
            prefect_file = project_dir / "prefect.yaml"
            prefect_file.unlink()

            with mock.patch(
                "prefect.cli.deploy._core._create_slas",
                mock.AsyncMock(),
            ):
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 -p"
                        f" {docker_work_pool.name} --sla"
                        f" '{json.dumps(cli_sla_spec)}'"
                        f" --prefect-file {prefect_file}"
                    ),
                    user_input=(
                        # Decline schedule
                        "n"
                        + readchar.key.ENTER
                        # Decline remote storage
                        + "n"
                        + readchar.key.ENTER
                        # Decline docker build
                        + "n"
                        + readchar.key.ENTER
                        # Accept save configuration
                        + "y"
                        + readchar.key.ENTER
                    ),
                    expected_code=0,
                )

            # Read the updated prefect.yaml
            with prefect_file.open(mode="r") as f:
                contents = yaml.safe_load(f)

            assert "deployments" in contents
            assert "sla" in contents["deployments"][-1]
            assert contents["deployments"][-1]["sla"] == [cli_sla_spec]
