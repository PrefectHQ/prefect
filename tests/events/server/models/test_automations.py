from datetime import timedelta
from typing import List, Sequence
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.events import actions, filters
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationCore,
    AutomationCreate,
    AutomationPartialUpdate,
    AutomationSort,
    AutomationUpdate,
    EventTrigger,
    Posture,
)
from prefect.server.events.schemas.events import ResourceSpecification
from prefect.types._datetime import now


async def test_reading_automations_by_workspace_empty(
    automations_session: AsyncSession,
):
    empty = await automations.read_automations_for_workspace(
        session=automations_session,
    )
    assert len(empty) == 0


async def test_reading_automations_by_workspace_by_name(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_ASC,
    )
    assert [automation.name for automation in existing] == [
        "automation 1",
        "automation 2",
        "automation 3",
        "automation 4",
    ]

    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_DESC,
    )
    assert [automation.name for automation in existing] == [
        "automation 4",
        "automation 3",
        "automation 2",
        "automation 1",
    ]


async def test_reading_automations_by_workspace_by_name_filtered_match(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_ASC,
        automation_filter=filters.AutomationFilter(name={"any_": ["automation 2"]}),
    )

    assert len(existing) == 1

    assert existing[0].name == "automation 2"


async def test_reading_automations_by_workspace_by_name_filtered_match_many(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_ASC,
        automation_filter=filters.AutomationFilter(
            name={"any_": ["automation 2", "automation 3"]}
        ),
    )

    assert len(existing) == 2

    assert [automation.name for automation in existing] == [
        "automation 2",
        "automation 3",
    ]


async def test_reading_automations_by_workspace_by_name_filtered_mismatch(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_ASC,
        automation_filter=filters.AutomationFilter(name={"any_": ["automation 5"]}),
    )

    assert len(existing) == 0


async def test_reading_automations_by_workspace_paging(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_ASC,
        limit=2,
    )
    assert [automation.name for automation in existing] == [
        "automation 1",
        "automation 2",
    ]

    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.NAME_ASC,
        limit=2,
        offset=1,
    )
    assert [automation.name for automation in existing] == [
        "automation 2",
        "automation 3",
    ]


async def test_reading_automations_by_workspace_by_times(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.CREATED_DESC,
    )
    assert len(existing) == 4
    returned = [automation.created for automation in existing]
    assert returned == sorted(returned, reverse=True)

    existing = await automations.read_automations_for_workspace(
        session=automations_session,
        sort=AutomationSort.UPDATED_DESC,
    )
    assert len(existing) == 4
    returned = [automation.updated for automation in existing]
    assert returned == sorted(returned, reverse=True)


async def test_counting_automations_by_workspace_empty(
    automations_session: AsyncSession,
):
    count = await automations.count_automations_for_workspace(
        session=automations_session
    )
    assert count == 0


async def test_counting_automations_by_workspace(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    count = await automations.count_automations_for_workspace(
        session=automations_session,
    )
    assert count == 4


async def test_creating_automation(automations_session: AsyncSession):
    # These will be what users provide at the API
    automation_request = AutomationCreate(
        name="a fresh automation for ya",
        trigger=EventTrigger(
            expect={"things.happened"},
            match=ResourceSpecification.model_validate(
                {"prefect.resource.id": "some-resource"}
            ),
            posture=Posture.Reactive,
            threshold=42,
            within=timedelta(seconds=42),
        ),
        actions=[actions.DoNothing()],
    )
    # This is what the models require
    automation = Automation(
        **automation_request.model_dump(),
    )
    saved_automation = await automations.create_automation(
        session=automations_session,
        automation=automation,
    )
    assert isinstance(saved_automation, Automation)
    assert saved_automation is not automation
    assert saved_automation.id
    assert saved_automation.created
    assert saved_automation.updated
    assert saved_automation.name == automation.name
    assert saved_automation.description == automation.description
    assert saved_automation.enabled is True
    assert saved_automation.trigger == automation.trigger

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=saved_automation.id,
    )
    assert isinstance(reloaded_automation, Automation)
    assert reloaded_automation is not automation
    assert reloaded_automation is not saved_automation
    assert reloaded_automation == saved_automation


@pytest.fixture
async def existing_automation(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
) -> Automation:
    automation = db.Automation(
        id=uuid4(),
        name="a automation that is already here, thank you",
        trigger=EventTrigger(
            expect=("things.happened",),
            match=ResourceSpecification.model_validate(
                {"prefect.resource.id": "some-resource"}
            ),
            posture=Posture.Reactive,
            threshold=42,
            within=timedelta(seconds=42),
        ),
        actions=[actions.DoNothing()],
    )
    automations_session.add(automation)
    await automations_session.flush()
    return Automation.model_validate(automation, from_attributes=True)


async def test_updating_automation_that_exists(
    automations_session: AsyncSession, existing_automation: Automation
):
    # take it to a core schema first to remove unexpected fields
    as_core = AutomationCore(**existing_automation.model_dump())
    assert as_core.enabled

    update = AutomationUpdate(**as_core.model_dump())
    update.enabled = False
    assert isinstance(update.trigger, EventTrigger)
    update.trigger.expect = {"things.definitely.did.not.happen", "or.maybe.not"}
    update.trigger.threshold = 3
    update.trigger.within = timedelta(seconds=42)

    result = await automations.update_automation(
        session=automations_session,
        automation_update=update,
        automation_id=existing_automation.id,
    )
    assert result is True

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=existing_automation.id,
    )
    assert isinstance(reloaded_automation, Automation)
    assert reloaded_automation is not existing_automation
    assert reloaded_automation.id == existing_automation.id

    # these should have changed
    assert not reloaded_automation.enabled
    assert isinstance(reloaded_automation.trigger, EventTrigger)
    assert reloaded_automation.trigger.expect == {
        "things.definitely.did.not.happen",
        "or.maybe.not",
    }
    assert reloaded_automation.trigger.threshold == 3
    assert reloaded_automation.trigger.within == timedelta(seconds=42)

    # these should remain the same
    assert reloaded_automation.name == "a automation that is already here, thank you"
    assert reloaded_automation.trigger.match == ResourceSpecification.model_validate(
        {"prefect.resource.id": "some-resource"}
    )
    assert reloaded_automation.trigger.posture == Posture.Reactive


async def test_partially_updating_automation_that_exists(
    automations_session: AsyncSession, existing_automation: Automation
):
    # take it to a core schema first to remove unexpected fields
    as_core = AutomationCore(**existing_automation.model_dump())
    assert as_core.enabled

    partial_update = AutomationPartialUpdate(enabled=False)

    result = await automations.update_automation(
        session=automations_session,
        automation_update=partial_update,
        automation_id=existing_automation.id,
    )
    assert result is True

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=existing_automation.id,
    )
    assert isinstance(reloaded_automation, Automation)
    assert reloaded_automation is not existing_automation
    assert reloaded_automation.id == existing_automation.id

    # these should have changed
    assert not reloaded_automation.enabled

    # these should remain the same
    assert reloaded_automation.name == "a automation that is already here, thank you"
    assert reloaded_automation.trigger.match == ResourceSpecification.model_validate(
        {"prefect.resource.id": "some-resource"}
    )
    assert reloaded_automation.trigger.posture == Posture.Reactive


async def test_updating_automation_that_does_not_exist(
    automations_session: AsyncSession,
):
    hypothetical_id = uuid4()

    update = AutomationUpdate(
        name="well this is terribly awkward",
        trigger=EventTrigger(
            expect=("things.happened",),
            match=ResourceSpecification.model_validate(
                {"prefect.resource.id": "some-resource"}
            ),
            posture=Posture.Reactive,
            threshold=42,
            within=timedelta(seconds=42),
        ),
        actions=[actions.DoNothing()],
    )
    result = await automations.update_automation(
        session=automations_session,
        automation_update=update,
        automation_id=hypothetical_id,
    )
    assert result is False

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=hypothetical_id,
    )
    assert reloaded_automation is None


async def test_updating_automation_with_create_schema_is_not_allowed(
    automations_session: AsyncSession,
):
    hypothetical_id = uuid4()

    create = AutomationCreate(
        name="well this is terribly awkward",
        trigger=EventTrigger(
            expect=("things.happened",),
            match=ResourceSpecification.model_validate(
                {"prefect.resource.id": "some-resource"}
            ),
            posture=Posture.Reactive,
            threshold=42,
            within=timedelta(seconds=42),
        ),
        actions=[actions.DoNothing()],
    )
    with pytest.raises(TypeError, match="AutomationUpdate or AutomationPartialUpdate"):
        await automations.update_automation(
            session=automations_session,
            automation_update=create,
            automation_id=hypothetical_id,
        )


async def test_deleting_automation_that_exists(
    automations_session: AsyncSession, existing_automation: Automation
):
    result = await automations.delete_automation(
        session=automations_session,
        automation_id=existing_automation.id,
    )
    assert result is True

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=existing_automation.id,
    )
    assert reloaded_automation is None


async def test_deleting_automation_that_does_not_exist(
    automations_session: AsyncSession,
):
    hypothetical_id = uuid4()

    result = await automations.delete_automation(
        session=automations_session,
        automation_id=hypothetical_id,
    )
    assert result is False

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=hypothetical_id,
    )
    assert reloaded_automation is None


async def test_reading_automations_from_related_resource(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    deployment_resource_id = f"prefect.deployment.{uuid4()}"

    for automation in some_workspace_automations[:3]:
        await automations.relate_automation_to_resource(
            session=automations_session,
            automation_id=automation.id,
            resource_id=deployment_resource_id,
            owned_by_resource=False,
        )

    retrieved = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id=deployment_resource_id,
    )

    assert {automation.id for automation in some_workspace_automations[:3]} == {
        automation.id for automation in retrieved
    }


async def test_reading_automations_from_related_resource_owned_by(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    deployment_resource_id = f"prefect.deployment.{uuid4()}"

    await automations.relate_automation_to_resource(
        session=automations_session,
        automation_id=some_workspace_automations[0].id,
        resource_id=deployment_resource_id,
        owned_by_resource=True,
    )

    for automation in some_workspace_automations[1:]:
        await automations.relate_automation_to_resource(
            session=automations_session,
            automation_id=automation.id,
            resource_id=deployment_resource_id,
            owned_by_resource=False,
        )

    retrieved = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id=deployment_resource_id,
        owned_by_resource=True,
    )

    assert len(retrieved) == 1
    assert retrieved[0].id == some_workspace_automations[0].id


async def test_reading_automations_from_related_resource_filter_created_before(
    db: PrefectDBInterface,
    automations_session: AsyncSession,
    some_workspace_automations: List[Automation],
):
    deployment_resource_id = f"prefect.deployment.{uuid4()}"

    for automation in some_workspace_automations[:3]:
        await automations.relate_automation_to_resource(
            session=automations_session,
            automation_id=automation.id,
            resource_id=deployment_resource_id,
            owned_by_resource=False,
        )

    old_automation = some_workspace_automations[0]
    horizon = now("UTC") - timedelta(days=1)

    await automations_session.execute(
        sa.update(db.Automation)
        .where(db.Automation.id == old_automation.id)
        .values(created=horizon - timedelta(days=1))
    )

    retrieved = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id=deployment_resource_id,
        automation_filter=filters.AutomationFilter(
            created=filters.AutomationFilterCreated(before_=horizon)
        ),
    )

    assert {old_automation.id} == {automation.id for automation in retrieved}


async def test_deleting_automations_owned_by_resource(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    deployment_resource_id = f"prefect.deployment.{uuid4()}"

    for automation in some_workspace_automations[:3]:
        await automations.relate_automation_to_resource(
            session=automations_session,
            automation_id=automation.id,
            resource_id=deployment_resource_id,
            owned_by_resource=True,
        )

    deleted_automation_ids = await automations.delete_automations_owned_by_resource(
        session=automations_session,
        resource_id=deployment_resource_id,
    )

    assert set(deleted_automation_ids) == {
        automation.id for automation in some_workspace_automations[:3]
    }

    for automation in some_workspace_automations[:3]:
        reloaded_automation = await automations.read_automation(
            session=automations_session,
            automation_id=automation.id,
        )
        assert reloaded_automation is None


@pytest.fixture
def uninteresting_trigger() -> EventTrigger:
    return EventTrigger(
        expect={"things.happened"},
        match=ResourceSpecification.model_validate(
            {"prefect.resource.id": "some-resource"}
        ),
        posture=Posture.Reactive,
        threshold=42,
        within=timedelta(seconds=42),
    )


async def test_creating_automation_creates_relations_to_resources(
    automations_session: AsyncSession,
    uninteresting_trigger: EventTrigger,
):
    # It's not important whether these _actually_ exist
    first_deployment = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    second_deployment = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    # These will be what users provide at the API
    automation_request = AutomationCreate(
        name="a fresh automation for ya",
        trigger=uninteresting_trigger,
        actions=[
            actions.RunDeployment(source="selected", deployment_id=first_deployment),
            actions.RunDeployment(source="selected", deployment_id=second_deployment),
        ],
    )
    # This is what the models require
    automation = Automation(
        **automation_request.model_dump(),
    )

    new_automation = await automations.create_automation(
        session=automations_session,
        automation=automation,
    )

    related_to_first = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    assert related_to_first == [new_automation]

    related_to_second = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    assert related_to_second == [new_automation]


async def test_creating_automation_skips_relating_inferred_deployments(
    automations_session: AsyncSession,
    uninteresting_trigger: EventTrigger,
):
    """Regression test where we were creating links to prefect.deployment.None resources
    when using inferred deployments"""
    # It's not important whether these _actually_ exist
    first_deployment = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # These will be what users provide at the API
    automation_request = AutomationCreate(
        name="a fresh automation for ya",
        trigger=uninteresting_trigger,
        actions=[
            actions.RunDeployment(source="selected", deployment_id=first_deployment),
            actions.RunDeployment(source="inferred"),
        ],
    )
    # This is what the models require
    automation = Automation(
        **automation_request.model_dump(),
    )

    new_automation = await automations.create_automation(
        session=automations_session,
        automation=automation,
    )

    related_to_first = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    assert related_to_first == [new_automation]

    related_to_none = await automations.read_automations_related_to_resource(
        session=automations_session,
        # This was the bug, we'd create links to "prefect.deployment.None"
        resource_id="prefect.deployment.None",
    )
    assert related_to_none == []


@pytest.fixture
async def existing_related_automation(
    automations_session: AsyncSession,
    uninteresting_trigger: EventTrigger,
) -> Automation:
    # It's not important whether these _actually_ exist
    first_deployment = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    second_deployment = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    automation_request = AutomationCreate(
        name="a fresh automation for ya",
        trigger=uninteresting_trigger,
        actions=[
            actions.RunDeployment(source="selected", deployment_id=first_deployment),
            actions.RunDeployment(source="selected", deployment_id=second_deployment),
        ],
    )
    automation = await automations.create_automation(
        session=automations_session,
        automation=Automation(
            **automation_request.model_dump(),
        ),
    )

    # Give it an owner that we _won't_ be mucking with when we update
    await automations.relate_automation_to_resource(
        session=automations_session,
        automation_id=automation.id,
        resource_id="prefect.deployment.ffffffff-ffff-ffff-ffff-ffffffffffff",
        owned_by_resource=True,
    )

    return automation


async def test_updating_automation_updates_relations_to_resources(
    automations_session: AsyncSession,
    existing_related_automation: Automation,
):
    # It's not important whether these _actually_ exist
    first_deployment = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    third_deployment = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    update_request = AutomationUpdate(
        name=existing_related_automation.name,
        trigger=existing_related_automation.trigger,
        actions=[
            actions.RunDeployment(source="selected", deployment_id=first_deployment),
            actions.RunDeployment(source="selected", deployment_id=third_deployment),
        ],
    )

    await automations.update_automation(
        session=automations_session,
        automation_update=update_request,
        automation_id=existing_related_automation.id,
    )
    existing_related_automation = await automations.read_automation_by_id(
        session=automations_session, automation_id=existing_related_automation.id
    )

    # The owner is always retained
    related_to_owner = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.ffffffff-ffff-ffff-ffff-ffffffffffff",
    )
    assert related_to_owner == [existing_related_automation]

    related_to_first = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    assert related_to_first == [existing_related_automation]

    related_to_second = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    assert related_to_second == []

    related_to_third = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.cccccccc-cccc-cccc-cccc-cccccccccccc",
    )
    assert related_to_third == [existing_related_automation]


async def test_updating_automation_updates_relations_to_resources_with_matching_owner(
    automations_session: AsyncSession,
    existing_related_automation: Automation,
):
    # It's not important whether these _actually_ exist
    first_deployment = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    third_deployment = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    owning_deployment = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    update_request = AutomationUpdate(
        name=existing_related_automation.name,
        trigger=existing_related_automation.trigger,
        actions=[
            actions.RunDeployment(source="selected", deployment_id=first_deployment),
            actions.RunDeployment(source="selected", deployment_id=third_deployment),
            # Include the owner here to demonstrate that we don't produce duplicates
            actions.RunDeployment(source="selected", deployment_id=owning_deployment),
        ],
    )

    await automations.update_automation(
        session=automations_session,
        automation_update=update_request,
        automation_id=existing_related_automation.id,
    )
    existing_related_automation = await automations.read_automation_by_id(
        session=automations_session, automation_id=existing_related_automation.id
    )

    # The owner is always retained
    related_to_owner = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.ffffffff-ffff-ffff-ffff-ffffffffffff",
    )
    assert related_to_owner == [existing_related_automation]

    related_to_first = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    assert related_to_first == [existing_related_automation]

    related_to_second = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    assert related_to_second == []

    related_to_third = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.cccccccc-cccc-cccc-cccc-cccccccccccc",
    )
    assert related_to_third == [existing_related_automation]


async def test_deleting_automation_updates_relations_to_resources(
    automations_session: AsyncSession,
    existing_related_automation: Automation,
):
    await automations.delete_automation(
        session=automations_session,
        automation_id=existing_related_automation.id,
    )
    existing_related_automation = await automations.read_automation_by_id(
        session=automations_session, automation_id=existing_related_automation.id
    )

    # The owner relation is removed because the automation itself is gone
    related_to_owner = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.ffffffff-ffff-ffff-ffff-ffffffffffff",
    )
    assert related_to_owner == []

    related_to_first = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    assert related_to_first == []

    related_to_second = await automations.read_automations_related_to_resource(
        session=automations_session,
        resource_id="prefect.deployment.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    assert related_to_second == []


async def test_deleting_automations_by_workspace(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    related = some_workspace_automations[0]
    await automations.relate_automation_to_resource(
        automations_session, related.id, "my.owner", True
    )
    await automations.relate_automation_to_resource(
        automations_session, related.id, "another.one", False
    )

    unrelated = some_workspace_automations[1]
    await automations.relate_automation_to_resource(
        automations_session, unrelated.id, "my.owner", True
    )
    await automations.relate_automation_to_resource(
        automations_session, unrelated.id, "another.one", False
    )

    await automations.delete_automations_for_workspace(automations_session)

    # show that we've removed all the automations and related objects for the workspace
    for automation in some_workspace_automations:
        reloaded = await automations.read_automation_by_id(
            automations_session, automation.id
        )
        assert reloaded is None

    assert not await automations.read_automations_related_to_resource(
        automations_session, "my.owner"
    )
    assert not await automations.read_automations_related_to_resource(
        automations_session, "another.one"
    )


async def test_disable_automations_by_workspace(
    automations_session: AsyncSession,
    some_workspace_automations: Sequence[Automation],
):
    assert len(some_workspace_automations) > 1
    assert all([a.enabled for a in some_workspace_automations])

    await automations.disable_automations_for_workspace(automations_session)

    # show that we've removed all automations were disabled
    for automation in some_workspace_automations:
        reloaded = await automations.read_automation_by_id(
            automations_session, automation.id
        )
        assert not reloaded.enabled


async def test_disabling_automation_that_exists(
    automations_session: AsyncSession, existing_automation: Automation
):
    # take it to a core schema first to remove unexpected fields
    as_core = AutomationCore(**existing_automation.model_dump())
    assert as_core.enabled

    result = await automations.disable_automation(
        session=automations_session,
        automation_id=existing_automation.id,
    )
    assert result is True

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=existing_automation.id,
    )
    assert isinstance(reloaded_automation, Automation)
    assert reloaded_automation is not existing_automation
    assert reloaded_automation.id == existing_automation.id

    # these should have changed
    assert not reloaded_automation.enabled

    # these should remain the same
    assert reloaded_automation.name == "a automation that is already here, thank you"
    assert reloaded_automation.trigger.match == ResourceSpecification.model_validate(
        {"prefect.resource.id": "some-resource"}
    )
    assert reloaded_automation.trigger.posture == Posture.Reactive


async def test_disabling_automation_that_does_not_exist(
    automations_session: AsyncSession,
):
    hypothetical_id = uuid4()

    with pytest.raises(ValueError, match="not found"):
        await automations.disable_automation(
            session=automations_session,
            automation_id=hypothetical_id,
        )

    reloaded_automation = await automations.read_automation(
        session=automations_session,
        automation_id=hypothetical_id,
    )
    assert reloaded_automation is None
