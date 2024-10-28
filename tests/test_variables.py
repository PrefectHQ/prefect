import pytest

from prefect import flow
from prefect.variables import Variable


@pytest.fixture
async def variable():
    var = await Variable.set(name="my_variable", value="my-value", tags=["123", "456"])
    return var


async def test_set_sync(variable):
    @flow
    def test_flow():
        # confirm variable doesn't exist
        variable_doesnt_exist = Variable.get("my_new_variable")
        assert variable_doesnt_exist is None

        # create new
        created = Variable.set(
            name="my_new_variable",
            value="my_value",
            tags=["123", "456"],
        )
        assert created.value == "my_value"
        assert created.tags == ["123", "456"]

        # try to overwrite
        with pytest.raises(
            ValueError,
            match="Variable 'my_new_variable' already exists. Use `overwrite=True` to update it.",
        ):
            Variable.set(name="my_new_variable", value="other_value")

        # actually overwrite
        updated = Variable.set(
            name="my_new_variable",
            value="other_value",
            tags=["new", "tags"],
            overwrite=True,
        )
        assert updated.value == "other_value"
        assert updated.tags == ["new", "tags"]

    test_flow()


async def test_set_async(variable):
    # confirm variable doesn't exist
    variable_doesnt_exist = await Variable.get("my_new_variable")
    assert variable_doesnt_exist is None

    # create new
    created = await Variable.set(
        name="my_new_variable", value="my_value", tags=["123", "456"]
    )
    assert created.value == "my_value"
    assert created.tags == ["123", "456"]

    # try to overwrite
    with pytest.raises(
        ValueError,
        match="Variable 'my_new_variable' already exists. Use `overwrite=True` to update it.",
    ):
        await Variable.set(name="my_new_variable", value="other_value")

    # actually overwrite
    updated = await Variable.set(
        name="my_new_variable",
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
    set_value = await Variable.set("json_variable", value=value)
    assert set_value.value == value


async def test_get(variable):
    # get value
    value = await Variable.get(variable.name)
    assert value == variable.value

    # get value of a variable that doesn't exist
    doesnt_exist = await Variable.get("doesnt_exist")
    assert doesnt_exist is None

    # default is respected if it doesn't exist
    doesnt_exist_default = await Variable.get("doesnt_exist", 42)
    assert doesnt_exist_default == 42


async def test_get_async(variable):
    # get value
    value = await Variable.get(variable.name)
    assert value == variable.value

    # get value of a variable that doesn't exist
    doesnt_exist = await Variable.get("doesnt_exist")
    assert doesnt_exist is None

    # default is respected if it doesn't exist
    doesnt_exist_default = await Variable.get("doesnt_exist", 42)
    assert doesnt_exist_default == 42


async def test_unset(variable):
    # unset a variable
    unset = await Variable.unset(variable.name)
    assert unset is True

    # confirm it's gone
    doesnt_exist = await Variable.get(variable.name)
    assert doesnt_exist is None

    # unset a variable that doesn't exist
    unset_doesnt_exist = await Variable.unset("doesnt_exist")
    assert unset_doesnt_exist is False


async def test_unset_async(variable):
    # unset a variable
    unset = await Variable.unset(variable.name)
    assert unset is True

    # confirm it's gone
    doesnt_exist = await Variable.get(variable.name)
    assert doesnt_exist is None

    # unset a variable that doesn't exist
    unset_doesnt_exist = await Variable.unset("doesnt_exist")
    assert unset_doesnt_exist is False


def test_get_in_sync_flow(variable):
    @flow
    def foo():
        var = Variable.get("my_variable")
        return var

    value = foo()
    assert value == variable.value


async def test_get_in_async_flow(variable):
    @flow
    async def foo():
        var = await Variable.get("my_variable")
        return var

    value = await foo()
    assert value == variable.value


def test_set_in_sync_flow():
    @flow
    def foo():
        return Variable.set("my_variable", value="my-value")

    res = foo()
    assert res
    assert res.value == "my-value"


async def test_set_in_async_flow():
    @flow
    async def foo():
        return await Variable.set("my_variable", value="my-value")

    res = await foo()
    assert res
    assert res.value == "my-value"


async def test_unset_in_sync_flow(variable):
    @flow
    def foo():
        Variable.unset(variable.name)

    foo()
    value = await Variable.get(variable.name)
    assert value is None


async def test_unset_in_async_flow(variable):
    @flow
    async def foo():
        await Variable.unset(variable.name)

    await foo()
    value = await Variable.get(variable.name)
    assert value is None
