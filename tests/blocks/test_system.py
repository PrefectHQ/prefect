import pendulum
from pydantic import SecretStr

from prefect.blocks import system


async def test_string():
    await system.String(value="hello").save(name="test")
    api_block = await system.String.load("test")
    assert api_block.value == "hello"


async def test_string_cast():
    await system.String(value=123).save(name="test")
    api_block = await system.String.load("test")
    assert api_block.value == "123"


async def test_datetime():
    await system.DateTime(value=pendulum.datetime(2022, 1, 1)).save(name="test")
    api_block = await system.DateTime.load("test")
    assert api_block.value == pendulum.datetime(2022, 1, 1)


async def test_environment_variable_block(monkeypatch):
    await system.EnvironmentVariable(name="ORION_TEST_EV").save(name="test")
    api_block = await system.EnvironmentVariable.load("test")
    assert api_block.get() is None

    monkeypatch.setenv("ORION_TEST_EV", "123")
    assert api_block.get() == "123"


async def test_secret_block():
    await system.Secret(value="test").save(name="test")
    api_block = await system.Secret.load("test")
    assert isinstance(api_block.value, SecretStr)

    assert api_block.get() == "test"
