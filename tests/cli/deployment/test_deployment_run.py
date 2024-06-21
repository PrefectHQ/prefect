import uuid
from functools import partial
from unittest.mock import ANY, AsyncMock

import pendulum
import pytest
from pendulum.datetime import DateTime
from pendulum.duration import Duration

import prefect
from prefect.client.schemas.objects import FlowRun
from prefect.exceptions import FlowRunWaitTimeout
from prefect.states import Completed, Failed
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
async def deployment_name(deployment, prefect_client):
    flow = await prefect_client.read_flow(deployment.flow_id)
    return f"{flow.name}/{deployment.name}"


@pytest.fixture
def frozen_now(monkeypatch):
    now = pendulum.now("UTC")
    monkeypatch.setattr("pendulum.now", lambda *_: now)
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
    deployment,
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
        ("5-17-43 5:30pm UTC", pendulum.parse("2043-05-17T17:30:00")),
        ("5-20-2020 5:30pm EDT", pendulum.parse("2020-05-20T17:30:00", tz="EST5EDT")),
        ("01/31/43 5:30 CST", pendulum.parse("2043-01-31T05:30:00", tz="CST6CDT")),
        ("5-20-43 5:30pm PDT", pendulum.parse("2043-05-20T17:30:00", tz="PST8PDT")),
        ("01/31/43 5:30 PST", pendulum.parse("2043-01-31T05:30:00", tz="PST8PDT")),
    ],
)
async def test_start_at_option_with_tz_displays_scheduled_start_time(
    deployment_name: str, start_at: str, expected_start_time: DateTime
):
    expected_start_time_local = expected_start_time.in_tz(pendulum.tz.local_timezone())
    expected_display = (
        expected_start_time_local.to_datetime_string()
        + " "
        + expected_start_time_local.tzname()
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            start_at,
        ],
        expected_output_contains=["Scheduled start time:", expected_display],
    )


@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        (
            "12/20/2022 1am",
            DateTime(2022, 12, 20, 1, 0, 0, tzinfo=pendulum.tz.local_timezone()),
        ),
        (
            "1-1-2020",
            DateTime(2020, 1, 1, 0, 0, 0, tzinfo=pendulum.tz.local_timezone()),
        ),
        (
            "5 June 2015",
            DateTime(2015, 6, 5, 0, 0, 0, tzinfo=pendulum.tz.local_timezone()),
        ),
    ],
)
async def test_start_at_option_schedules_flow_run(
    deployment_name: str,
    start_at: str,
    expected_start_time: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
):
    expected_display = expected_start_time.to_datetime_string()

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

    assert scheduled_time == expected_start_time


@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        ("5-17-43 5:30pm UTC", pendulum.parse("2043-05-17T17:30:00")),
        ("5-20-2020 5:30pm EDT", pendulum.parse("2020-05-20T17:30:00", tz="EST5EDT")),
        ("01/31/43 5:30 CST", pendulum.parse("2043-01-31T05:30:00", tz="CST6CDT")),
        ("5-20-43 5:30pm PDT", pendulum.parse("2043-05-20T17:30:00", tz="PST8PDT")),
        ("01/31/43 5:30 PST", pendulum.parse("2043-01-31T05:30:00", tz="PST8PDT")),
    ],
)
async def test_start_at_option_with_tz_schedules_flow_run(
    deployment_name: str,
    start_at: str,
    expected_start_time: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
):
    expected_start_time_local = expected_start_time.in_tz(pendulum.tz.local_timezone())
    expected_display = (
        expected_start_time_local.to_datetime_string()
        + " "
        + expected_start_time_local.tzname()
    )

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

    assert scheduled_time == expected_start_time


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
        ("20 minutes", "in 20 minutes"),
        ("5 days", "in 5 days"),
        ("3 seconds", "in a few seconds"),
        (None, "now"),
        ("1 year and 3 months", "in 1 year"),
        ("2 weeks & 1 day", "in 2 weeks"),
        ("27 hours + 4 mins", "in 1 day"),
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
        ("10 minutes", pendulum.duration(minutes=10)),
        ("5 days", pendulum.duration(days=5)),
        ("3 seconds", pendulum.duration(seconds=3)),
        (None, pendulum.duration(seconds=0)),
        ("1 year and 3 months", pendulum.duration(years=1, months=3)),
        ("2 weeks & 1 day", pendulum.duration(weeks=2, days=1)),
        ("27 hours + 4 mins", pendulum.duration(days=1, hours=3, minutes=4)),
    ],
)
async def test_start_in_option_schedules_flow_run(
    deployment_name: str,
    frozen_now: DateTime,
    prefect_client: prefect.client.orchestration.PrefectClient,
    start_in: str,
    expected_duration: Duration,
):
    expected_start_time = frozen_now + expected_duration
    expected_display = expected_start_time.in_tz(
        pendulum.tz.local_timezone()
    ).to_datetime_string()

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

    assert scheduled_time == expected_start_time


@pytest.mark.parametrize(
    "start_time,expected_start_time",
    [
        (
            "12/20/2030 1am",
            DateTime(2030, 12, 20, 1, 0, 0, tzinfo=pendulum.tz.local_timezone()),
        ),
        (
            "1-1-2020",
            DateTime(2020, 1, 1, 0, 0, 0, tzinfo=pendulum.tz.local_timezone()),
        ),
        (
            "5 June 2015",
            DateTime(2015, 6, 5, 0, 0, 0, tzinfo=pendulum.tz.local_timezone()),
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
    expected_display = expected_start_time.to_datetime_string()

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

    assert start_at_scheduled_time == expected_start_time
    assert start_in_scheduled_time == expected_start_time


async def test_print_parameter_validation_error(deployment_with_parameter_schema, flow):
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
    monkeypatch,
    deployment,
    deployment_name,
    prefect_client,
    test_case,
    mock_wait_for_flow_run,
    timeout,
    expected_output,
    expected_code,
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
