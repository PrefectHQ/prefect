from datetime import timedelta

import pytest

from prefect import flow
from prefect.deployments import Deployment
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.testing.cli import invoke_and_assert


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
