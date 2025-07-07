import signal
from typing import Any

from prefect import flow, get_client
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.schedules import Cron

"\nthis integration test should\n\n- start serve w a schedule (no slug)\n- stop the serve process\n- start serve with no schedule\n- observe that deployment has no schedules\n\n\n- start serve with schedule (slug)\n- stop the serve process\n- start serve with no schedule\n- stop the serve process\n- observe that deployment still has that named schedule\n\n"
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
        my_flow.serve(name=DEPLOYMENT_NAME, **serve_kwargs or {})
    except KeyboardInterrupt:
        print("Serve interrupted")
    finally:
        signal.alarm(0)


def check_deployment_schedules(deployment_name: str) -> list[DeploymentSchedule]:
    with get_client(sync_client=True) as client:
        deployment = client.read_deployment_by_name(deployment_name)
        return deployment.schedules


def main():
    print("\nTest case 1: Schedule without slug")
    run_serve_with_schedule(serve_kwargs={"schedules": [Cron("0 9 * * *")]})
    run_serve_with_schedule(serve_kwargs={"schedules": []})
    schedules = check_deployment_schedules(f"my-flow/{DEPLOYMENT_NAME}")
    assert not schedules, (
        f"Expected no schedules after removing unnamed schedule: {schedules}"
    )
    print("\nTest case 2: Schedule with slug")
    run_serve_with_schedule(
        serve_kwargs={"schedules": [Cron("0 9 * * *", slug="every-day-at-9am")]}
    )
    run_serve_with_schedule(serve_kwargs={"schedules": []})
    schedules = check_deployment_schedules(f"my-flow/{DEPLOYMENT_NAME}")
    assert any((s.slug == "every-day-at-9am" for s in schedules)), (
        f"Expected named schedule to persist: {schedules}"
    )
    print("All tests passed!")


def test_schedule_statefulness():
    """Test for schedule_statefulness."""
    main()
