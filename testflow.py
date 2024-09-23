from prefect import flow, task
from prefect.deployments.runner import ConcurrencyLimitConfig


@task
def slow_task(time_to_wait: int):
    import time

    time.sleep(time_to_wait)


@flow
def slow_flow():
    # tasks = slow_task.map([300, 360, 180])
    # tasks.wait()
    slow_task(300)


if __name__ == "__main__":
    limit = ConcurrencyLimitConfig(limit=2, collision_strategy="CANCEL_NEW")
    slow_flow.serve(name="slow-flow", global_limit=limit)
