import json
from datetime import timedelta
from unittest.mock import Mock

import pendulum
import pytest

from prefect import flow
from prefect.client.orion import OrionClient
from prefect.deployments import Deployment
from prefect.orion.schemas.filters import DeploymentFilter, DeploymentFilterId
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.settings import PREFECT_UI_URL, temporary_settings
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@flow
def my_flow():
    pass


@pytest.fixture
def dep_path():
    return "./dog.py"


@pytest.fixture
def patch_import(monkeypatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    monkeypatch.setattr("prefect.utilities.importtools.import_object", lambda path: fn)


class TestInputValidation:
    def test_useful_message_when_flow_name_skipped(self, dep_path):
        invoke_and_assert(
            ["deployment", "build", dep_path, "-n", "dog-deployment"],
            expected_output_contains=[
                "Your flow entrypoint must include the name of the function that is the entrypoint to your flow.",
                f"Try {dep_path}:<flow_name>",
            ],
            expected_code=1,
        )

    def test_name_must_be_provided_by_default(self, dep_path):
        invoke_and_assert(
            ["deployment", "build", dep_path],
            expected_output_contains=["A name for this deployment must be provided"],
            expected_code=1,
        )

    def test_work_queue_name_is_populated_as_default(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.work_queue_name == "default"

    def test_entrypoint_is_saved_as_relative_path(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.entrypoint == "fake-path.py:fn"

    def test_server_side_settings_are_used_if_present(self, patch_import, tmp_path):
        """
        This only applies to tags, work queue name, description, schedules and default parameter values
        """
        d = Deployment(
            name="TEST",
            flow_name="fn",
            description="server-side value",
            version="server",
            parameters={"key": "server"},
            tags=["server-tag"],
            work_queue_name="dev",
        )
        assert d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.description == "server-side value"
        assert deployment.tags == ["server-tag"]
        assert deployment.parameters == dict(key="server")
        assert deployment.work_queue_name == "dev"

    def test_version_flag_takes_precedence(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
            version="server",
        )
        assert d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "-v",
                "CLI-version",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.version == "CLI-version"

    def test_auto_apply_flag(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--apply",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Deployment '{d.flow_name}/{d.name}' successfully created with id '{deployment_id}'."
            ],
            temp_dir=tmp_path,
        )

    def test_param_overrides(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--param",
                "foo=bar",
                "--param",
                'greenman_says={"parsed as json": "I am"}',
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.parameters["foo"] == "bar"
        assert deployment.parameters["greenman_says"] == {"parsed as json": "I am"}

    def test_parameters_override(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--params",
                '{"greenman_says": {"parsed as json": "I am"}}',
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.parameters["greenman_says"] == {"parsed as json": "I am"}

    def test_mixing_parameter_overrides(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--params",
                '{"which": "parameter"}',
                "--param",
                "shouldbe:used",
            ],
            expected_code=1,
            temp_dir=tmp_path,
        )

    def test_passing_cron_schedules_to_build(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--cron",
                "0 4 * * *",
                "--timezone",
                "Europe/Berlin",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.schedule.cron == "0 4 * * *"
        assert deployment.schedule.timezone == "Europe/Berlin"

    def test_passing_interval_schedules_to_build(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--interval",
                "42",
                "--anchor-date",
                "2018-02-02",
                "--timezone",
                "America/New_York",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.schedule.interval == timedelta(seconds=42)
        assert deployment.schedule.anchor_date == pendulum.parse("2018-02-02")
        assert deployment.schedule.timezone == "America/New_York"

    def test_passing_anchor_without_interval_exits(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--anchor-date",
                "2018-02-02",
            ],
            expected_code=1,
            temp_dir=tmp_path,
            expected_output_contains="An anchor date can only be provided with an interval schedule",
        )

    def test_parsing_rrule_schedule_string_literal(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--rrule",
                "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )

    @pytest.fixture
    def built_deployment_with_queue_and_limit_overrides(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "-q",
                "the-queue-to-end-all-queues",
                "--limit",
                "424242",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

    @pytest.fixture
    def applied_deployment_with_queue_and_limit_overrides(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "-q",
                "the-mother-of-all-queues",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )
        invoke_and_assert(
            [
                "deployment",
                "apply",
                str(tmp_path / "test.yaml"),
                "-l",
                "4242",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

    async def test_setting_work_queue_concurrency_limits_with_build(
        self, built_deployment_with_queue_and_limit_overrides, orion_client
    ):
        queue = await orion_client.read_work_queue_by_name(
            "the-queue-to-end-all-queues"
        )
        assert queue.concurrency_limit == 424242

    async def test_setting_work_queue_concurrency_limits_with_apply(
        self, applied_deployment_with_queue_and_limit_overrides, orion_client
    ):
        queue = await orion_client.read_work_queue_by_name("the-mother-of-all-queues")
        assert queue.concurrency_limit == 4242

    def test_parsing_rrule_schedule_json(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--rrule",
                '{"rrule": "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17", "timezone": "America/New_York"}',
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )
        assert deployment.schedule.timezone == "America/New_York"

    def test_parsing_rrule_timezone_overrides_if_passed_explicitly(
        self, patch_import, tmp_path
    ):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--rrule",
                '{"rrule": "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17", "timezone": "America/New_York"}',
                "--timezone",
                "Europe/Berlin",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )
        assert deployment.schedule.timezone == "Europe/Berlin"


class TestOutputMessages:
    def test_message_with_work_queue_name(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )
        invoke_and_assert(
            [
                "deployment",
                "apply",
                str(tmp_path / "test.yaml"),
            ],
            expected_output_contains=[
                (
                    "To execute flow runs from this deployment, start an agent "
                    "that pulls work from the 'default' work queue:"
                ),
                "$ prefect agent start -q 'default'",
            ],
        )

    def test_message_with_work_queue_name_from_python_build(
        self, patch_import, tmp_path
    ):
        d = Deployment.build_from_flow(
            flow=my_flow,
            name="TEST",
            flow_name="my_flow",
            output=str(tmp_path / "test.yaml"),
            work_queue_name="prod",
        )
        invoke_and_assert(
            [
                "deployment",
                "apply",
                str(tmp_path / "test.yaml"),
            ],
            expected_output_contains=[
                (
                    "To execute flow runs from this deployment, start an agent "
                    f"that pulls work from the {d.work_queue_name!r} work queue:"
                ),
                f"$ prefect agent start -q {d.work_queue_name!r}",
            ],
        )

    def test_linking_to_deployment_in_ui(
        self,
        patch_import,
        tmp_path,
        monkeypatch,
    ):
        with temporary_settings({PREFECT_UI_URL: "http://foo/bar"}):
            d = Deployment.build_from_flow(
                flow=my_flow,
                name="TEST",
                flow_name="my_flow",
                output=str(tmp_path / "test.yaml"),
                work_queue_name="prod",
            )
            invoke_and_assert(
                [
                    "deployment",
                    "apply",
                    str(tmp_path / "test.yaml"),
                ],
                expected_output_contains="http://foo/bar/deployments/deployment/",
            )

    def test_updating_work_queue_concurrency_from_python_build(
        self, patch_import, tmp_path
    ):
        d = Deployment.build_from_flow(
            flow=my_flow,
            name="TEST",
            flow_name="my_flow",
            output=str(tmp_path / "test.yaml"),
            work_queue_name="prod",
        )
        invoke_and_assert(
            [
                "deployment",
                "apply",
                str(tmp_path / "test.yaml"),
                "-l",
                "42",
            ],
            expected_output_contains=[
                "Updated concurrency limit on work queue 'prod' to 42",
            ],
        )

    def test_message_with_missing_work_queue_name(self, patch_import, tmp_path):
        d = Deployment.build_from_flow(
            flow=my_flow,
            name="TEST",
            flow_name="my_flow",
            output=str(tmp_path / "test.yaml"),
            work_queue_name=None,
        )
        invoke_and_assert(
            [
                "deployment",
                "apply",
                str(tmp_path / "test.yaml"),
            ],
            expected_output_contains=(
                "This deployment does not specify a work queue name, which means agents "
                "will not be able to pick up its runs. To add a work queue, "
                "edit the deployment spec and re-run this command, or visit the deployment in the UI.",
            ),
        )


class TestUpdatingDeployments:
    @pytest.fixture
    async def flojo(self, orion_client):
        @flow
        async def rence_griffith():
            pass

        flow_id = await orion_client.create_flow(rence_griffith)
        old_record = IntervalSchedule(interval=timedelta(seconds=10.76))

        deployment_id = await orion_client.create_deployment(
            flow_id=flow_id,
            name="test-deployment",
            version="git-commit-hash",
            manifest_path="path/file.json",
            schedule=old_record,
            parameters={"foo": "bar"},
            tags=["foo", "bar"],
            parameter_openapi_schema={},
        )
        return deployment_id

    def test_updating_schedules(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["10.76"],  # 100 m record
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "set-schedule",
                "rence-griffith/test-deployment",
                "--interval",
                "10.49",  # July 16, 1988
            ],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["10.49"],  # flo-jo breaks the world record
            expected_code=0,
        )

    def test_incompatible_schedule_parameters(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "set-schedule",
                "rence-griffith/test-deployment",
                "--interval",
                "424242",
                "--cron",
                "i dont know cron syntax dont judge",
            ],
            expected_code=1,
            expected_output_contains="Incompatible schedule parameters",
        )

    def test_rrule_schedules_are_parsed_properly(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "set-schedule",
                "rence-griffith/test-deployment",
                "--rrule",
                '{"rrule": "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17", "timezone": "America/New_York"}',
            ],
            expected_code=0,
            expected_output_contains="Updated deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["America/New_York"],
            expected_code=0,
        )

    def test_rrule_schedule_timezone_overrides_if_passed_explicitly(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "set-schedule",
                "rence-griffith/test-deployment",
                "--rrule",
                '{"rrule": "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17", "timezone": "America/New_York"}',
                "--timezone",
                "Asia/Seoul",
            ],
            expected_code=0,
            expected_output_contains="Updated deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["Asia/Seoul"],
            expected_code=0,
        )

    def test_pausing_and_resuming_schedules(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "pause-schedule",
                "rence-griffith/test-deployment",
            ],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'is_schedule_active': False"],
        )

        invoke_and_assert(
            [
                "deployment",
                "resume-schedule",
                "rence-griffith/test-deployment",
            ],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'is_schedule_active': True"],
        )


class TestDeploymentRun:
    @pytest.fixture
    async def deployment_name(self, deployment, orion_client):
        flow = await orion_client.read_flow(deployment.flow_id)
        return f"{flow.name}/{deployment.name}"

    def test_run_wraps_parameter_stdin_parsing_exception(self, deployment_name):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--params", "-"],
            expected_code=1,
            expected_output_contains="Failed to parse JSON",
            user_input="not-valid-json",
        )

    def test_run_wraps_parameter_stdin_empty(self, tmp_path, deployment_name):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--params", "-"],
            expected_code=1,
            expected_output_contains="No data passed to stdin",
        )

    def test_run_wraps_parameters_parsing_exception(self, deployment_name):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--params", "not-valid-json"],
            expected_code=1,
            expected_output_contains="Failed to parse JSON",
        )

    def test_wraps_parameter_json_parsing_exception(self, deployment_name):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--param", 'x="foo"1'],
            expected_code=1,
            expected_output_contains=f"Failed to parse JSON for parameter 'x'",
        )

    def test_validates_parameters_are_in_deployment_schema(
        self,
        deployment_name,
    ):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--param", f"x=test"],
            expected_code=1,
            expected_output_contains=[
                "parameters were specified but not found on the deployment: 'x'",
                "parameters are available on the deployment: 'name'",
            ],
        )

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("foo", "foo"),
            ('"foo"', "foo"),
            (1, 1),
            ('["one", "two"]', ["one", "two"]),
            ('{"key": "val"}', {"key": "val"}),
            ('["one", 2]', ["one", 2]),
            ('{"key": 2}', {"key": 2}),
        ],
    )
    async def test_passes_parameters_to_flow_run(
        self, deployment, deployment_name, orion_client: OrionClient, given, expected
    ):
        """
        This test ensures the parameters are set on the created flow run and that
        data types are cast correctly.
        """
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["deployment", "run", deployment_name, "--param", f"name={given}"],
        )

        flow_runs = await orion_client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment.id])
            )
        )

        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.parameters == {"name": expected}

    async def test_passes_parameters_from_stdin_to_flow_run(
        self,
        deployment,
        deployment_name,
        orion_client,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["deployment", "run", deployment_name, "--params", "-"],
            json.dumps({"name": "foo"}),  # stdin
        )

        flow_runs = await orion_client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment.id])
            )
        )

        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.parameters == {"name": "foo"}

    async def test_passes_parameters_from_dict_to_flow_run(
        self,
        deployment,
        deployment_name,
        orion_client,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "deployment",
                "run",
                deployment_name,
                "--params",
                json.dumps({"name": "foo"}),
            ],
        )

        flow_runs = await orion_client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment.id])
            )
        )

        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.parameters == {"name": "foo"}


class TestDeploymentBuild:
    def patch_deployment_build_cli(self, monkeypatch):
        mock_build_from_flow = AsyncMock()

        # needed to handle `if deployment.storage` check
        ret = Mock()
        ret.storage = None
        mock_build_from_flow.return_value = ret

        monkeypatch.setattr(
            "prefect.cli.deployment.Deployment.build_from_flow", mock_build_from_flow
        )

        # not needed for test
        monkeypatch.setattr(
            "prefect.cli.deployment.create_work_queue_and_set_concurrency_limit",
            AsyncMock(),
        )

        return mock_build_from_flow

    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    @pytest.mark.parametrize("skip_upload", ["--skip-upload", None])
    def test_skip_upload_called_correctly(
        self, monkeypatch, patch_import, tmp_path, skip_upload
    ):
        mock_build_from_flow = self.patch_deployment_build_cli(monkeypatch)

        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]

        if skip_upload:
            cmd.append(skip_upload)

        invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs

        if skip_upload:
            assert build_kwargs["skip_upload"] == True
        else:
            assert build_kwargs["skip_upload"] == False
