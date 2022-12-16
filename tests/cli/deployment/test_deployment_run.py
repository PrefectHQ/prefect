import dateparser
import pendulum
import pytest

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


def test_both_start_in_and_start_at_raises():
    invoke_and_assert(
        command=["deployment", "run", "--start-in", "foo", "--start-at", "bar"],
        expected_code=1,
        expected_output="Expected optional start_in field or start_at field but not both.",
    )


def test_run_with_bygone_start_at_arg_begins_immediately():
    ...


def test_run_with_no_start_at_or_start_in_arg_begins_immediately():
    ...


def test_start_at_arg_correctly_parsed():
    ...


@pytest.mark.parametrize(
    "start_in,expected_duration",
    [
        ("10 minutes", pendulum.duration(minutes=10)),
        ("5 days", pendulum.duration(days=5)),
    ],
)
async def test_start_in_option_scheduled_flow_run_in_future(
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


def test_displays_scheduled_start_time(deployment_name: str, monkeypatch):
    monkeypatch.setattr(
        "pendulum.now",
        lambda *_: pendulum.instance(dateparser.parse("January 1st 2023")),
    )
    invoke_and_assert(
        command=[
            "deployment",
            "run",
            deployment_name,
            "--start-at",
            "January 1st 2022",
        ],
        expected_output_contains="Scheduled start time: 2022-01-01 00:00:00 (1 year ago)",
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
