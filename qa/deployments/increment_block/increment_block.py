import asyncio

from prefect import blocks, flow, get_run_logger
from prefect.cli._dev_utilities import assert_state_type_completed
from prefect.client import get_client
from prefect.context import get_run_context

purpose = """
The purpose of this flow is make sure that the JSON block can be 
loaded and updated as expected.

Expected behavior: this flow should load a value from an existing
'dev-qa-block' JSON block, or create one if it doesn't exist. It 
should then log a value n on load, then log a value n+1 after a 
save and re-load.
"""


@flow
def increment_block_body():
    logger = get_run_logger()
    logger.info(purpose)

    try:
        json_block = blocks.system.JSON.load("dev-qa-block")
    except Exception as exc:
        logger.info(exc)
        logger.info("No JSON block 'dev-qa-block' found. Creating new block now")
        json_block = blocks.system.JSON(value={"num": 0})
        json_block.save("dev-qa-block")

    val = json_block.value["num"]
    logger.info(f"Value of 'dev-qa-block' on load: {val}")
    json_block.value["num"] = int(val) + 1
    json_block.save("dev-qa-block", overwrite=True)
    json_block_reloaded = blocks.system.JSON.load("dev-qa-block")
    logger.info(
        f"Value of 'dev-qa-block' after save and re-load: {json_block_reloaded.value['num']}"
    )

    ctx = get_run_context()
    return ctx.flow_run.id


@flow
async def increment_block():
    run_id = increment_block_body()
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id=run_id)

    await assert_state_type_completed(flow_run.state_type)


if __name__ == "__main__":
    asyncio.run(increment_block())
