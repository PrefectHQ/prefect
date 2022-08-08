import asyncio

from prefect import flow, get_run_logger, task
from prefect.cli._dev_utilities import assert_state_type_completed
from prefect.client import get_client
from prefect.context import get_run_context


@task
def first_task():
    return 42


@task
def second_task(msg, result):
    logger = get_run_logger()
    logger.info(
        f"Hello from second task!\nYour message is '{msg}'.\nThe first result was {result}"
    )


default_purpose = """
Placeholder
"""


@flow(name="demo")
def demo_body(msg="default message", purpose=default_purpose):
    logger = get_run_logger()  # All flows should begin by getting a run logger
    logger.info(purpose)  # and then logging the purpose of the flow.
    result_1 = first_task()
    second_task(msg, result_1)

    ctx = get_run_context()
    return ctx.flow_run.id


@flow
async def demo():
    run_id = demo_body()
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id=run_id)
    assert_state_type_completed(flow_run.state_type)


if __name__ == "__main__":
    asyncio.run(demo())
