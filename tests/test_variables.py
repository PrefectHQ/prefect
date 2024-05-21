import pytest

from prefect import flow, variables


@pytest.fixture
async def variable():
    model = await variables.Variable.set(
        name="my_variable", value="my-value", tags=["123", "456"]
    )
    return model


async def test_set_variable():
    model = await variables.Variable.set(
        name="my_new_variable", value="my_value", tags=["123", "456"]
    )
    assert model.name == "my_new_variable"
    assert model.value == "my_value"
    assert model.tags == ["123", "456"]


def test_variable_with_same_name_and_not_overwrite_errors(variable):
    with pytest.raises(
        ValueError,
        match="You are attempting to save a variable with a name that is already in use. If you would like to overwrite the values that are saved, then call .set with `overwrite=True`.",
    ):
        variables.Variable.set(name=variable.name, value="new_value", overwrite=False)


async def test_variable_with_same_name_and_overwrite(variable):
    new_value = "new_value"
    new_tags = ["my", "new", "tags"]
    overwritten_variable = await variables.Variable.set(
        name=variable.name, value=new_value, tags=new_tags, overwrite=True
    )
    assert overwritten_variable.value == new_value
    assert overwritten_variable.tags == new_tags


def test_get(variable):
    res = variables.Variable.get(variable.name)
    assert res
    assert res.id == variable.id
    assert res.name == variable.name
    assert res.value == variable.value

    res = variables.Variable.get("doesnt_exist")
    assert res is None


async def test_get_async(variable):
    res = await variables.Variable.get(variable.name)
    assert res
    assert res.id == variable.id
    assert res.name == variable.name
    assert res.value == variable.value

    value = await variables.Variable.get("doesnt_exist")
    assert value is None


def test_get_in_sync_flow(variable):
    @flow
    def foo():
        var = variables.Variable.get("my_variable")
        return var

    res = foo()
    assert res
    assert res.id == variable.id
    assert res.name == variable.name
    assert res.value == variable.value


async def test_get_in_async_flow(variable):
    @flow
    async def foo():
        var = await variables.Variable.get("my_variable")
        return var

    res = await foo()
    assert res
    assert res.id == variable.id
    assert res.name == variable.name
    assert res.value == variable.value
