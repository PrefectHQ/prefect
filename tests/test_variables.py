import uuid

import pytest

from prefect import flow
from prefect.variables import Variable


@pytest.fixture
async def variable() -> Variable:
    var = await Variable.aset(
        name=f"my_variable_{uuid.uuid4()}", value="my-value", tags=["123", "456"]
    )
    return var


async def test_set_sync(variable: Variable):
    var_name = f"my_new_variable_{uuid.uuid4()}"

    @flow
    def test_flow():
        # confirm variable doesn't exist
        variable_doesnt_exist = Variable.get(var_name)
        assert variable_doesnt_exist is None

        # create new
        created = Variable.set(
            name=var_name,
            value="my_value",
            tags=["123", "456"],
        )
        assert created.value == "my_value"
        assert created.tags == ["123", "456"]

        # try to overwrite
        with pytest.raises(
            ValueError,
            match=f"Variable '{var_name}' already exists. Use `overwrite=True` to update it.",
        ):
            Variable.set(name=var_name, value="other_value")

        # actually overwrite
        updated = Variable.set(
            name=var_name,
            value="other_value",
            tags=["new", "tags"],
            overwrite=True,
        )
        assert updated.value == "other_value"
        assert updated.tags == ["new", "tags"]

    test_flow()


async def test_set_async(variable: Variable):
    var_name = f"my_new_variable_{uuid.uuid4()}"

    # confirm variable doesn't exist
    variable_doesnt_exist = await Variable.get(var_name)
    assert variable_doesnt_exist is None

    # create new
    created = await Variable.set(name=var_name, value="my_value", tags=["123", "456"])
    assert created.value == "my_value"
    assert created.tags == ["123", "456"]

    # try to overwrite
    with pytest.raises(
        ValueError,
        match=f"Variable '{var_name}' already exists. Use `overwrite=True` to update it.",
    ):
        await Variable.set(name=var_name, value="other_value")

    # actually overwrite
    updated = await Variable.set(
        name=var_name,
        value="other_value",
        tags=["new", "tags"],
        overwrite=True,
    )
    assert updated.value == "other_value"
    assert updated.tags == ["new", "tags"]


@pytest.mark.parametrize(
    "value",
    [
        "string-value",
        '"string-value"',
        123,
        12.3,
        True,
        False,
        None,
        {"key": "value"},
        ["value1", "value2"],
        {"key": ["value1", "value2"]},
    ],
)
async def test_json_types(value):
    var_name = f"json_variable_{uuid.uuid4()}"
    set_value = await Variable.set(var_name, value=value)
    assert set_value.value == value


async def test_get(variable: Variable):
    # get value
    value = await Variable.get(variable.name)
    assert value == variable.value

    # get value of a variable that doesn't exist
    doesnt_exist = await Variable.get("doesnt_exist")
    assert doesnt_exist is None

    # default is respected if it doesn't exist
    doesnt_exist_default = await Variable.get("doesnt_exist", 42)
    assert doesnt_exist_default == 42


async def test_get_async(variable: Variable):
    # get value
    value = await Variable.get(variable.name)
    assert value == variable.value

    # get value of a variable that doesn't exist
    doesnt_exist = await Variable.get("doesnt_exist")
    assert doesnt_exist is None

    # default is respected if it doesn't exist
    doesnt_exist_default = await Variable.get("doesnt_exist", 42)
    assert doesnt_exist_default == 42


async def test_unset(variable: Variable):
    # unset a variable
    unset = await Variable.unset(variable.name)
    assert unset is True

    # confirm it's gone
    doesnt_exist = await Variable.get(variable.name)
    assert doesnt_exist is None

    # unset a variable that doesn't exist
    unset_doesnt_exist = await Variable.unset("doesnt_exist")
    assert unset_doesnt_exist is False


async def test_unset_async(variable: Variable):
    # unset a variable
    unset = await Variable.unset(variable.name)
    assert unset is True

    # confirm it's gone
    doesnt_exist = await Variable.get(variable.name)
    assert doesnt_exist is None

    # unset a variable that doesn't exist
    unset_doesnt_exist = await Variable.unset("doesnt_exist")
    assert unset_doesnt_exist is False


def test_get_in_sync_flow(variable: Variable):
    @flow
    def foo():
        var = Variable.get(variable.name)
        return var

    value = foo()
    assert value == variable.value


async def test_get_in_async_flow(variable: Variable):
    @flow
    async def foo():
        var = await Variable.get(variable.name)
        return var

    value = await foo()
    assert value == variable.value


def test_set_in_sync_flow():
    var_name = f"my_variable_{uuid.uuid4()}"

    @flow
    def foo():
        return Variable.set(var_name, value="my-value")

    res = foo()
    assert res
    assert res.value == "my-value"


async def test_set_in_async_flow():
    var_name = f"my_variable_{uuid.uuid4()}"

    @flow
    async def foo():
        return await Variable.set(var_name, value="my-value")

    res = await foo()
    assert res
    assert res.value == "my-value"


async def test_unset_in_sync_flow(variable: Variable):
    @flow
    def foo():
        Variable.unset(variable.name)

    foo()
    value = await Variable.get(variable.name)
    assert value is None


async def test_unset_in_async_flow(variable: Variable):
    @flow
    async def foo():
        await Variable.unset(variable.name)

    await foo()
    value = await Variable.get(variable.name)
    assert value is None


async def test_explicit_async_methods_from_async_context(variable: Variable):
    var_name = f"some_variable_{uuid.uuid4()}"
    var = await Variable.aset(var_name, value="my value", tags=["marvin"])
    assert var.value == "my value"
    assert var.tags == ["marvin"]
    assert var.name == var_name

    updated = await Variable.aset(var_name, value="my updated value", overwrite=True)
    assert updated.value == "my updated value"
    assert updated.tags == []

    await Variable.aunset(var_name)
    assert await Variable.aget(var_name) is None


async def test_generic_typing_syntax():
    """Test that the generic typing syntax works at runtime.

    This test verifies that Variable[T].get() and Variable[T].aget() work correctly
    at runtime. The type narrowing is primarily a static type checking feature,
    but we verify the runtime behavior is unchanged.
    """
    # Set up a test variable
    var_name = f"typed_variable_{uuid.uuid4()}"
    await Variable.aset(var_name, value="test_value", overwrite=True)

    # Test sync get with generic syntax
    @flow
    def sync_flow():
        # Variable[str].get() should work the same as Variable.get()
        value = Variable[str].get(var_name)
        return value

    result = sync_flow()
    assert result == "test_value"

    # Test async get with generic syntax
    value = await Variable[str].aget(var_name)
    assert value == "test_value"

    # Test with default value
    nonexistent_var = f"nonexistent_variable_{uuid.uuid4()}"
    default_value = await Variable[str].aget(nonexistent_var, "default")
    assert default_value == "default"

    # Test without default (should return None)
    none_value = await Variable[str].aget(nonexistent_var)
    assert none_value is None

    # Clean up
    await Variable.aunset(var_name)
