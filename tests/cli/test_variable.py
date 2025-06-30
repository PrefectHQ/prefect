import sys

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from typer import Exit

from prefect.server.models.variables import create_variable
from prefect.server.schemas.actions import VariableCreate
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.variable.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


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


def test_inspect_variable_with_json_output(variable):
    """Test variable inspect command with JSON output flag."""
    import json

    result = invoke_and_assert(
        ["variable", "inspect", variable.name, "--output", "json"],
        expected_code=0,
    )

    # Parse JSON output and verify it's valid JSON
    output_data = json.loads(result.stdout.strip())

    # Verify key fields are present
    assert "id" in output_data
    assert "name" in output_data
    assert "value" in output_data
    assert output_data["id"] == str(variable.id)
    assert output_data["name"] == variable.name
    assert output_data["value"] == variable.value


def test_delete_variable_doesnt_exist():
    invoke_and_assert(
        ["variable", "delete", "doesnt_exist"],
        user_input="y",
        expected_output_contains="Variable 'doesnt_exist' not found",
        expected_code=1,
    )


def test_get_variable(variable):
    invoke_and_assert(
        ["variable", "get", variable.name],
        expected_output_contains=variable.value,
        expected_code=0,
    )


def test_get_variable_doesnt_exist(variable):
    invoke_and_assert(
        ["variable", "get", "doesnt_exist"],
        expected_output_contains="Variable 'doesnt_exist' not found",
        expected_code=1,
    )


def test_set_variable():
    invoke_and_assert(
        [
            "variable",
            "set",
            "my_variable",
            "my-value",
            "--tag",
            "tag1",
            "--tag",
            "tag2",
        ],
        expected_output_contains="Set variable 'my_variable'.",
        expected_code=0,
    )
    invoke_and_assert(
        ["variable", "inspect", "my_variable"],
        expected_output_contains=[
            "name='my_variable'",
            "value='my-value'",
            "tags=['tag1', 'tag2']",
        ],
        expected_code=0,
    )


def test_set_existing_variable_without_overwrite(variable):
    invoke_and_assert(
        ["variable", "set", variable.name, "new-value"],
        expected_output_contains="already exists. Use `--overwrite` to update it.",
        expected_code=1,
    )


def test_set_overwrite_variable(variable):
    invoke_and_assert(
        ["variable", "set", variable.name, "new-value", "--overwrite"],
        expected_output_contains=f"Set variable {variable.name!r}",
        expected_code=0,
    )
    invoke_and_assert(
        ["variable", "get", variable.name],
        expected_output_contains="new-value",
        expected_code=0,
    )


def test_unset_variable_doesnt_exist():
    invoke_and_assert(
        ["variable", "unset", "doesnt_exist"],
        user_input="y",
        expected_output_contains="Variable 'doesnt_exist' not found",
        expected_code=1,
    )


def test_unset_variable(variable):
    invoke_and_assert(
        ["variable", "unset", variable.name],
        user_input="y",
        expected_output_contains=f"Unset variable {variable.name!r}.",
        expected_code=0,
    )


def test_unset_variable_without_confirmation_aborts(variable):
    invoke_and_assert(
        ["variable", "unset", variable.name],
        user_input="n",
        expected_output_contains="Unset aborted.",
        expected_code=1,
    )


def test_delete_variable(variable):
    invoke_and_assert(
        ["variable", "delete", variable.name],
        user_input="y",
        expected_output_contains=f"Unset variable {variable.name!r}.",
        expected_code=0,
    )
