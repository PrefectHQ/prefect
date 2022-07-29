from prefect import flow, get_run_logger, task
from prefect.deployments import Deployment
from prefect.infrastructure import Process
from prefect.orion.schemas.schedules import CronSchedule


@task
def say_hi(user_name: str):
    logger = get_run_logger()
    logger.info("Hello %s!", user_name)


@flow
def hello(user: str = "world"):
    say_hi(user)


Deployment(
    name="manual",
    flow=hello,
    parameters=dict(user="from a QA flow"),
    infrastructure=Process(),
)
Deployment(
    name="scheduled",
    flow=hello,
    parameters=dict(user="Marvin"),
    infrastructure=Process(),
    schedule=CronSchedule(cron="*/2 * * * *", timezone="US/Eastern"),
)


if __name__ == "__main__":
    hello(user="from QA flow")
