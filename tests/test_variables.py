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


async def test_get_async(variable):
    value = await variables.get(variable.name)
    assert value == variable.value

    value = await variables.get("doesnt_exist")
    assert value is None


def test_variables_work_in_sync_flows(variable):
    @flow
    def foo():
        var = variables.get("my_variable")
        return var

    res = foo()
    assert res == variable.value


async def test_variables_work_in_async_flows(variable):
    @flow
    async def foo():
        var = await variables.get("my_variable")
        return var

    res = await foo()
    assert res == variable.value
