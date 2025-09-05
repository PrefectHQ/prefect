import json
import sys
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from typer import Exit

from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId
from prefect.client.schemas.responses import DeploymentResponse
from prefect.client.schemas.schedules import IntervalSchedule
from prefect.settings import (
    PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
def interactive_console(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("prefect.cli.deployment.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar() -> str:
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@flow
def my_flow():
    pass


@pytest.fixture
def patch_import(monkeypatch: pytest.MonkeyPatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    def _import_object(path: str) -> Any:
        return fn

    monkeypatch.setattr("prefect.utilities.importtools.import_object", _import_object)
    return fn


@pytest.fixture
async def create_flojo_deployment(prefect_client: PrefectClient) -> UUID:
    @flow
    async def rence_griffith():
        pass

    flow_id = await prefect_client.create_flow(rence_griffith)
    schedule = DeploymentScheduleCreate(
        schedule=IntervalSchedule(interval=timedelta(seconds=10.76))
    )

    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        version="git-commit-hash",
        schedules=[schedule],
        parameters={"foo": "bar"},
        tags=["foo", "bar"],
        parameter_openapi_schema={},
    )
    return deployment_id


@pytest.fixture
async def flojo_deployment(
    create_flojo_deployment: UUID, prefect_client: PrefectClient
) -> DeploymentResponse:
    return await prefect_client.read_deployment(create_flojo_deployment)


def test_list_schedules(flojo_deployment: DeploymentResponse):
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


class TestDeploymentSchedules:
    @pytest.fixture(autouse=True)
    def enable_triggers(self):
        with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
            yield

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_interval_without_anchor_date(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "clear", "-y", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_no_schedule(self, commands: list[str]):
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
            expected_output_contains=["'schedules': []"],
            expected_code=0,
        )

    @pytest.mark.usefixtures("create_flojo_deployment")
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
        self, commands: list[str], error: str
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands,error",
        [
            [
                ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
                "Exactly one of `--interval`, `--rrule`, or `--cron` must be provided",
            ],
        ],
    )
    def test_set_schedule_with_no_schedule_options_raises(
        self, commands: list[str], error: str
    ):
        invoke_and_assert(
            [*commands],
            expected_code=1,
            expected_output_contains=error,
        )

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule_has_timezone(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule_with_timezone_arg(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_json_rrule_with_timezone_arg_overrides_if_passed_explicitly(
        self, commands: list[str]
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule_has_timezone(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule_with_timezone_arg(
        self, commands: list[str]
    ):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_str_literal_rrule_with_timezone_arg_overrides_if_passed_explicitly(
        self, commands: list[str]
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_updates_cron(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment-2"),
        ],
    )
    def test_set_schedule_deployment_not_found_raises(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_pausing_and_resuming_schedules_with_schedule_pause(
        self, flojo_deployment: DeploymentResponse
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_schedule_pause_deployment_not_found_raises(
        self, flojo_deployment: DeploymentResponse
    ):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands",
        [
            ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
        ],
    )
    def test_set_schedule_updating_anchor_date_respected(self, commands: list[str]):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
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
        self, commands: list[str], error: str
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    @pytest.mark.parametrize(
        "commands,error",
        [
            [
                ("deployment", "schedule", "create", "rence-griffith/test-deployment"),
                "The anchor date must be a valid date string.",
            ],
        ],
    )
    def test_set_schedule_invalid_interval_anchor_raises(
        self, commands: list[str], error: str
    ):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_create_schedule_replace_replaces_existing_schedules_many(self):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_create_schedule_replace_replaces_existing_schedule(self):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_create_schedule_replace_seeks_confirmation(self):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_create_schedule_replace_accepts_confirmation(self):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_clear_schedule_deletes(self):
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_clear_schedule_raises_if_deployment_does_not_exist(self):
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

    def test_delete_schedule_deletes(self, flojo_deployment: DeploymentResponse):
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

    def test_delete_schedule_raises_if_schedule_does_not_exist(
        self, flojo_deployment: DeploymentResponse
    ):
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
        self, flojo_deployment: DeploymentResponse
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

    @pytest.mark.usefixtures("create_flojo_deployment")
    def test_deployment_inspect_json_output(self):
        """Test deployment inspect command with JSON output flag."""
        result = invoke_and_assert(
            [
                "deployment",
                "inspect",
                "rence-griffith/test-deployment",
                "--output",
                "json",
            ],
            expected_code=0,
        )

        # Parse JSON output and verify it's valid JSON
        output_data = json.loads(result.stdout.strip())

        # Verify key fields are present
        assert "id" in output_data
        assert "name" in output_data
        assert "flow_id" in output_data

    @pytest.fixture
    async def create_multiple_deployments_with_schedules(
        self, prefect_client: PrefectClient
    ):
        """Create multiple deployments with active schedules for testing bulk operations."""

        @flow
        async def rence_griffith():
            pass

        flow_id = await prefect_client.create_flow(rence_griffith)
        deployments = []

        for i in range(3):
            deployment_id = await prefect_client.create_deployment(
                flow_id=flow_id,
                name=f"test-bulk-{i}",
                schedules=[
                    DeploymentScheduleCreate(
                        schedule=IntervalSchedule(interval=timedelta(seconds=3600)),
                        active=True,
                    )
                ],
            )
            deployment = await prefect_client.read_deployment(deployment_id)
            deployments.append(deployment)

        return deployments

    def test_pause_schedule_with_all_flag(
        self, create_multiple_deployments_with_schedules
    ):
        """Test pausing all deployment schedules with --all flag."""
        # First verify schedules are active
        for deployment in create_multiple_deployments_with_schedules:
            invoke_and_assert(
                ["deployment", "inspect", f"rence-griffith/{deployment.name}"],
                expected_output_contains=["'active': True"],
            )

        # Pause all schedules
        invoke_and_assert(
            ["deployment", "schedule", "pause", "--all"],
            expected_code=0,
            expected_output_contains=["Paused 3 deployment schedule(s)"],
        )

        # Verify all schedules are now inactive
        for deployment in create_multiple_deployments_with_schedules:
            invoke_and_assert(
                ["deployment", "inspect", f"rence-griffith/{deployment.name}"],
                expected_output_contains=["'active': False"],
            )

    def test_resume_schedule_with_all_flag(
        self, create_multiple_deployments_with_schedules
    ):
        """Test resuming all deployment schedules with --all flag."""
        # First pause all schedules
        invoke_and_assert(
            ["deployment", "schedule", "pause", "--all"],
            expected_code=0,
        )

        # Verify schedules are inactive
        for deployment in create_multiple_deployments_with_schedules:
            invoke_and_assert(
                ["deployment", "inspect", f"rence-griffith/{deployment.name}"],
                expected_output_contains=["'active': False"],
            )

        # Resume all schedules
        invoke_and_assert(
            ["deployment", "schedule", "resume", "--all"],
            expected_code=0,
            expected_output_contains=["Resumed 3 deployment schedule(s)"],
        )

        # Verify all schedules are now active
        for deployment in create_multiple_deployments_with_schedules:
            invoke_and_assert(
                ["deployment", "inspect", f"rence-griffith/{deployment.name}"],
                expected_output_contains=["'active': True"],
            )

    def test_pause_all_with_no_active_schedules(self, prefect_client: PrefectClient):
        """Test pausing all when there are no active schedules."""
        invoke_and_assert(
            ["deployment", "schedule", "pause", "--all"],
            expected_code=0,
            expected_output_contains=["No deployments found"],
        )

    def test_resume_all_with_no_inactive_schedules(
        self, create_multiple_deployments_with_schedules
    ):
        """Test resuming all when all schedules are already active."""
        # Ensure all schedules are active (they should be by default)
        invoke_and_assert(
            ["deployment", "schedule", "resume", "--all"],
            expected_code=0,
            expected_output_contains=["No inactive schedules found to resume"],
        )

    def test_pause_with_all_flag_and_deployment_name_raises(self):
        """Test that providing both --all and deployment name raises an error."""
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "pause",
                "--all",
                "some-flow/some-deployment",
                "12345678-1234-1234-1234-123456789012",
            ],
            expected_code=1,
            expected_output_contains=[
                "Cannot specify deployment name or schedule ID with --all"
            ],
        )

    def test_resume_with_all_flag_and_deployment_name_raises(self):
        """Test that providing both --all and deployment name raises an error."""
        invoke_and_assert(
            [
                "deployment",
                "schedule",
                "resume",
                "--all",
                "some-flow/some-deployment",
                "12345678-1234-1234-1234-123456789012",
            ],
            expected_code=1,
            expected_output_contains=[
                "Cannot specify deployment name or schedule ID with --all"
            ],
        )

    def test_pause_without_args_or_all_flag_raises(self):
        """Test that pause without arguments or --all flag raises an error."""
        invoke_and_assert(
            ["deployment", "schedule", "pause"],
            expected_code=1,
            expected_output_contains=[
                "Must provide deployment name and schedule ID, or use --all"
            ],
        )

    def test_resume_without_args_or_all_flag_raises(self):
        """Test that resume without arguments or --all flag raises an error."""
        invoke_and_assert(
            ["deployment", "schedule", "resume"],
            expected_code=1,
            expected_output_contains=[
                "Must provide deployment name and schedule ID, or use --all"
            ],
        )


class TestDeploymentRun:
    @pytest.fixture
    async def deployment_name(
        self, deployment: DeploymentResponse, prefect_client: PrefectClient
    ):
        flow = await prefect_client.read_flow(deployment.flow_id)
        return f"{flow.name}/{deployment.name}"

    def test_run_wraps_parameter_stdin_parsing_exception(self, deployment_name: str):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--params", "-"],
            expected_code=1,
            expected_output_contains="Failed to parse JSON",
            user_input="not-valid-json",
        )

    def test_run_wraps_parameter_stdin_empty(self, deployment_name: str):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--params", "-"],
            expected_code=1,
            expected_output_contains="No data passed to stdin",
        )

    def test_run_wraps_parameters_parsing_exception(self, deployment_name: str):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--params", "not-valid-json"],
            expected_code=1,
            expected_output_contains="Failed to parse JSON",
        )

    def test_wraps_parameter_json_parsing_exception(self, deployment_name: str):
        invoke_and_assert(
            ["deployment", "run", deployment_name, "--param", 'x="foo"1'],
            expected_code=1,
            expected_output_contains="Failed to parse JSON for parameter 'x'",
        )

    def test_validates_parameters_are_in_deployment_schema(
        self,
        deployment_name: str,
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
        deployment: DeploymentResponse,
        deployment_name: str,
        prefect_client: PrefectClient,
        given: Any,
        expected: Any,
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
        deployment: DeploymentResponse,
        deployment_name: str,
        prefect_client: PrefectClient,
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
        deployment: DeploymentResponse,
        deployment_name: str,
        prefect_client: PrefectClient,
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

    async def test_sets_templated_flow_run_name(
        self,
        deployment: DeploymentResponse,
        deployment_name: str,
        prefect_client: PrefectClient,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "deployment",
                "run",
                deployment_name,
                "--flow-run-name",
                "hello-{name}",
                "--param",
                "name=tester",
            ],
            expected_code=0,
        )

        flow_runs = await prefect_client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment.id])
            )
        )
        assert len(flow_runs) == 1
        assert flow_runs[0].name == "hello-tester"

    def test_raises_error_on_missing_template_param(self, deployment_name: str):
        run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "deployment",
                "run",
                deployment_name,
                "--flow-run-name",
                "hello-{missing}",
            ],
            expected_code=1,
            expected_output_contains="Missing parameter for flow run name: 'missing' is undefined",
        )


class TestDeploymentDelete:
    def test_delete_single_deployment(self, flojo_deployment: DeploymentResponse):
        invoke_and_assert(
            [
                "deployment",
                "delete",
                f"rence-griffith/{flojo_deployment.name}",
            ],
            expected_code=0,
        )

    @pytest.fixture
    async def setup_many_deployments(
        self,
        prefect_client: PrefectClient,
        flojo_deployment: DeploymentResponse,
    ):
        for i in range(3):
            await prefect_client.create_deployment(
                flow_id=flojo_deployment.flow_id,
                name=f"test-deployment-{i}",
            )

    @pytest.mark.usefixtures("setup_many_deployments")
    async def test_delete_all_deployments(self, prefect_client: PrefectClient):
        deployments = await prefect_client.read_deployments()
        assert len(deployments) > 0
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["deployment", "delete", "--all"],
            expected_code=0,
        )
        deployments = await prefect_client.read_deployments()
        assert len(deployments) == 0

    @pytest.mark.usefixtures("setup_many_deployments", "interactive_console")
    def test_delete_all_deployments_needs_confirmation_with_interactive_console(
        self,
    ):
        invoke_and_assert(
            ["deployment", "delete", "--all"],
            expected_code=0,
            user_input="y",
            expected_output_contains=[
                "Are you sure you want to delete",
                "Deleted",
                "deployments",
            ],
        )

    def test_delete_all_deployments_fails_if_name_or_id_provided(self):
        invoke_and_assert(
            ["deployment", "delete", "--all", "test-deployment"],
            expected_code=1,
            expected_output_contains="Cannot provide a deployment name or id when deleting all deployments.",
        )
