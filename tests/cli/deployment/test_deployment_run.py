import pendulum
import pytest
from pendulum.datetime import DateTime
from pendulum.tz.timezone import Timezone

import prefect
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
async def deployment_name(deployment, orion_client):
    flow = await orion_client.read_flow(deployment.flow_id)
    return f"{flow.name}/{deployment.name}"


@pytest.fixture
def frozen_now(monkeypatch):
    now = pendulum.now()
    monkeypatch.setattr("pendulum.now", lambda *_: now)
    yield now


@pytest.mark.skip
def test_both_start_in_and_start_at_raises():
    invoke_and_assert(
        command=["deployment", "run", "--start-in", "foo", "--start-at", "bar"],
        expected_code=1,
        expected_output="Expected optional start_in field or start_at field but not both.",
    )


@pytest.mark.skip
@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [
        ("12-1-22 5pm", "2022-12-01 17:00:00"),
        ("1/1/30", "2030-01-01 00:00:00"),
        ("13/1/20 13:31", "2020-01-13 13:31:00"),
        ("9pm December 31st 2022", "2022-12-31 21:00:00"),
        ("January 2nd 2023", "2023-01-02 00:00:00"),
    ],
)
async def test_start_at_option_displays_scheduled_start_time(
    deployment_name: str,
    orion_client: prefect.OrionClient,
    start_at: str,
    expected_start_time,
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


@pytest.mark.skip
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
async def test_start_in_option_schedules_flow_run_in_future(
    deployment_name: str,
    frozen_now,
    orion_client: prefect.OrionClient,
    start_in: str,
    expected_duration,
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

    flow_runs = await orion_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.state.is_scheduled()
    scheduled_time = flow_run.state.state_details.scheduled_time

    assert scheduled_time == expected_start_time


# working on
@pytest.mark.parametrize(
    "start_at,expected_start_time",
    [("12/20/2022 1am", DateTime(2022, 12, 20, 6, 0, 0, tzinfo=Timezone("UTC")))],
)
async def test_start_at_option_schedules_flow_run_in_future(
    deployment_name: str,
    start_at: str,
    expected_start_time: DateTime,
    orion_client: prefect.OrionClient,
):
    expected_display = expected_start_time.in_tz(
        pendulum.tz.local_timezone()
    ).to_datetime_string()

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

    flow_runs = await orion_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.state.is_scheduled()
    scheduled_time = flow_run.state.state_details.scheduled_time

    assert scheduled_time == expected_start_time


@pytest.mark.skip
@pytest.mark.parametrize(
    "start_in, expected_display",
    [
        ("10 minutes", "in 10 minutes"),
        ("5 days", "in 5 days"),
        ("3 seconds", "in a few seconds"),
        (None, "now"),
        ("1 year and 3 months", "in 1 year"),
        ("2 weeks & 1 day", "in 2 weeks"),
        ("27 hours + 4 mins", "in 1 day"),
    ],
)
async def test_start_in_displays_scheduled_start_time(
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


@pytest.mark.skip
@pytest.mark.parametrize(
    "start_at,expected_output",
    [
        ("foobar", "Unable to parse scheduled start time 'at foobar'."),
        ("1671483897", "Unable to parse scheduled start time 'at 1671483897'."),
        ("Jan 32nd 2023", "Unable to parse scheduled start time 'at Jan 32nd 2023'."),
        ("Jan 31st 20231", "Unable to parse scheduled start time 'at Jan 31st 20231'."),
        ("Octob 1st 2020", "Unable to parse scheduled start time 'at Octob 1st 2020'."),
        (
            "5:30pm PST",
            "Timezone not expected in 'at 5:30pm PST'. Timezone is inferred with pendulum.tz.local_timezone().",
        ),
    ],
)
def test_start_at_invalid_input(
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


def test_start_in_invalid_input(deployment_name: str):
    invoke_and_assert(
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-in",
            "foobar",
        ],
        expected_code=1,
        expected_output="Unable to parse scheduled start time 'in foobar'.",
    )


async def test_run_deployment_only_creates_one_flow_run(
    deployment_name: str, orion_client: prefect.OrionClient, deployment
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "run",
            deployment_name,
        ],
    )

    flow_runs = await orion_client.read_flow_runs()
    assert len(flow_runs) == 1
    flow_run = flow_runs[0]

    assert flow_run.deployment_id == deployment.id
