from uuid import UUID

import pytest

from prefect import flow
from prefect.automations import Automation, DoNothing
from prefect.events import ResourceSpecification
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED, temporary_settings


@pytest.fixture(autouse=True)
def enable_triggers():
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        yield


@pytest.fixture
async def automation_spec():
    automation_to_create = Automation(
        name="hello",
        description="world",
        enabled=True,
        trigger=EventTrigger(
            match={"prefect.resource.name": "howdy!"},
            match_related={"prefect.resource.role": "something-cool"},
            after={"this.one", "or.that.one"},
            expect={"surely.this", "but.also.this"},
            for_each=["prefect.resource.name"],
            posture=Posture.Reactive,
            threshold=42,
        ),
        actions=[DoNothing()],
    )
    return automation_to_create


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
            for_each=["prefect.resource.name"],
            posture=Posture.Reactive,
            threshold=42,
        ),
        actions=[DoNothing()],
    )

    model = await automation_to_create.create()
    return model


async def test_read_automation_by_uuid(automation):
    model = await Automation.read(id=automation.id)
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == ResourceSpecification(
        {"prefect.resource.name": "howdy!"}
    )
    assert model.trigger.match_related == ResourceSpecification(
        {"prefect.resource.role": "something-cool"}
    )
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == {"prefect.resource.name"}
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0] == DoNothing(type="do-nothing")


async def test_read_automation_by_uuid_string(automation):
    model = await Automation.read(str(automation.id))
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == ResourceSpecification(
        {"prefect.resource.name": "howdy!"}
    )
    assert model.trigger.match_related == ResourceSpecification(
        {"prefect.resource.role": "something-cool"}
    )
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == {"prefect.resource.name"}
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0] == DoNothing(type="do-nothing")


async def test_read_automation_by_name(automation):
    model = await Automation.read(name=automation.name)
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == ResourceSpecification(
        {"prefect.resource.name": "howdy!"}
    )
    assert model.trigger.match_related == ResourceSpecification(
        {"prefect.resource.role": "something-cool"}
    )
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == {"prefect.resource.name"}
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0] == DoNothing(type="do-nothing")


async def test_update_automation(automation_spec):
    auto_to_create = await automation_spec.create()
    created_auto = await Automation.read(id=auto_to_create.id)

    created_auto.name = "goodbye"
    await created_auto.update()

    updated_auto = await Automation.read(id=created_auto.id)
    assert updated_auto.name == "goodbye"


async def test_disable_automation(automation):
    model = await automation.disable()
    model = await Automation.read(id=automation.id)
    assert model.enabled is False


async def test_enable_automation(automation):
    model = await automation.enable()
    model = await Automation.read(id=automation.id)
    assert model.enabled is True


async def test_automations_work_in_sync_flows(automation_spec):
    @flow
    def create_automation():
        created_automation = automation_spec.create()
        return created_automation

    auto = create_automation()
    assert isinstance(auto, Automation)
    assert auto.id is not None


async def test_automations_work_in_async_flows(automation_spec):
    @flow
    async def create_automation():
        created_automation = await automation_spec.create()
        return created_automation

    auto = await create_automation()
    assert isinstance(auto, Automation)
    assert auto.id is not None


async def test_delete_automation(automation):
    await Automation.delete(automation)
    with pytest.raises(ValueError):
        await Automation.read(id=automation.id)


async def test_read_automation_by_name_no_name():
    with pytest.raises(ValueError, match="One of id or name must be provided"):
        await Automation.read()


async def test_read_auto_by_id_and_name(automation):
    with pytest.raises(ValueError, match="Only one of id or name can be provided"):
        await Automation.read(id=automation.id, name=automation.name)


async def test_nonexistent_id_raises_value_error():
    with pytest.raises(ValueError):
        await Automation.read(id=UUID("6d222a09-3c68-42d4-b019-bd331a3abb88"))


async def test_nonexistent_name_raises_value_error():
    with pytest.raises(ValueError):
        await Automation.read(name="nonexistent_name")
