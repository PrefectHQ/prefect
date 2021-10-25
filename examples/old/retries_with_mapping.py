"""
This example showcases a few basic Prefect concepts:
    - the ability to "map" tasks across the dynamic output of upstream tasks; additionally, it is not required that the
        upstream task actually passes data to the downstream task, as this example demonstrates
    - task retries: `flow.run()` will perform retries, on schedule, for all tasks that require it,
        including individual mapped tasks

This flow first generates a list of random length, and them maps over that list to spawn a dynamic number of
downstream tasks that randomly fail.  The takeaway here is that we don't have to know a-priori how many mapped tasks
will be created prior to execution!  Additionally, each failed mapped task will retry on its own.
"""
import random
from datetime import timedelta

from prefect import Flow, task


@task
def generate_random_list():
    n = random.randint(15, 25)
    return list(range(n))


@task(max_retries=3, retry_delay=timedelta(seconds=0))
def randomly_fail():
    x = random.random()
    if x > 0.7:
        raise ValueError("x is too large")


with Flow("random-mapping") as f:
    final = randomly_fail.map(upstream_tasks=[generate_random_list])

# should see logs suggesting that some tasks are failing and retrying
f.run()
