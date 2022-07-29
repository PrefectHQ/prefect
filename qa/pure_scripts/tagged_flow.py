from prefect import flow, get_run_logger, task
from prefect.deployments import Deployment
from prefect.infrastructure import Process


@task
def say_hi(user_name: str):
    logger = get_run_logger()
    logger.info("Hello %s!", user_name)


@flow
def hello(user: str = "world"):
    say_hi(user)


Deployment(
    name="tagged",
    flow=hello,
    tags=["qa"],
    parameters=dict(user="Work Queue"),
    infrastructure=Process(),
)
