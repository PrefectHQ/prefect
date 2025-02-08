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
from typing import Any

from prefect import flow, get_client
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.schedules import Cron

DEPLOYMENT_NAME = "my-deployment"


@flow
def my_flow():
    print("Hello, world!")


def _handler(signum: int, frame: Any):
    raise KeyboardInterrupt("Simulating user interruption")


def run_serve_with_schedule(
    timeout: int = 2, serve_kwargs: dict[str, Any] | None = None
):
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout)
    try:
        my_flow.serve(name=DEPLOYMENT_NAME, **(serve_kwargs or {}))
    except KeyboardInterrupt:
        print("Serve interrupted")
    finally:
        signal.alarm(0)


def check_deployment_schedules(deployment_name: str) -> list[DeploymentSchedule]:
    with get_client(sync_client=True) as client:
        deployment = client.read_deployment_by_name(deployment_name)
        return deployment.schedules


def main():
    # case 1: Schedule without slug
    print("\nTest case 1: Schedule without slug")
    run_serve_with_schedule(serve_kwargs={"schedules": [Cron("0 9 * * *")]})
    run_serve_with_schedule(serve_kwargs={"schedules": []})
    schedules = check_deployment_schedules(f"my-flow/{DEPLOYMENT_NAME}")
    assert not schedules, (
        f"Expected no schedules after removing unnamed schedule: {schedules}"
    )

    # case 2: Schedule with slug
    print("\nTest case 2: Schedule with slug")
    run_serve_with_schedule(
        serve_kwargs={"schedules": [Cron("0 9 * * *", slug="every-day-at-9am")]}
    )
    run_serve_with_schedule(serve_kwargs={"schedules": []})
    schedules = check_deployment_schedules(f"my-flow/{DEPLOYMENT_NAME}")
    assert any(s.slug == "every-day-at-9am" for s in schedules), (
        f"Expected named schedule to persist: {schedules}"
    )
    print("All tests passed!")


if __name__ == "__main__":
    main()
