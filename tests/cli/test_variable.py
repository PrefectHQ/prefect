import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.models.variables import create_variable
from prefect.server.schemas.actions import VariableCreate
from prefect.testing.cli import invoke_and_assert


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


@pytest.fixture
async def variables(
    session: AsyncSession,
):
    variables = [
        VariableCreate(name="variable1", value="value1", tags=["tag1"]),
        VariableCreate(name="variable12", value="value12", tags=["tag2"]),
        VariableCreate(name="variable2", value="value2", tags=["tag1"]),
        VariableCreate(name="variable21", value="value21", tags=["tag2"]),
    ]
    models = []
    for variable in variables:
        model = await create_variable(session, variable)
        models.append(model)
    await session.commit()

    return models


def test_list_variables_none_exist():
    invoke_and_assert(
        ["variable", "ls"],
        expected_output_contains="""
            ┏━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
            ┃ Name ┃ Value ┃ Created ┃ Updated ┃
            ┡━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
            └──────┴───────┴─────────┴─────────┘
        """,
        expected_code=0,
    )


def test_list_variables_with_limit(variables):
    # variables are alphabetical by name
    name = sorted([variable.name for variable in variables])[0]
    invoke_and_assert(
        ["variable", "ls", "--limit", "1"],
        expected_output_contains=name,
        expected_code=0,
    )


def test_list_variables(variables):
    names = (variable.name for variable in variables)
    invoke_and_assert(
        ["variable", "ls"],
        expected_output_contains=(names),
        expected_code=0,
    )


def test_inspect_variable_doesnt_exist():
    invoke_and_assert(
        ["variable", "inspect", "doesnt_exist"],
        expected_output_contains="Variable 'doesnt_exist' not found",
        expected_code=1,
    )


def test_inspect_variable(variable):
    invoke_and_assert(
        ["variable", "inspect", variable.name],
        expected_output_contains=(variable.name, variable.value, str(variable.id)),
        expected_code=0,
    )


def test_delete_variable_doesnt_exist():
    invoke_and_assert(
        ["variable", "delete", "doesnt_exist"],
        expected_output_contains="Variable 'doesnt_exist' not found",
        expected_code=1,
    )


def test_delete_variable(variable):
    invoke_and_assert(
        ["variable", "delete", variable.name],
        expected_output_contains=f"Deleted variable {variable.name!r}.",
        expected_code=0,
    )
