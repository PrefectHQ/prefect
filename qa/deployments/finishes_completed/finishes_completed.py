from prefect import flow, get_run_logger, task
from prefect.cli._dev_utilities import assert_state_type_completed
from prefect.client import get_client
from prefect.context import get_run_context

purpose = """
The purpose of this flow is to finish in a completed state.

Expected behavior: `parent_task` will pass results to `first_child`
and `second_child`. `first_child` will pass results to `grand_child`. 
The flow should finish in a completed state.
"""


@task
def parent_task():
    return 256


@task
def first_child(from_parent):
    return 512


@task
def second_child(from_parent):
    return 42


@task
def grand_child(from_child):
    return 1024


@flow
def finishes_completed_body():
    logger = get_run_logger()
    logger.info(purpose)

    parent_res = parent_task()
    c1_res = first_child(parent_res)
    c2_res = second_child(parent_res)
    grand_child(c1_res)

    ctx = get_run_context()
    return ctx.flow_run.id


@flow
async def finishes_completed():
    run_id = finishes_completed_body()
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id=run_id)

    await assert_state_type_completed(flow_run.state_type)


if __name__ == "__main__":
    finishes_completed()
