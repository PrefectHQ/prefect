from uuid import UUID

import pytest

from prefect import flow
from prefect.automations import Automation, DoNothing
from prefect.events import ResourceSpecification
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.exceptions import ObjectNotFound
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED, temporary_settings


@pytest.fixture(autouse=True)
def enable_triggers():
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        yield


@pytest.fixture
async def automation_spec() -> Automation:
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
async def automation() -> Automation:
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


async def test_read_automation_by_uuid(automation: Automation):
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


async def test_read_automation_by_uuid_string(automation: Automation):
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


async def test_read_automation_by_name(automation: Automation):
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


async def test_aenable_automation(automation: Automation):
    model = await automation.aenable()
    model = await Automation.aread(id=automation.id)
    assert model.enabled is True


def test_enable_automation(automation: Automation):
    automation.enable()
    model = Automation.read(id=automation.id)
    assert model.enabled is True


async def test_automations_work_in_sync_flows(automation_spec: Automation):
    @flow
    def create_automation() -> Automation:
        automation = automation_spec.create(_sync=True)
        return automation

    auto = create_automation()
    assert isinstance(auto, Automation)
    assert auto.id is not None


async def test_automations_work_in_async_flows(automation_spec: Automation):
    @flow
    async def create_automation():
        created_automation = await automation_spec.acreate()
        return created_automation

    auto = await create_automation()
    assert isinstance(auto, Automation)
    assert auto.id is not None


async def test_adelete_automation(automation: Automation):
    await Automation.adelete(automation)
    with pytest.raises(ValueError):
        await Automation.read(id=automation.id)


def test_delete_automation(automation: Automation):
    automation.delete()
    with pytest.raises(ValueError):
        Automation.read(id=automation.id)


async def test_read_auto_by_id_and_name(automation: Automation):
    with pytest.raises(ValueError, match="Only one of id or name can be provided"):
        await Automation.read(id=automation.id, name=automation.name)


async def test_nonexistent_id_raises_value_error():
    with pytest.raises(ValueError):
        await Automation.read(id=UUID("6d222a09-3c68-42d4-b019-bd331a3abb88"))


async def test_nonexistent_name_raises_value_error():
    with pytest.raises(ValueError):
        await Automation.read(name="nonexistent_name")


async def test_disabled_automation_can_be_enabled(automation: Automation):
    await automation.adisable()
    await automation.aenable()

    updated_automation = await Automation.aread(id=automation.id)
    assert updated_automation.enabled is True


def test_disabled_automation_can_be_enabled_sync(automation: Automation):
    automation.disable()
    automation.enable()

    updated_automation = Automation.read(id=automation.id)
    assert updated_automation.enabled is True


async def test_find_automation(automation: Automation):
    from prefect.client.orchestration import get_client

    client = get_client()

    # Test finding by UUID
    found = await client.find_automation(automation.id)
    assert found == automation

    # Test finding by UUID string
    found = await client.find_automation(str(automation.id))
    assert found == automation

    # Test finding by exact name
    found = await client.find_automation(automation.name)
    assert found == automation

    # Test finding by case-insensitive name
    found = await client.find_automation(automation.name.upper())
    assert found == automation

    # Test finding nonexistent UUID raises ObjectNotFound
    with pytest.raises(ObjectNotFound):
        await client.find_automation(UUID("6d222a09-3c68-42d4-b019-bd331a3abb88"))

    # Test finding nonexistent name returns None
    found = await client.find_automation("nonexistent_name")
    assert found is None
