import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect import flow, variables
from prefect.server.models.variables import create_variable
from prefect.server.schemas.actions import VariableCreate


@pytest.fixture
async def variable(
    session: AsyncSession,
):
    model = await create_variable(
        session,
        VariableCreate(name="my_variable", value="my-value", tags=["123", "456"]),
    )
    await session.commit()

    return model


def test_get(variable):
    value = variables.get(variable.name)
    assert value == variable.value

    value = variables.get("doesnt_exist")
    assert value is None


def test_get_item(variable):
    value = variables[variable.name]
    assert value == variable.value

    value = variables["doesnt_exist"]
    assert value is None


async def test_aget(variable):
    value = await variables.aget(variable.name)
    assert value == variable.value

    value = await variables.aget("doesnt_exist")
    assert value is None


def test_variables_work_in_sync_flows(variable):
    @flow
    def foo():
        res1 = variables.get("my_variable")
        res2 = variables["my_variable"]
        return res1, res2

    res = foo()
    assert res == (variable.value, variable.value)


async def test_variables_work_in_async_flows(variable):
    @flow
    async def foo():
        res1 = variables.get("my_variable")
        res2 = variables["my_variable"]
        res3 = await variables.aget("my_variable")
        return res1, res2, res3

    res = await foo()
    assert res == (variable.value, variable.value, variable.value)
