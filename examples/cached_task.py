import datetime
import random

from prefect import task, Flow
from prefect.schedules import IntervalSchedule


@task(cache_for=datetime.timedelta(minutes=1, seconds=30))
def return_random_number():
    return random.random()


@task
def print_number(num):
    print("=" * 50)
    print("Value: {}".format(num))
    print("=" * 50)


schedule = IntervalSchedule(
    start_date=datetime.datetime.utcnow(), interval=datetime.timedelta(minutes=1)
)


with Flow("cached-task", schedule=schedule) as flow:
    result = print_number(return_random_number)


flow.run()
# ==================================================
# Value: 0.8246312081499598
# ==================================================
# ==================================================
# Value: 0.8246312081499598
# ==================================================
# ==================================================
# Value: 0.36999574748592756
# ==================================================
