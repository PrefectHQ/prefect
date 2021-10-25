"""
An example Flow that stores the current flow visualization to a file
each time the flow changes state, using a Flow-level state handler.

Uses the same flow from "Retries w/ Mapping" on a minute schedule.
"""
import random
from datetime import datetime, timedelta

from prefect import Flow, task
from prefect.schedules import IntervalSchedule


def visualize(flow, old_state, new_state):
    """
    Flow state handler that stores the current flow
    visualization to a known file location, for live viewing.
    """
    if isinstance(new_state.result, dict):
        ## note that the relevant file will actually be called "known_location.pdf"
        flow.visualize(flow_state=new_state, filename="known_location")
    return new_state


@task
def generate_random_list():
    n = random.randint(15, 25)
    return list(range(n))


@task(max_retries=3, retry_delay=timedelta(seconds=0))
def randomly_fail():
    x = random.random()
    if x > 0.7:
        raise ValueError("x is too large")


schedule = IntervalSchedule(
    start_date=datetime.utcnow(),
    interval=timedelta(minutes=1),
    end_date=datetime.utcnow() + timedelta(minutes=10),
)

with Flow(
    "random-mapping-with-viz", schedule=schedule, state_handlers=[visualize]
) as f:
    randomly_fail.map(upstream_tasks=[generate_random_list])


f.run()
