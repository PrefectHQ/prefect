from uuid import UUID

import pytest

import prefect.exceptions
from prefect import flow
from prefect.automations import Automation, EventTrigger, Posture
from prefect.server.events import ResourceSpecification
from prefect.server.events.actions import DoNothing
from prefect.settings import PREFECT_EXPERIMENTAL_EVENTS, temporary_settings


@pytest.fixture(autouse=True)
def enable_task_scheduling():
    with temporary_settings({PREFECT_EXPERIMENTAL_EVENTS: True}):
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

    model = await Automation.create(automation=automation_to_create)
    return model


@pytest.fixture
async def automation_with_updates():
    automation_to_update = Automation(
        name="goodbye",
        description="mars",
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
    return automation_to_update


async def test_read_automation_by_uuid(automation):
    model = await Automation.read(automation)
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == ResourceSpecification(
        __root__={"prefect.resource.name": "howdy!"}
    )
    assert model.trigger.match_related == ResourceSpecification(
        __root__={"prefect.resource.role": "something-cool"}
    )
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == {"prefect.resource.name"}
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0] == DoNothing(type="do-nothing")


async def test_read_automation_by_uuid_string(automation):
    model = await Automation.read(str(automation))
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == ResourceSpecification(
        __root__={"prefect.resource.name": "howdy!"}
    )
    assert model.trigger.match_related == ResourceSpecification(
        __root__={"prefect.resource.role": "something-cool"}
    )
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == {"prefect.resource.name"}
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0] == DoNothing(type="do-nothing")


async def test_read_automation_by_name(automation):
    automation_name = "hello"
    model = await Automation.read(automation_name)
    assert model.name == "hello"
    assert model.description == "world"
    assert model.enabled is True
    assert model.trigger.match == ResourceSpecification(
        __root__={"prefect.resource.name": "howdy!"}
    )
    assert model.trigger.match_related == ResourceSpecification(
        __root__={"prefect.resource.role": "something-cool"}
    )
    assert model.trigger.after == {"this.one", "or.that.one"}
    assert model.trigger.expect == {"surely.this", "but.also.this"}
    assert model.trigger.for_each == {"prefect.resource.name"}
    assert model.trigger.posture == Posture.Reactive
    assert model.trigger.threshold == 42
    assert model.actions[0] == DoNothing(type="do-nothing")


async def test_update_automation(automation, automation_with_updates):
    model = await Automation.update(
        automation_id=automation, automation=automation_with_updates
    )
    model = await Automation.read(automation)
    assert model.name == "goodbye"


async def test_disable_automation(automation):
    model = await Automation.disable(automation)
    model = await Automation.read(automation)
    assert model.enabled is False


async def test_enable_automation(automation):
    model = await Automation.enable(automation)
    model = await Automation.read(automation)
    assert model.enabled is True


async def test_automatinos_work_in_sync_flows(automation_spec):
    @flow
    def create_automation():
        auto = Automation.create(automation=automation_spec)
        return auto

    auto = create_automation()
    assert isinstance(auto, UUID)


async def test_automatinos_work_in_async_flows(automation_spec):
    @flow
    async def create_automation():
        auto = await Automation.create(automation=automation_spec)
        return auto

    res = await create_automation()
    assert isinstance(res, UUID)


async def test_delete_automation(automation):
    await Automation.delete(automation)
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await Automation.read(automation)
