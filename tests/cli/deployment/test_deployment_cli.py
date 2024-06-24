import json
from datetime import timedelta

import pytest

from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId
from prefect.client.schemas.schedules import IntervalSchedule
from prefect.settings import (
    PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@flow
def my_flow():
    pass


@pytest.fixture
def patch_import(monkeypatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    monkeypatch.setattr("prefect.utilities.importtools.import_object", lambda path: fn)
    return fn


class TestDeploymentSchedules:
    @pytest.fixture(autouse=True)
    def enable_triggers(self):
        with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
            yield

    @pytest.fixture
    async def flojo(self, prefect_client):
        @flow
        async def rence_griffith():
            pass

        flow_id = await prefect_client.create_flow(rence_griffith)
        old_record = IntervalSchedule(interval=timedelta(seconds=10.76))

        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="test-deployment",
            version="git-commit-hash",
            schedule=old_record,
            parameters={"foo": "bar"},
            tags=["foo", "bar"],
            parameter_openapi_schema={},
        )
        return deployment_id

    @pytest.fixture
    async def flojo_deployment(self, flojo, prefect_client):
        return await prefect_client.read_deployment(flojo)

    def test_list_schedules(self, flojo_deployment):
        create_commands = [
            "deployment",
            "schedule",
            "create",
            "rence-griffith/test-deployment",
        ]

        invoke_and_assert(
            [
                *create_commands,
                "--cron",
                "5 4 * * *",
            ],
            expected_code=0,
        )

        invoke_and_assert(
            [
                *create_commands,
                "--rrule",
                '{"rrule": "RRULE:FREQ=HOURLY"}',
            ],
            expected_code=0,
        )

        invoke_and_assert(
            ["deployment", "schedule", "ls", "rence-griffith/test-deployment"],
            expected_code=0,
            expected_output_contains=[
                str(flojo_deployment.schedules[0].id)[:8],
                "interval: 0:00:10.760000s",
                "cron: 5 4 * * *",
                "rrule: RRULE:FREQ=HOURLY",
                "True",
            ],
            expected_output_does_not_contain="False",
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_interval_without_anchor_date(self, flojo, commands):
        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 10.76,"],  # 100 m record
            expected_code=0,
        )

        invoke_and_assert(
            [
                *commands,
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
            expected_output_contains=[
                "'interval': 10.49,"
            ],  # flo-jo breaks the world record
            expected_code=0,
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "clear", "-y", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_no_schedule(self, flojo, commands):
        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 10.76,"],  # 100 m record
            expected_code=0,
        )

        invoke_and_assert(
            [
                *commands,
            ],
            expected_code=0,
            expected_output_contains=(
                "Cleared all schedules for deployment rence-griffith/test-deployment"
            ),
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_does_not_contain=["'interval': 10.76,"],
            expected_output_contains=["'schedule': None"],
            expected_code=0,
        )

    @pytest.mark.parametrize(
        "commands,error",
        [
            [
                ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
                "Exactly one of `--interval`, `--rrule`, or `--cron` must be provided",
            ],
        ],
    )
    def test_set_schedule_with_too_many_schedule_options_raises(
        self, flojo, commands, error
    ):
        invoke_and_assert(
            [
                *commands,
                "--interval",
                "424242",
                "--cron",
                "i dont know cron syntax dont judge",
            ],
            expected_code=1,
            expected_output_contains=error,
        )

    @pytest.mark.parametrize(
        "commands,error",
        [
            [
                ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
                "Exactly one of `--interval`, `--rrule`, or `--cron` must be provided",
            ],
        ],
    )
    def test_set_schedule_with_no_schedule_options_raises(self, flojo, commands, error):
        invoke_and_assert(
            [*commands],
            expected_code=1,
            expected_output_contains=error,
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                (
                    '{"rrule":'
                    ' "DTSTART:20300910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"}'
                ),
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["UTC"],
            expected_code=0,
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule_has_timezone(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                (
                    '{"rrule":'
                    ' "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",'
                    ' "timezone": "America/New_York"}'
                ),
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
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

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule_with_timezone_arg(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                (
                    '{"rrule":'
                    ' "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"}'
                ),
                "--timezone",
                "Asia/Seoul",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
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

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule_with_timezone_arg_overrides_if_passed_explicitly(
        self, flojo, commands
    ):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                (
                    '{"rrule":'
                    ' "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",'
                    ' "timezone": "America/New_York"}'
                ),
                "--timezone",
                "Asia/Seoul",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
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

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["UTC"],
            expected_code=0,
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule_has_timezone(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                "DTSTART;TZID=US-Eastern:19970902T090000\nRRULE:FREQ=DAILY;COUNT=10",
            ],
            expected_code=1,
            expected_output_contains=(
                "You can provide a timezone by providing a dict with a `timezone` key"
                " to the --rrule option"
            ),
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule_with_timezone_arg(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",
                "--timezone",
                "Asia/Seoul",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule_with_timezone_arg_overrides_if_passed_explicitly(
        self, flojo, commands
    ):
        invoke_and_assert(
            [
                *commands,
                "--rrule",
                "DTSTART;TZID=US-Eastern:19970902T090000\nRRULE:FREQ=DAILY;COUNT=10",
                "--timezone",
                "Asia/Seoul",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
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

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_updates_cron(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--cron",
                "5 4 * * *",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["5 4 * * *"],
            expected_code=0,
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment-2"),
        ],
    )
    def test_set_schedule_deployment_not_found_raises(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--cron",
                "5 4 * * *",
            ],
            expected_code=1,
            expected_output_contains=[
                "Deployment 'rence-griffith/test-deployment-2' not found!"
            ],
        )

    def test_pausing_and_resuming_schedules_with_schedule_pause(
        self, flojo, flojo_deployment
    ):
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "pause",
                "rence-griffith/test-deployment",
                str(flojo_deployment.schedules[0].id),
            ],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'active': False"],
        )

        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "resume",
                "rence-griffith/test-deployment",
                str(flojo_deployment.schedules[0].id),
            ],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'active': True"],
        )

    def test_schedule_pause_deployment_not_found_raises(self, flojo, flojo_deployment):
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "pause",
                "rence-griffith/test-deployment-2",
                str(flojo_deployment.schedules[0].id),
            ],
            expected_code=1,
            expected_output_contains=[
                "Deployment 'rence-griffith/test-deployment-2' not found!"
            ],
        )

    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_updating_anchor_date_respected(self, flojo, commands):
        invoke_and_assert(
            [
                *commands,
                "--interval",
                "1800",
                "--anchor-date",
                "2040-01-01T00:00:00",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'anchor_date': '2040-01-01T00:00:00Z'"],
        )

    @pytest.mark.parametrize(
        "commands,error",
        [
            [
                ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
                "An anchor date can only be provided with an interval schedule",
            ],
        ],
    )
    def test_set_schedule_updating_anchor_date_without_interval_raises(
        self, flojo, commands, error
    ):
        invoke_and_assert(
            [
                *commands,
                "--cron",
                "5 4 * * *",
                "--anchor-date",
                "2040-01-01T00:00:00",
            ],
            expected_code=1,
            expected_output_contains=error,
        )

    @pytest.mark.parametrize(
        "commands,error",
        [
            [
                ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
                "The anchor date must be a valid date string.",
            ],
        ],
    )
    def test_set_schedule_invalid_interval_anchor_raises(self, flojo, commands, error):
        invoke_and_assert(
            [
                *commands,
                "--interval",
                "50",
                "--anchor-date",
                "bad date string",
            ],
            expected_code=1,
            expected_output_contains=error,
        )

    def test_create_schedule_replace_replaces_existing_schedules_many(self, flojo):
        create_args = [
            "deployment",
            "schedule",
            "create",
            "rence-griffith/test-deployment",
            "--interval",
        ]

        invoke_and_assert(
            [
                *create_args,
                "90",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                *create_args,
                "1800",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 90.0,", "'interval': 1800.0,"],
            expected_code=0,
        )

        invoke_and_assert(
            [*create_args, "10", "--replace", "-y"],
            expected_code=0,
            expected_output_contains="Replaced existing deployment schedules with new schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 10.0,"],
            expected_output_does_not_contain=[
                "'interval': 90.0,",
                "'interval': 1800.0,",
            ],
            expected_code=0,
        )

    def test_create_schedule_replace_replaces_existing_schedule(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "clear",
                "rence-griffith/test-deployment",
                "-y",
            ],
            expected_code=0,
            expected_output_contains="Cleared all schedules",
        )

        create_args = [
            "deployment",
            "schedule",
            "create",
            "rence-griffith/test-deployment",
            "--interval",
        ]

        invoke_and_assert(
            [
                *create_args,
                "90",
            ],
            expected_code=0,
            expected_output_contains="Created deployment schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 90.0,"],
            expected_code=0,
        )

        invoke_and_assert(
            [*create_args, "10", "--replace", "-y"],
            expected_code=0,
            expected_output_contains="Replaced existing deployment schedule with new schedule!",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 10.0,"],
            expected_output_does_not_contain=["'interval': 1800.0,"],
            expected_code=0,
        )

    def test_create_schedule_replace_seeks_confirmation(self, flojo):
        deployment_name = "rence-griffith/test-deployment"
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "create",
                deployment_name,
                "--interval",
                "60",
                "--replace",
            ],
            user_input="N",
            expected_code=1,
            expected_output_contains=f"Are you sure you want to replace 1 schedule for {deployment_name}?",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 10.76,"],  # original schedule
            expected_code=0,
        )

    def test_create_schedule_replace_accepts_confirmation(self, flojo):
        deployment_name = "rence-griffith/test-deployment"
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "create",
                deployment_name,
                "--interval",
                "60",
                "--replace",
            ],
            user_input="y",
            expected_code=0,
            expected_output_contains=f"Are you sure you want to replace 1 schedule for {deployment_name}?",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'interval': 60.0,"],  # new schedule
            expected_output_does_not_contain=[
                "'interval': 10.76,"
            ],  # original schedule
            expected_code=0,
        )

    def test_clear_schedule_deletes(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'schedule': {"],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "clear",
                "-y",
                "rence-griffith/test-deployment",
            ],
            expected_code=0,
            expected_output_contains="Cleared all schedules for deployment",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'schedules': []"],
            expected_code=0,
        )

    def test_clear_schedule_raises_if_deployment_does_not_exist(self, flojo):
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "clear",
                "-y",
                "rence-griffith/not-a-real-deployment",
            ],
            expected_code=1,
            expected_output_contains=(
                "Deployment 'rence-griffith/not-a-real-deployment' not found!"
            ),
        )

    def test_delete_schedule_deletes(self, flojo_deployment):
        schedule_id = str(flojo_deployment.schedules[0].id)

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'schedule': {"],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "delete",
                "-y",
                "rence-griffith/test-deployment",
                schedule_id,
            ],
            expected_code=0,
            expected_output_contains="Deleted deployment schedule",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'schedules': []"],
            expected_code=0,
        )

    def test_delete_schedule_raises_if_schedule_does_not_exist(self, flojo_deployment):
        schedule_id = str(flojo_deployment.schedules[0].id)

        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "delete",
                "-y",
                "rence-griffith/test-deployment",
                schedule_id,
            ],
            expected_code=0,
            expected_output_contains=f"Deleted deployment schedule {schedule_id}",
        )

        invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
            ],
            expected_output_contains=["'schedules': []"],
            expected_code=0,
        )

        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "delete",
                "-y",
                "rence-griffith/test-deployment",
                schedule_id,
            ],
            expected_code=1,
            expected_output_contains="Deployment schedule not found!",
        )

    def test_delete_schedule_raises_if_deployment_does_not_exist(
        self, flojo_deployment
    ):
        schedule_id = str(flojo_deployment.schedules[0].id)

        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "delete",
                "-y",
                "rence-griffith/not-a-real-deployment",
                schedule_id,
            ],
            expected_code=1,
            expected_output_contains=(
                "Deployment rence-griffith/not-a-real-deployment not found!"
            ),
        )


class TestDeploymentRun:
    @pytest.fixture
    async def deployment_name(self, deployment, prefect_client):
        flow = await prefect_client.read_flow(deployment.flow_id)
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
            expected_output_contains="Failed to parse JSON for parameter 'x'",
        )

    def test_validates_parameters_are_in_deployment_schema(
        self,
        deployment_name,
    ):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--param", "x=test"],
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
        self,
        deployment,
        deployment_name,
        prefect_client: PrefectClient,
        given,
        expected,
    ):
        """
        This test ensures the parameters are set on the created flow run and that
        data types are cast correctly.
        """

        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["deployment", "run", deployment_name, "--param", f"name={given}"],
        )

        flow_runs = await prefect_client.read_flow_runs(
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
        prefect_client,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["deployment", "run", deployment_name, "--params", "-"],
            json.dumps({"name": "foo"}),  # stdin
        )

        flow_runs = await prefect_client.read_flow_runs(
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
        prefect_client,
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

        flow_runs = await prefect_client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment.id])
            )
        )

        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.parameters == {"name": "foo"}
