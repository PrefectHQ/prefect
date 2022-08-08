import asyncio

from prefect import flow, get_run_logger, task
from prefect.cli._dev_utilities import assert_state_type_completed
from prefect.client import get_client
from prefect.context import get_run_context

default_str = "I am the default message"


@task
def log_message(msg: str):
    logger = get_run_logger()
    logger.info(f"Your 'msg' parameter was {msg}")


@task
def log_num(num: int):
    logger = get_run_logger()
    logger.info(f"Your 'num' parameter was {num}")


default_purpose = """
The purpose of this deployment is to check that parameters are able to
be provided correctly to a deployment. 

Expected behavior: This flow should successfully complete two tasks. The first 
task should log the parameter 'msg' and the second task should log in the number 
'num'. If parameters are not provided, the default values are 'I am the default message' and '42'.
"""


@flow(name="parameters")
def parameters_body(msg: str = default_str, num: int = 42, purpose=default_purpose):
    logger = get_run_logger()
    logger.info(purpose)

    log_message(msg)
    log_num(num)

    ctx = get_run_context()
    return ctx.flow_run.id


@flow
async def parameters():
    run_id = parameters_body()
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id=run_id)

    await assert_state_type_completed(flow_run.state_type)


if __name__ == "__main__":
    asyncio.run(parameters())
