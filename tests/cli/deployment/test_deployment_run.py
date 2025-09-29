from __future__ import annotations

import sys
import uuid
from datetime import datetime
from functools import partial
from typing import Any, Generator
from unittest.mock import ANY, AsyncMock
from zoneinfo import ZoneInfo

import pytest
from whenever import DateDelta, DateTimeDelta, TimeDelta, ZonedDateTime

import prefect
from prefect.client.schemas.objects import Deployment, FlowRun
from prefect.exceptions import FlowRunWaitTimeout
from prefect.states import Completed, Failed
from prefect.testing.cli import invoke_and_assert
from prefect.types._datetime import (
    DateTime,
    Duration,
    in_local_tz,
    parse_datetime,
    to_datetime_string,
)
from prefect.types._datetime import now as now_fn
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
async def deployment_name(
    deployment: Deployment,
    prefect_client: prefect.client.orchestration.PrefectClient,
) -> str:
    flow = await prefect_client.read_flow(deployment.flow_id)
    return f"{flow.name}/{deployment.name}"


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> Generator[DateTime, None, None]:
    now = now_fn("UTC")
    monkeypatch.setattr("prefect.types._datetime.now", lambda *_: now)  # type: ignore
    yield now


def completed_flow_run():
    return FlowRun(
        id=uuid.uuid4(), flow_id=uuid.uuid4(), state=Completed(), work_pool_id=None
    )


def failed_flow_run():
    return FlowRun(
        id=uuid.uuid4(), flow_id=uuid.uuid4(), state=Failed(), work_pool_id=None
    )


async def test_run_deployment_only_creates_one_flow_run(
    deployment_name: str,
    prefect_client: prefect.client.orchestration.PrefectClient,
    deployment: Deployment,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
        ],
    )

    flow_runs = await prefect_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.deployment_id == deployment.id


def test_both_start_in_and_start_at_raises():
    invoke_and_assert(
        command=["deployment", "run", "--start-in", "foo", "--start-at", "bar"],
        expected_code=1,
        expected_output=(
            "Only one of `--start-in` or `--start-at` can be set, not both."
        ),
    )


@pytest.mark.parametrize(
    "start_at,expected_output",
    [
        ("foobar", "Unable to parse scheduled start time 'at foobar'."),
        ("1671483897", "Unable to parse scheduled start time 'at 1671483897'."),
        ("Jan 32nd 2023", "Unable to parse scheduled start time 'at Jan 32nd 2023'."),
        ("Jan 31st 20231", "Unable to parse scheduled start time 'at Jan 31st 20231'."),
        ("Octob 1st 2020", "Unable to parse scheduled start time 'at Octob 1st 2020'."),
    ],
)
def test_start_at_option_invalid_input(
    deployment_name: str, start_at: str, expected_output: str
):
    invoke_and_assert(
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_at,
        ],
        expected_code=1,
        expected_output=expected_output,
    )


@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        ("12-1-2022 5pm", "2022-12-01 17:00:00"),
        ("1/1/30", "2030-01-01 00:00:00"),
        ("13/1/2020 13:31", "2020-01-13 13:31:00"),
        ("9pm December 31st 2022", "2022-12-31 21:00:00"),
        ("January 2nd 2043", "2043-01-02 00:00:00"),
    ],
)
async def test_start_at_option_displays_scheduled_start_time(
    deployment_name: str,
    start_at: str,
    expected_start_time: str,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_at,
        ],
        expected_output_contains=["Scheduled start time:", expected_start_time],
    )


@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        ("5-17-43 5:30pm UTC", parse_datetime("2043-05-17T17:30:00")),
        ("5-20-2020 5:30pm EDT", parse_datetime("2020-05-20T17:30:00-04:00")),
        ("01/31/43 5:30 CST", parse_datetime("2043-01-31T05:30:00-06:00")),
        ("5-20-43 5:30pm PDT", parse_datetime("2043-05-20T17:30:00-07:00")),
        ("01/31/43 5:30 PST", parse_datetime("2043-01-31T05:30:00-08:00")),
    ],
)
async def test_start_at_option_with_tz_displays_scheduled_start_time(
    deployment_name: str, start_at: str, expected_start_time: DateTime
):
    expected_start_time_local = in_local_tz(expected_start_time)

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_at,
        ],
        expected_output_contains=[
            "Scheduled start time:",
            to_datetime_string(expected_start_time_local),
        ],
    )


@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        (
            "12/20/2022 1am",
            DateTime(2022, 12, 20, 1, 0, 0),
        ),
        (
            "1-1-2020",
            DateTime(2020, 1, 1, 0, 0, 0),
        ),
        (
            "5 June 2015",
            DateTime(2015, 6, 5, 0, 0, 0),
        ),
    ],
)
async def test_start_at_option_schedules_flow_run(
    deployment_name: str,
    start_at: str,
    expected_start_time: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
):
    expected_display = to_datetime_string(expected_start_time)

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_at,
        ],
        expected_output_contains=f"Scheduled start time: {expected_display}",
    )

    flow_runs = await prefect_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.state.is_scheduled()
    scheduled_time = flow_run.state.state_details.scheduled_time

    assert scheduled_time == expected_start_time.astimezone(ZoneInfo("UTC"))


@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        ("5-17-43 5:30pm UTC", parse_datetime("2043-05-17T17:30:00")),
        ("5-20-2020 5:30pm EDT", parse_datetime("2020-05-20T17:30:00-04:00")),
        ("01/31/43 5:30 CST", parse_datetime("2043-01-31T05:30:00-06:00")),
        ("5-20-43 5:30pm PDT", parse_datetime("2043-05-20T17:30:00-07:00")),
        ("01/31/43 5:30 PST", parse_datetime("2043-01-31T05:30:00-08:00")),
    ],
)
async def test_start_at_option_with_tz_schedules_flow_run(
    deployment_name: str,
    start_at: str,
    expected_start_time: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
):
    expected_start_time_local = in_local_tz(expected_start_time)

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_at,
        ],
        expected_output_contains=f"Scheduled start time: {to_datetime_string(expected_start_time_local)}",
    )

    flow_runs = await prefect_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.state.is_scheduled()
    scheduled_time = flow_run.state.state_details.scheduled_time

    assert scheduled_time == expected_start_time.replace(microsecond=0)


@pytest.mark.parametrize(
    "start_in,expected_output",
    [
        ("foobar", "Unable to parse scheduled start time 'in foobar'."),
        ("1671483897", "Unable to parse scheduled start time 'in 1671483897'."),
        ("Jan 32nd 2023", "Unable to parse scheduled start time 'in Jan 32nd 2023'."),
        ("Jan 31st 20231", "Unable to parse scheduled start time 'in Jan 31st 20231'."),
        ("Octob 1st 2020", "Unable to parse scheduled start time 'in Octob 1st 2020'."),
    ],
)
def test_start_in_option_invalid_input(
    deployment_name: str, start_in: str, expected_output: str
):
    invoke_and_assert(
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-in",
            start_in,
        ],
        expected_code=1,
        expected_output=expected_output,
    )


@pytest.mark.parametrize(
    "start_in, expected_display",
    [
        (
            "20 minutes",
            "in 19 minutes" if sys.version_info < (3, 13) else "19 minutes from now",
        ),  # difference due to different libraries used for parsing and display
        ("5 days", "in 5 days" if sys.version_info < (3, 13) else "4 days from now"),
        (
            "3 seconds",
            "in a few seconds" if sys.version_info < (3, 13) else "2 seconds from now",
        ),
        (None, "now"),
        (
            "1 year and 3 months",
            "in 1 year" if sys.version_info < (3, 13) else "1 year, 2 months from now",
        ),
        (
            "2 weeks & 1 day",
            "in 2 weeks" if sys.version_info < (3, 13) else "14 days from now",
        ),
        (
            "27 hours + 4 mins",
            "in 1 day" if sys.version_info < (3, 13) else "a day from now",
        ),
    ],
)
async def test_start_in_option_displays_scheduled_start_time(
    deployment_name: str,
    start_in: str,
    expected_display: str,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-in",
            start_in,
        ],
        expected_output_contains=["Scheduled start time:", expected_display],
    )


@pytest.mark.parametrize(
    "start_in,expected_duration",
    [
        ("10 minutes", TimeDelta(minutes=10)),
        ("5 days", DateDelta(days=5)),
        ("3 seconds", TimeDelta(seconds=3)),
        (None, TimeDelta(seconds=0)),
        ("1 year and 3 months", DateDelta(years=1, months=3)),
        ("2 weeks & 1 day", DateDelta(weeks=2, days=1)),
        ("27 hours + 4 mins", DateTimeDelta(days=1, hours=3, minutes=4)),
    ],
)
async def test_start_in_option_schedules_flow_run(
    deployment_name: str,
    frozen_now: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
    start_in: str,
    expected_duration: Duration,
):
    # coerce to a datetime whenever will accept
    frozen_now_py = datetime.fromisoformat(frozen_now.isoformat())
    frozen_now_py_tz = frozen_now_py.replace(
        tzinfo=ZoneInfo(frozen_now_py.tzname() or "UTC")
    )
    expected_start_time = (
        ZonedDateTime.from_py_datetime(frozen_now_py_tz)
        .add(expected_duration)
        .py_datetime()
    )
    expected_display = to_datetime_string(in_local_tz(expected_start_time))

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-in",
            start_in,
        ],
        expected_output_contains=f"Scheduled start time: {expected_display}",
    )

    flow_runs = await prefect_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.state.is_scheduled()
    scheduled_time = flow_run.state.state_details.scheduled_time

    assert scheduled_time.replace(microsecond=0) == expected_start_time.replace(
        microsecond=0
    )


@pytest.mark.parametrize(
    "start_time,expected_start_time",
    [
        (
            "12/20/2030 1am",
            DateTime(2030, 12, 20, 1, 0, 0),
        ),
        (
            "1-1-2020",
            DateTime(2020, 1, 1, 0, 0, 0),
        ),
        (
            "5 June 2015",
            DateTime(2015, 6, 5, 0, 0, 0),
        ),
    ],
)
async def test_date_as_start_in_option_schedules_flow_run_equal_to_start_at(
    deployment_name: str,
    start_time: str,
    expected_start_time: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
):
    """
    Passing a date (rather than something like `5 minutes`) as an argument to start_in results in a scheduled flow run,
    equivalent to passing the same date as a start_at argument.

    Example:
    `prefect deployment run --start-in 12/20/2022` and
    `prefect deployment run --start-at 12/20/2022`
    have the same scheduled start time.

    The result of the design is unintentional and this test documents the observed
    output.
    """
    expected_display = to_datetime_string(expected_start_time, include_tz=False)

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_time,
        ],
        expected_output_contains=f"Scheduled start time: {expected_display}",
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-in",
            start_time,
        ],
        expected_output_contains=f"Scheduled start time: {expected_display}",
    )

    flow_runs = await prefect_client.read_flow_runs()

    assert len(flow_runs) == 2
    start_at_flow_run = flow_runs[0]
    start_in_flow_run = flow_runs[1]

    assert start_at_flow_run.state.is_scheduled()
    assert start_in_flow_run.state.is_scheduled()
    start_at_scheduled_time = start_at_flow_run.state.state_details.scheduled_time
    start_in_scheduled_time = start_in_flow_run.state.state_details.scheduled_time

    assert start_at_scheduled_time == expected_start_time.astimezone(ZoneInfo("UTC"))
    assert start_in_scheduled_time == expected_start_time.astimezone(ZoneInfo("UTC"))


async def test_print_parameter_validation_error(
    deployment_with_parameter_schema: Deployment,
    flow: Any,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            f"{flow.name}/{deployment_with_parameter_schema.name}",
            "-p",
            "x=1",
        ],
        expected_code=1,
        expected_output_contains=(
            "Validation failed for field 'x'. Failure reason: 1 is not of type 'string'"
        ),
    )


@pytest.mark.parametrize(
    "test_case, mock_wait_for_flow_run, timeout, expected_output, expected_code",
    [
        (
            "pass",
            AsyncMock(return_value=completed_flow_run()),
            None,
            "Flow run finished successfully",
            0,
        ),
        (
            "fail",
            AsyncMock(return_value=failed_flow_run()),
            None,
            "Flow run finished in state 'Failed'",
            1,
        ),
        (
            "timeout",
            AsyncMock(side_effect=FlowRunWaitTimeout("Timeout occurred")),
            10,
            "Timeout occurred",
            1,
        ),
    ],
    ids=["watch-pass", "watch-fail", "watch-timeout"],
)
async def test_run_deployment_watch(
    monkeypatch: pytest.MonkeyPatch,
    deployment: Deployment,
    deployment_name: str,
    prefect_client: prefect.client.orchestration.PrefectClient,
    test_case: str,
    mock_wait_for_flow_run: AsyncMock,
    timeout: int | None,
    expected_output: str,
    expected_code: int,
):
    monkeypatch.setattr(
        "prefect.cli.deployment.wait_for_flow_run", mock_wait_for_flow_run
    )

    deployment_run_with_watch_command = partial(
        invoke_and_assert,
        command=["deployment", "run", deployment_name, "--watch"]
        + (["--watch-timeout", str(timeout)] if timeout else [])
        + ["--tag", "cool-tag"],
        expected_output_contains=expected_output,
        expected_code=expected_code,
    )

    if test_case == "timeout":
        with pytest.raises(FlowRunWaitTimeout):
            await run_sync_in_worker_thread(deployment_run_with_watch_command)
    else:
        await run_sync_in_worker_thread(deployment_run_with_watch_command)

    assert len(flow_runs := await prefect_client.read_flow_runs()) == 1
    flow_run = flow_runs[0]
    assert flow_run.deployment_id == deployment.id

    assert flow_run.state.is_scheduled()

    assert set(flow_run.tags) == set(["cool-tag", "test"])
    mock_wait_for_flow_run.assert_awaited_once_with(
        flow_run.id,
        timeout=timeout,
        poll_interval=ANY,
        log_states=ANY,
    )


@pytest.mark.parametrize("arg_name", ["-jv", "--job-variable"])
async def test_deployment_runs_with_job_variables(
    deployment_name: str,
    prefect_client: prefect.client.orchestration.PrefectClient,
    arg_name: str,
):
    """
    Verify that job variables created on the CLI are passed onto the flow run.
    """
    job_vars = {"foo": "bar", "1": 2, "baz": "qux"}

    # assemble the command string from the job_vars
    job_vars_command = ""
    for k, v in job_vars.items():
        job_vars_command += f"{arg_name} {k}={v} "

    command = ["deployment", "run", deployment_name]
    command.extend(job_vars_command.split())

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=command,
        expected_output_contains=f"Job Variables: {job_vars}",
    )

    flow_runs = await prefect_client.read_flow_runs()
    this_run = flow_runs[0]
    assert this_run.job_variables == job_vars


async def test_deployment_run_without_parameter_openapi_schema(
    flow: Any,
    prefect_client: prefect.client.orchestration.PrefectClient,
):
    """
    Verify that deployments created without a parameter_openapi_schema
    can still be run via the CLI without crashing.

    Regression test for issue where deployments created via client.create_deployment
    without an explicit parameter_openapi_schema would cause a KeyError when
    running via `prefect deployment run`.
    """
    flow_id = await prefect_client.create_flow(flow=flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment-no-schema",
    )

    deployment = await prefect_client.read_deployment(deployment_id)
    deployment_name = f"{flow.name}/{deployment.name}"

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=["deployment", "run", deployment_name],
        expected_output_contains="Created flow run",
    )

    flow_runs = await prefect_client.read_flow_runs()
    assert len(flow_runs) == 1
    assert flow_runs[0].deployment_id == deployment_id
