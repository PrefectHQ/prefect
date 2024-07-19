import uuid

from prefect import flow
from prefect.blocks.system import Secret

block_name = f"foo-{uuid.uuid4()}"
Secret(value="bar").save("foo")

my_secret = Secret.load("foo")


@flow
async def uses_block():
    return my_secret.get()
