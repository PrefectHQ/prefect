"""
this integration test should

- start serve w a schedule (no slug)
- stop the serve process
- start serve with no schedule
- observe that deployment has no schedules


- start serve with schedule (slug)
- stop the serve process
- start serve with no schedule
- stop the serve process
- observe that deployment still has that named schedule

"""

import signal
from typing import Any, Callable
from uuid import uuid4

import pytest

from prefect import flow, get_client
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.client.schemas.schedules import CronSchedule
from prefect.schedules import Cron, Schedule
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    temporary_settings,
)


@pytest.fixture()
def deployment_name():
    return f"my-deployment-{uuid4()}"


@flow
def my_flow():
    print("Hello, world!")


def create_check_handler(
    deployment_name: str,
    check_function: Callable[[list[DeploymentSchedule]], bool] = lambda schedules: True,
    num_checks: int = 5,
    timeout: int = 5,
):
    def handler(signum: int, frame: Any):
        try:
            schedules = check_deployment_schedules(f"my-flow/{deployment_name}")
        except Exception as e:
            print(f"Error checking schedules: {e}")
            schedules = []

        if check_function(schedules) or num_checks <= 0:
            raise KeyboardInterrupt("Simulating user interruption")
        else:
            print(f"Checking {num_checks} more times")
            signal.signal(
                signal.SIGALRM,
                create_check_handler(
                    deployment_name, check_function, num_checks - 1, timeout
                ),
            )
            signal.alarm(timeout)

    return handler


def run_serve_with_schedule(
    deployment_name: str,
    check_function: Callable[[list[DeploymentSchedule]], bool] = lambda schedules: True,
    schedules: list[Schedule] | None = None,
    timeout: int = 5,
    num_checks: int = 5,
):
    signal.signal(
        signal.SIGALRM,
        create_check_handler(deployment_name, check_function, num_checks, timeout),
    )
    signal.alarm(timeout)
    try:
        my_flow.serve(name=deployment_name, schedules=schedules)
    except KeyboardInterrupt:
        print("Serve interrupted")
    finally:
        signal.alarm(0)


def check_deployment_schedules(deployment_name: str) -> list[DeploymentSchedule]:
    with get_client(sync_client=True) as client:
        deployment = client.read_deployment_by_name(deployment_name)
        return deployment.schedules


def test_schedule_statefulness(deployment_name: str):
    # case 1: Schedule without slug
    print("\nTest case 1: Schedule without slug")
    run_serve_with_schedule(
        deployment_name,
        schedules=[Cron("0 9 * * *")],
        check_function=lambda schedules: any(
            s.schedule == CronSchedule(cron="0 9 * * *") for s in schedules
        ),
    )
    schedules = check_deployment_schedules(f"my-flow/{deployment_name}")
    assert any(s.schedule == CronSchedule(cron="0 9 * * *") for s in schedules), (
        f"Expected schedule to persist: {schedules}"
    )
    run_serve_with_schedule(
        deployment_name, schedules=[], check_function=lambda schedules: not schedules
    )
    schedules = check_deployment_schedules(f"my-flow/{deployment_name}")
    assert not schedules, (
        f"Expected no schedules after removing unnamed schedule: {schedules}"
    )

    # case 2: Schedule with slug
    print("\nTest case 2: Schedule with slug")
    run_serve_with_schedule(
        deployment_name,
        schedules=[Cron("0 9 * * *", slug="every-day-at-9am")],
        check_function=lambda schedules: any(
            s.slug == "every-day-at-9am" for s in schedules
        ),
    )
    run_serve_with_schedule(deployment_name, schedules=[])
    schedules = check_deployment_schedules(f"my-flow/{deployment_name}")
    assert any(s.slug == "every-day-at-9am" for s in schedules), (
        f"Expected named schedule to persist: {schedules}"
    )
    print("All tests passed!")


def test_schedule_id_stability_for_no_slug_redeploy(deployment_name: str):
    # Use an ephemeral local API to ensure this integration test exercises
    # branch code and does not depend on external profile configuration.
    with temporary_settings(
        {
            PREFECT_API_URL: "",
            PREFECT_API_KEY: "",
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        initial_deployment = my_flow.to_deployment(
            name=deployment_name,
            schedules=[Cron("0 9 * * *")],
        )
        initial_deployment.apply()

        initial_schedules = check_deployment_schedules(f"my-flow/{deployment_name}")
        assert len(initial_schedules) == 1
        initial_schedule = initial_schedules[0]
        assert initial_schedule.schedule == CronSchedule(cron="0 9 * * *")

        updated_deployment = my_flow.to_deployment(
            name=deployment_name,
            schedules=[Cron("0 10 * * *")],
        )
        updated_deployment.apply()

        updated_schedules = check_deployment_schedules(f"my-flow/{deployment_name}")
        assert len(updated_schedules) == 1
        updated_schedule = updated_schedules[0]
        assert updated_schedule.schedule == CronSchedule(cron="0 10 * * *")
        assert updated_schedule.id == initial_schedule.id
