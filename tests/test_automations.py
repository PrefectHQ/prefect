import pytest

from prefect.automations import Automation, EventTrigger, Posture
from prefect.server.events import actions


@pytest.fixture
async def automation():
    automation_to_create = Automation(
        name="hello",
        description="world",
        enabled=True,
        trigger=EventTrigger(
            match={"prefect.resource.name": "howdy!"},
            match_related={"prefect.resource.role": "something-cool"},
            after={"this.one", "or.that.one"},
            expect={"surely.this", "but.also.this"},
            for_each=["prefect.resource.name", "prefect.handle"],
            posture=Posture.Reactive,
            threshold=42,
        ),
        actions=[actions.DoNothing()],
    )

    model = await Automation.create(automation=automation_to_create)
    return model


async def test_read_automation_by_id(automation):
    model = await Automation.read(automation.id)
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == {"prefect.resource.name": "howdy!"}
    assert model.trigger.match_related == {"prefect.resource.role": "something-cool"}
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == ["prefect.resource.name", "prefect.handle"]
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0].name == "DoNothing"


async def test_read_automation_by_name(automation):
    model = await Automation.read(automation.name)
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == {"prefect.resource.name": "howdy!"}
    assert model.trigger.match_related == {"prefect.resource.role": "something-cool"}
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == ["prefect.resource.name", "prefect.handle"]
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0].name == "DoNothing"


async def test_update_automation(automation):
    automation.name = "goodbye"
    model = await Automation.update(automation)
    assert model.name == "goodbye"


async def test_disable_automation(automation):
    model = await Automation.disable(automation.id)
    assert model.enabled is False


async def test_enable_automation(automation):
    model = await Automation.enable(automation.id)
    assert model.enabled is True


async def test_delete_automation(automation):
    model = await Automation.delete(automation.id)
    assert model is None


# async def test_set_variable():
#     model = await variables.Variable.set(
#         name="my_new_variable", value="my_value", tags=["123", "456"]
#     )
#     assert model.name == "my_new_variable"
#     assert model.value == "my_value"
#     assert model.tags == ["123", "456"]


# def test_variable_with_same_name_and_not_overwrite_errors(variable):
#     with pytest.raises(
#         ValueError,
#         match="You are attempting to save a variable with a name that is already in use. If you would like to overwrite the values that are saved, then call .set with `overwrite=True`.",
#     ):
#         variables.Variable.set(name=variable.name, value="new_value", overwrite=False)


# async def test_variable_with_same_name_and_overwrite(variable):
#     new_value = "new_value"
#     new_tags = ["my", "new", "tags"]
#     overwritten_variable = await variables.Variable.set(
#         name=variable.name, value=new_value, tags=new_tags, overwrite=True
#     )
#     assert overwritten_variable.value == new_value
#     assert overwritten_variable.tags == new_tags


# def test_get(variable):
#     value = variables.get(variable.name)
#     assert value == variable.value

#     value = variables.get("doesnt_exist")
#     assert value is None


# async def test_get_async(variable):
#     value = await variables.get(variable.name)
#     assert value == variable.value

#     value = await variables.get("doesnt_exist")
#     assert value is None


# def test_variables_work_in_sync_flows(variable):
#     @flow
#     def foo():
#         var = variables.get("my_variable")
#         return var

#     res = foo()
#     assert res == variable.value


# async def test_variables_work_in_async_flows(variable):
#     @flow
#     async def foo():
#         var = await variables.get("my_variable")
#         return var

#     res = await foo()
#     assert res == variable.value


# def test_variable_class_work_in_sync_flows(variable):
#     @flow
#     def foo():
#         var = variables.Variable.get("my_variable")
#         return var

#     res = foo()
#     assert res.value == variable.value


# async def test_variable_class_work_in_async_flows(variable):
#     @flow
#     async def foo():
#         var = await variables.Variable.get("my_variable")
#         return var

#     res = await foo()
#     assert res.value == variable.value
