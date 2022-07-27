import pendulum
from pydantic import SecretStr

from prefect.blocks import system


async def test_datetime():
    await system.DateTime(value=pendulum.datetime(2022, 1, 1)).save(name="test")
    api_block = await system.DateTime.load("test")
    assert api_block.value == pendulum.datetime(2022, 1, 1)


async def test_secret_block():
    await system.Secret(value="test").save(name="test")
    api_block = await system.Secret.load("test")
    assert isinstance(api_block.value, SecretStr)

    assert api_block.get() == "test"
