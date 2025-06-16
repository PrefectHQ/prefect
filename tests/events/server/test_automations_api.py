import textwrap
from datetime import timedelta
from typing import Any, Dict, List, Optional
from unittest import mock
from uuid import UUID, uuid4

import httpx
import pydantic
import pytest
import sqlalchemy as sa
from fastapi.applications import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models as server_models
from prefect.server import schemas as server_schemas
from prefect.server.api.validation import ValidationError
from prefect.server.database import PrefectDBInterface
from prefect.server.events import actions, filters
from prefect.server.events.models.automations import (
    create_automation,
    read_automations_related_to_resource,
    relate_automation_to_resource,
)
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationCore,
    AutomationCreate,
    AutomationPartialUpdate,
    AutomationSort,
    AutomationUpdate,
    CompoundTrigger,
    EventTrigger,
    Posture,
)
from prefect.server.models import deployments
from prefect.settings import (
    PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    temporary_settings,
)
from prefect.types import DateTime
from prefect.types._datetime import now as now_fn
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture(autouse=True)
def enable_automations():
    with temporary_settings(
        {
            PREFECT_API_SERVICES_TRIGGERS_ENABLED: True,
        }
    ):
        yield


@pytest.fixture
async def client(app: FastAPI):
    # The automations tests assume that the client will not raise exceptions and will
    # serve any server-side errors as HTTP responses.  This is different than some other
    # parts of the general test suite, so we'll override the fixture here.

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://test/api"
    ) as async_client:
        yield async_client


@pytest.fixture
def workspace_url() -> str:
    return "https://test/api"


@pytest.fixture
def automations_url(workspace_url: str) -> str:
    return f"{workspace_url}/automations"


@pytest.fixture
def automation_to_create() -> AutomationCreate:
    return AutomationCreate(
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
            within=timedelta(minutes=2),
        ),
        actions=[actions.DoNothing()],
    )


async def create_work_pool(
    session,
    pool_schema: dict,
    type: str = "None",
):
    work_pool = await server_models.workers.create_work_pool(
        session=session,
        work_pool=server_schemas.actions.WorkPoolCreate.model_construct(
            _fields_set=server_schemas.actions.WorkPoolCreate.model_fields_set,
            name="wp-1",
            type=type,
            description="None",
            base_job_template=pool_schema,
        ),
    )
    await session.commit()
    return work_pool


async def create_deployment(session, work_pool, job_vars: dict) -> UUID:
    flow = await server_models.flows.create_flow(
        session=session, flow=server_schemas.core.Flow(name="my-flow")
    )

    deployment = await deployments.create_deployment(
        session=session,
        deployment=server_schemas.core.Deployment(
            name="My Deployment X",
            flow_id=flow.id,
            paused=False,
            work_queue_id=work_pool.default_queue_id,
        ),
    )
    return deployment.id


async def create_run_deployment_automation_payload(deployment_id: UUID, job_vars: dict):
    return AutomationCreate(
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
            within=timedelta(minutes=2),
        ),
        actions=[
            actions.RunDeployment(job_variables=job_vars, deployment_id=deployment_id)
        ],
    )


async def create_objects_for_automation(
    session: AsyncSession,
    *,
    base_job_template: Optional[dict] = None,
    deployment_vars: Optional[dict] = None,
    run_deployment_job_variables: Optional[dict] = None,
    work_pool_type: str = "None",
):
    base_job_template = base_job_template or {}
    deployment_vars = deployment_vars or {}
    run_deployment_job_variables = run_deployment_job_variables or {}

    wp = await create_work_pool(session, base_job_template, type=work_pool_type)
    deployment = await create_deployment(session, wp, deployment_vars)
    automation = await create_run_deployment_automation_payload(
        deployment, run_deployment_job_variables
    )

    await session.commit()

    return wp, deployment, automation


@pytest.mark.parametrize(
    "invalid_time",
    [
        timedelta(seconds=-10),
        timedelta(seconds=-1),
        timedelta(seconds=-0.001),
    ],
)
def test_negative_within_not_allowed(invalid_time: timedelta):
    with pytest.raises(
        pydantic.ValidationError, match="greater than or equal to 0 seconds"
    ):
        EventTrigger(posture=Posture.Reactive, threshold=1, within=invalid_time)

    with pytest.raises(
        pydantic.ValidationError, match="greater than or equal to 10 seconds"
    ):
        EventTrigger(posture=Posture.Proactive, threshold=1, within=invalid_time)


def test_minimum_reactive_within_is_required_but_defaulted():
    with pytest.raises(pydantic.ValidationError, match="should be a valid timedelta"):
        EventTrigger(posture=Posture.Reactive, threshold=1, within=None)

    trigger = EventTrigger(posture=Posture.Reactive, threshold=1)
    assert trigger.within == timedelta(seconds=0)


@pytest.mark.parametrize(
    "invalid_time",
    [
        timedelta(seconds=1),
        timedelta(seconds=9),
        timedelta(seconds=9, microseconds=999999),
    ],
)
def test_minimum_proactive_within_is_enforced(invalid_time: timedelta):
    with pytest.raises(
        pydantic.ValidationError, match="greater than or equal to 10 seconds"
    ):
        EventTrigger(posture=Posture.Proactive, threshold=1, within=invalid_time)


def test_minimum_proactive_within_is_required_but_defaulted():
    with pytest.raises(pydantic.ValidationError, match="should be a valid timedelta"):
        EventTrigger(posture=Posture.Proactive, threshold=1, within=None)

    trigger = EventTrigger(posture=Posture.Proactive, threshold=1, within=0)
    assert trigger.within == timedelta(seconds=10)

    trigger = EventTrigger(posture=Posture.Proactive, threshold=1)
    assert trigger.within == timedelta(seconds=10)


async def test_create_automation_allows_specifying_just_owner_resource(
    client: AsyncClient,
    automations_session: AsyncSession,
    automations_url: str,
    automation_to_create: AutomationCreate,
) -> None:
    deployment_id = uuid4()
    automation_to_create.owner_resource = f"prefect.deployment.{deployment_id}"

    response = await client.post(
        f"{automations_url}/",
        json=automation_to_create.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)

    related_automations = await read_automations_related_to_resource(
        session=automations_session,
        resource_id=automation_to_create.owner_resource,
        owned_by_resource=True,
    )

    assert {automation.id for automation in related_automations} == {
        created_automation.id
    }


async def test_create_automation_allows_specifying_owner_resource_and_actions(
    client: AsyncClient,
    automations_session: AsyncSession,
    automations_url: str,
    automation_to_create: AutomationCreate,
) -> None:
    """Regression test for an issue where the owner_resource was being ignored on the
    creation of automations when they actually have the RunDeployment actions, because
    we'd already created a relationship to the deployment where it was False"""
    deployment_id = uuid4()
    other_one = uuid4()
    automation_to_create.owner_resource = f"prefect.deployment.{deployment_id}"
    automation_to_create.actions += [
        actions.RunDeployment(source="selected", deployment_id=deployment_id),
        actions.RunDeployment(source="selected", deployment_id=other_one),
    ]

    response = await client.post(
        f"{automations_url}/",
        json=automation_to_create.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)

    related_automations = await read_automations_related_to_resource(
        session=automations_session,
        resource_id=automation_to_create.owner_resource,
        owned_by_resource=True,
    )
    assert {automation.id for automation in related_automations} == {
        created_automation.id
    }

    # The other deployment should _not_ be marked as an owner...
    related_automations = await read_automations_related_to_resource(
        session=automations_session,
        resource_id=f"prefect.deployment.{other_one}",
        owned_by_resource=True,
    )
    assert not related_automations

    # ...but it should have been created as related
    related_automations = await read_automations_related_to_resource(
        session=automations_session,
        resource_id=f"prefect.deployment.{other_one}",
        owned_by_resource=False,
    )
    assert {automation.id for automation in related_automations} == {
        created_automation.id
    }


async def test_create_automation_overrides_client_provided_trigger_ids(
    client: AsyncClient,
    automations_url: str,
    automation_to_create: AutomationCreate,
) -> None:
    # replace the trigger with a compound one with a nested trigger
    inner_trigger = automation_to_create.trigger
    outer_trigger = automation_to_create.trigger = CompoundTrigger(
        within=timedelta(seconds=60),
        require="any",
        triggers=[inner_trigger],
    )

    response = await client.post(
        f"{automations_url}/",
        json=automation_to_create.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)

    assert isinstance(created_automation.trigger, CompoundTrigger)

    assert created_automation.trigger.id != outer_trigger.id
    assert created_automation.trigger.triggers[0].id != inner_trigger.id


@pytest.fixture
async def existing_automation(
    automations_session: AsyncSession,
    automation_to_create: AutomationCreate,
) -> Automation:
    existing = await create_automation(
        automations_session,
        Automation(
            **automation_to_create.model_dump(),
        ),
    )
    await automations_session.commit()

    assert existing.id
    assert existing.created

    return existing


@pytest.fixture
async def existing_disabled_invalid_automation(
    automations_session: AsyncSession,
    automation_to_create: AutomationCreate,
) -> Automation:
    automation_to_create.enabled = False
    automation_to_create.trigger = EventTrigger(
        match={"prefect.resource.id": "prefect.flow-run.*"},
        for_each={"prefect.resource.id"},
        expect={"prefect.flow-run.*"},
        posture=Posture.Reactive,
        threshold=1,
        within=timedelta(seconds=0),
    )
    automation_to_create.actions = [actions.RunDeployment(source="inferred")]

    existing = await create_automation(
        automations_session,
        Automation(
            **automation_to_create.model_dump(),
        ),
    )
    await automations_session.commit()

    assert existing.id
    assert existing.created

    # it should be valid while it's disabled
    Automation.model_validate(existing, from_attributes=True)

    # But not while it's enabled
    existing.enabled = True
    with pytest.raises(pydantic.ValidationError):
        Automation.model_validate(existing, from_attributes=True)

    return existing


@pytest.fixture
def automation_update(existing_automation: Automation) -> AutomationUpdate:
    as_core = AutomationCore(**existing_automation.model_dump())
    assert as_core.enabled

    update = AutomationUpdate(**as_core.model_dump())
    update.enabled = False

    assert isinstance(update.trigger, EventTrigger)
    update.trigger.expect = {"things.definitely.did.not.happen", "or.maybe.not"}
    update.trigger.threshold = 3
    update.trigger.within = timedelta(seconds=42)

    return update


async def test_update_automation(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
    automation_update: AutomationUpdate,
) -> None:
    response = await client.put(
        f"{automations_url}/{existing_automation.id}",
        json=automation_update.model_dump(mode="json"),
    )
    assert response.status_code == 204, response.content

    response = await client.get(
        f"{automations_url}/{existing_automation.id}",
    )
    assert response.status_code == 200, response.content

    updated_automation = Automation.model_validate_json(response.content)
    assert updated_automation.enabled is False

    assert isinstance(updated_automation.trigger, EventTrigger)
    assert updated_automation.trigger.expect == {
        "things.definitely.did.not.happen",
        "or.maybe.not",
    }
    assert updated_automation.trigger.threshold == 3
    assert updated_automation.trigger.within == timedelta(seconds=42)


async def test_update_automation_404s_on_unknown_id(
    client: AsyncClient,
    automations_url: str,
    automation_update: AutomationUpdate,
) -> None:
    response = await client.put(
        f"{automations_url}/{uuid4()}",
        json=automation_update.model_dump(mode="json"),
    )
    assert response.status_code == 404, response.content
    assert "Automation not found" in response.content.decode()


async def test_update_automation_cannot_change_id(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
    automation_update: AutomationUpdate,
) -> None:
    update = automation_update.model_dump(mode="json")

    # try to set an alternative id manually in the payload
    update["id"] = str(uuid4())

    response = await client.put(
        f"{automations_url}/{existing_automation.id}",
        json=update,
    )
    assert response.status_code == 422, response.content
    assert "extra_forbidden" in response.content.decode()


async def test_update_automation_overrides_client_provided_trigger_ids(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
    automation_update: AutomationUpdate,
) -> None:
    # replace the trigger with a compound one with a nested trigger
    inner_trigger = automation_update.trigger
    outer_trigger = automation_update.trigger = CompoundTrigger(
        within=timedelta(seconds=60),
        require="any",
        triggers=[inner_trigger],
    )

    response = await client.put(
        f"{automations_url}/{existing_automation.id}",
        json=automation_update.model_dump(mode="json"),
    )
    assert response.status_code == 204, response.content

    response = await client.get(
        f"{automations_url}/{existing_automation.id}",
    )
    assert response.status_code == 200, response.content

    updated_automation = Automation.model_validate_json(response.content)

    assert isinstance(updated_automation.trigger, CompoundTrigger)

    assert updated_automation.trigger.id != outer_trigger.id
    assert updated_automation.trigger.triggers[0].id != inner_trigger.id


@pytest.fixture
def automation_patch(existing_automation: Automation) -> AutomationPartialUpdate:
    as_core = AutomationCore(**existing_automation.model_dump())
    assert as_core.enabled
    return AutomationPartialUpdate(enabled=False)


async def test_patch_automation(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
    automation_patch: AutomationPartialUpdate,
) -> None:
    response = await client.patch(
        f"{automations_url}/{existing_automation.id}",
        json=automation_patch.model_dump(mode="json"),
    )
    assert response.status_code == 204, response.content

    response = await client.get(
        f"{automations_url}/{existing_automation.id}",
    )
    assert response.status_code == 200, response.content

    updated_automation = Automation.model_validate_json(response.content)
    assert updated_automation.enabled is False


async def test_patch_automation_404s_on_unknown_id(
    client: AsyncClient,
    automations_url: str,
    automation_patch: AutomationPartialUpdate,
) -> None:
    response = await client.patch(
        f"{automations_url}/{uuid4()}",
        json=automation_patch.model_dump(mode="json"),
    )
    assert response.status_code == 404, response.content
    assert "Automation not found" in response.content.decode()


async def test_patch_automation_cannot_change_id(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
    automation_patch: AutomationPartialUpdate,
) -> None:
    update = automation_patch.model_dump(mode="json")

    # try to set an alternative id manually in the payload
    update["id"] = str(uuid4())

    response = await client.patch(
        f"{automations_url}/{existing_automation.id}",
        json=update,
    )
    assert response.status_code == 422, response.content
    assert "extra_forbidden" in response.content.decode()


async def test_patch_automation_cannot_enable_invalid_automation(
    client: AsyncClient,
    automations_url: str,
    existing_disabled_invalid_automation: Automation,
) -> None:
    """Regression test for an issue where we were not checking that an automation will
    be valid once it is enabled, like in the case of the infinitely recursive
    automations.  See tests/events/actions_tests/test_infinite_loops.py for more
    info and examples."""
    response = await client.patch(
        f"{automations_url}/{existing_disabled_invalid_automation.id}",
        json=AutomationPartialUpdate(enabled=True).model_dump(mode="json"),
    )
    assert response.status_code == 422, response.content

    # Ensure the error looks like a normal validation response from pydantic
    error = response.json()
    assert error["exception_message"] == "Invalid request received."

    details: List[Dict[str, Any]] = error["exception_detail"]
    assert len(details) == 1
    (detail,) = details

    assert detail["loc"] == []
    assert detail["type"] == "value_error"
    assert "Running an inferred deployment" in detail["msg"]


async def test_delete_automation(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
) -> None:
    response = await client.delete(
        f"{automations_url}/{existing_automation.id}",
    )
    assert response.status_code == 204, response.content

    response = await client.get(
        f"{automations_url}/{existing_automation.id}",
    )
    assert response.status_code == 404, response.content


async def test_delete_automation_404s_on_unknown_id(
    client: AsyncClient,
    automations_url: str,
) -> None:
    response = await client.delete(
        f"{automations_url}/{uuid4()}",
    )
    assert response.status_code == 404, response.content
    assert "Automation not found" in response.content.decode()


async def test_read_automation(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
) -> None:
    response = await client.get(f"{automations_url}/{existing_automation.id}")
    assert response.status_code == 200, response.content

    read_automation = Automation.model_validate_json(response.content)
    assert read_automation.id
    assert read_automation.name == "hello"
    assert read_automation.description == "world"
    assert read_automation.enabled
    assert read_automation.trigger == existing_automation.trigger


async def test_read_automation_that_does_not_exist(
    client: AsyncClient,
    automations_url: str,
) -> None:
    response = await client.get(f"{automations_url}/{uuid4()}")
    assert response.status_code == 404, response.content
    assert "Automation not found" in response.content.decode()


async def test_read_automations(
    some_workspace_automations: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    response = await client.post(f"{automations_url}/filter")
    assert response.status_code == 200, response.content

    automations = parse_obj_as(List[Automation], response.json())

    expected = sorted(some_workspace_automations, key=lambda a: a.name)

    assert automations == expected


async def test_read_automations_page(
    some_workspace_automations: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    response = await client.post(
        f"{automations_url}/filter",
        json={"limit": 2, "offset": 1, "sort": AutomationSort.UPDATED_DESC},
    )
    assert response.status_code == 200, response.content

    automations = parse_obj_as(List[Automation], response.json())

    # updated is technically Optional, so assert it here to satisfy the type system
    def by_updated(automation: Automation) -> DateTime:
        assert automation.updated
        return automation.updated

    expected = sorted(some_workspace_automations, key=by_updated, reverse=True)
    expected = expected[1:3]

    assert automations == expected


async def test_read_automations_filter_by_name_match(
    some_workspace_automations: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    automation_filter = dict(
        automations=filters.AutomationFilter(
            name=filters.AutomationFilterName(any_=["automation 1", "automation 2"])
        ).model_dump(mode="json")
    )

    response = await client.post(f"{automations_url}/filter", json=automation_filter)

    assert response.status_code == 200, response.content

    automations = parse_obj_as(List[Automation], response.json())

    expected = sorted(some_workspace_automations, key=lambda a: a.name)
    expected = [a for a in expected if a.name in ["automation 1", "automation 2"]]

    assert automations == expected
    assert len(automations) == 2


async def test_read_automations_filter_by_name_mismatch(
    some_workspace_automations: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    automation_filter = dict(
        automations=filters.AutomationFilter(
            name=filters.AutomationFilterName(any_=["nonexistentautomation"])
        ).model_dump(mode="json")
    )

    response = await client.post(f"{automations_url}/filter", json=automation_filter)

    assert response.status_code == 200, response.content

    assert response.json() == []


@pytest.fixture
async def automations_with_tags(
    automations_session: AsyncSession,
) -> List[Automation]:
    """Create test automations with various tag combinations for filtering tests"""
    automation_configs = [
        {
            "name": "automation-tag-1",
            "tags": ["production", "critical"],
        },
        {
            "name": "automation-tag-2",
            "tags": ["staging", "experimental"],
        },
        {
            "name": "automation-tag-3",
            "tags": ["production", "monitoring"],
        },
        {
            "name": "automation-tag-4",
            "tags": ["production", "critical", "monitoring"],
        },
        {
            "name": "automation-no-tags",
            "tags": [],
        },
    ]

    automations = []
    for config in automation_configs:
        automation_to_create = AutomationCreate(
            name=config["name"],
            description="Test automation for tag filtering",
            enabled=True,
            tags=config["tags"],
            trigger=EventTrigger(
                match={"prefect.resource.name": "test"},
                expect={"test.event"},
                threshold=1,
                within=timedelta(seconds=30),
                posture=Posture.Reactive,
            ),
            actions=[actions.DoNothing()],
        )

        automation = await create_automation(
            automations_session,
            Automation(**automation_to_create.model_dump()),
        )
        automations.append(automation)

    await automations_session.commit()
    return automations


async def test_read_automations_filter_tags_any(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations by tags using any_ filter"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            tags=filters.AutomationFilterTags(any_=["production"])
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]

    # Should match automations that have "production" tag
    expected_names = {"automation-tag-1", "automation-tag-3", "automation-tag-4"}
    actual_names = {a.name for a in automations}
    assert actual_names == expected_names


async def test_read_automations_filter_tags_any_multiple(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations by tags using any_ filter with multiple tags"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            tags=filters.AutomationFilterTags(any_=["critical", "experimental"])
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]

    # Should match automations that have either "critical" or "experimental" tag
    expected_names = {"automation-tag-1", "automation-tag-2", "automation-tag-4"}
    actual_names = {a.name for a in automations}
    assert actual_names == expected_names


async def test_read_automations_filter_tags_all(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations by tags using all_ filter"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            tags=filters.AutomationFilterTags(all_=["production", "critical"])
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]

    # Should match automations that have both "production" AND "critical" tags
    expected_names = {"automation-tag-1", "automation-tag-4"}
    actual_names = {a.name for a in automations}
    assert actual_names == expected_names


async def test_read_automations_filter_tags_all_no_match(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations by tags using all_ filter with no matches"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            tags=filters.AutomationFilterTags(all_=["nonexistent", "missing"])
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]
    assert len(automations) == 0


async def test_read_automations_filter_tags_is_null_true(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations to only include those without tags"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            tags=filters.AutomationFilterTags(is_null_=True)
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]

    # Should only match the automation with no tags
    expected_names = {"automation-no-tags"}
    actual_names = {a.name for a in automations}
    assert actual_names == expected_names


async def test_read_automations_filter_tags_is_null_false(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations to only include those with tags"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            tags=filters.AutomationFilterTags(is_null_=False)
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]

    # Should match all automations except the one with no tags
    expected_names = {
        "automation-tag-1",
        "automation-tag-2",
        "automation-tag-3",
        "automation-tag-4",
    }
    actual_names = {a.name for a in automations}
    assert actual_names == expected_names


async def test_read_automations_filter_tags_combined_with_name(
    automations_with_tags: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    """Test filtering automations by both tags and name"""
    automation_filter = dict(
        automations=filters.AutomationFilter(
            name=filters.AutomationFilterName(
                any_=["automation-tag-1", "automation-tag-3"]
            ),
            tags=filters.AutomationFilterTags(any_=["production"]),
        ).model_dump(mode="json")
    )
    response = await client.post(f"{automations_url}/filter", json=automation_filter)
    assert response.status_code == 200, response.content

    automations = [Automation.model_validate(a) for a in response.json()]

    # Should match automations that have name in the list AND have "production" tag
    expected_names = {"automation-tag-1", "automation-tag-3"}
    actual_names = {a.name for a in automations}
    assert actual_names == expected_names


async def test_count_automations(
    some_workspace_automations: List[Automation],
    client: AsyncClient,
    automations_url: str,
) -> None:
    response = await client.post(f"{automations_url}/count")
    assert response.status_code == 200, response.content

    count: int = response.json()

    expected = sorted(some_workspace_automations, key=lambda a: a.name)

    assert count == len(expected)


@pytest.fixture
def templates_url(workspace_url: str) -> str:
    return f"{workspace_url}/templates"


async def test_validate_good_template(
    client: AsyncClient,
    templates_url: str,
):
    response = await client.post(
        f"{templates_url}/validate",
        headers={"Content-Type": "text/plain"},
        content="""
        {{ hello }} world!
        """,
    )
    assert response.status_code == 204
    assert response.text == ""


async def test_validate_bad_template(
    client: AsyncClient,
    templates_url: str,
):
    template = textwrap.dedent(
        """
        1 - {{ hello }} world!
        2 - oops, this {{ ain't } gonna work
        3 - this is fine
        """
    ).strip()

    response = await client.post(
        f"{templates_url}/validate",
        headers={"Content-Type": "text/plain"},
        content=template,
    )
    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/json"
    assert response.json() == {
        "error": {
            "line": 2,
            "message": 'unexpected char "\'" at 44',
            "source": template,
        }
    }


async def test_validate_bad_template_loop_constraints(
    client: AsyncClient,
    templates_url: str,
):
    template = textwrap.dedent(
        """
        {% for i in range(100) %}
            {% for j in range(100) %}
                {% for l in range(100) %}
                {% endfor %}"
            {% endfor %}"
        {% endfor %}"
        """
    ).strip()

    response = await client.post(
        f"{templates_url}/validate",
        headers={
            "Content-Type": "text/plain",
        },
        content=template,
    )
    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/json"
    assert response.json() == {
        "error": {
            "line": 0,
            "message": "Contains nested for loops at a depth of 3. Templates can nest for loops no more than 2 loops deep.",
            "source": template,
        }
    }


async def test_read_automations_related_to_resource(
    client: AsyncClient,
    automations_session: AsyncSession,
    automations_url: str,
    some_workspace_automations: List[Automation],
):
    # This test relates the first three automations to this resource, so confirm
    # that there are other related and non-related, automations in the test setup too
    owned = some_workspace_automations[0]
    related = some_workspace_automations[1]
    non_related = some_workspace_automations[2]

    assert owned.id != related.id != non_related.id

    deployment_resource_id = f"prefect.deployment.{uuid4()}"
    for automation in [owned, related]:
        await relate_automation_to_resource(
            session=automations_session,
            automation_id=automation.id,
            resource_id=deployment_resource_id,
            owned_by_resource=(automation == owned),
        )

    await automations_session.commit()

    response = await client.get(
        f"{automations_url}/related-to/{deployment_resource_id}",
    )
    assert response.status_code == 200, response.content

    returned = parse_obj_as(List[Automation], response.json())
    assert returned == [owned, related]


async def test_delete_automations_owned_by_resource(
    db: PrefectDBInterface,
    client: AsyncClient,
    automations_session: AsyncSession,
    automations_url: str,
    some_workspace_automations: List[Automation],
):
    # This test relates the first three automations to this resource, so confirm
    # that there are other related and non-related, automations in the test setup too
    old_owned = some_workspace_automations[0]
    new_owned = some_workspace_automations[1]
    related = some_workspace_automations[2]
    non_related = some_workspace_automations[3]

    assert old_owned.id != new_owned.id != related.id != non_related.id

    deployment_resource_id = f"prefect.deployment.{uuid4()}"

    for automation in [old_owned, new_owned, related]:
        await relate_automation_to_resource(
            session=automations_session,
            automation_id=automation.id,
            resource_id=deployment_resource_id,
            owned_by_resource=(automation in [old_owned, new_owned]),
        )

    now = now_fn("UTC")

    # Make sure the old owned automation is older than the horizon
    await automations_session.execute(
        sa.update(db.Automation)
        .where(db.Automation.id == old_owned.id)
        .values(created=now - timedelta(days=1))
    )

    # Make sure the new owned automation is newer than the horizon
    new_owned = some_workspace_automations[1]
    await automations_session.execute(
        sa.update(db.Automation)
        .where(db.Automation.id == new_owned.id)
        .values(created=now + timedelta(days=1))
    )

    await automations_session.commit()

    for automation in [old_owned, new_owned, related, non_related]:
        response = await client.get(
            f"{automations_url}/{automation.id}",
        )
        assert response.status_code == 200, response.content

    response = await client.delete(
        f"{automations_url}/owned-by/{deployment_resource_id}",
    )
    assert response.status_code == 202, response.content

    response = await client.get(
        f"{automations_url}/related-to/{deployment_resource_id}",
    )
    assert response.status_code == 200, response.content

    returned = parse_obj_as(List[Automation], response.json())
    assert {a.id for a in returned} == {related.id, new_owned.id}

    for automation in [old_owned, new_owned, related, non_related]:
        response = await client.get(
            f"{automations_url}/{automation.id}",
        )
        expected = 404 if automation == old_owned else 200
        assert response.status_code == expected, response.content


async def test_create_run_deployment_automation_with_job_variables_and_no_schema(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    run_vars = {"this": "that"}
    *_, run_deployment_with_no_schema = await create_objects_for_automation(
        session,
        base_job_template={},
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_no_schema.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)
    assert isinstance(created_automation.actions[0], actions.RunDeployment)
    assert created_automation.actions[0].job_variables == run_vars


async def test_create_run_deployment_automation_with_job_variables_that_match_schema(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    run_vars = {"this": "is a string"}
    *_, run_deployment_with_schema = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "thing_one": "{{ this }}",
            },
            "variables": {
                "properties": {
                    "this": {"title": "this_one", "default": "0", "type": "string"}
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_schema.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)
    assert isinstance(created_automation.actions[0], actions.RunDeployment)
    assert created_automation.actions[0].job_variables == run_vars


async def test_create_run_deployment_automation_with_job_variables_that_dont_match_schema(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    run_vars = {"this": 100}
    *_, run_deployment_with_bad_vars = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "thing_one": "{{ this }}",
            },
            "variables": {
                "properties": {
                    "this": {"title": "this_one", "default": "0", "type": "string"}
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_bad_vars.model_dump(mode="json"),
    )
    assert response.status_code == 422, response.content
    assert "Validation failed for field 'this'" in response.text


async def test_multiple_run_deployment_actions_with_job_variables_that_dont_match_schema(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    run_vars = {"this": 100}
    *_, run_deployment_with_bad_vars = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "thing_one": "{{ this }}",
            },
            "variables": {
                "properties": {
                    "this": {"title": "this_one", "default": "0", "type": "string"}
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    # Copy the same action
    for _ in range(3):
        run_deployment_with_bad_vars.actions.append(
            run_deployment_with_bad_vars.actions[0]
        )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_bad_vars.model_dump(mode="json"),
    )
    assert response.status_code == 422, response.content
    assert (
        "Error creating automation: Validation failed for field 'this'" in response.text
    )


async def test_updating_run_deployment_automation_with_bad_job_variables(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    run_vars = {"this": "that"}
    *_, run_deployment_with_str_schema = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "thing_one": "{{ this }}",
            },
            "variables": {
                "properties": {
                    "this": {"title": "this_one", "default": "0", "type": "string"}
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_str_schema.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    automation_id = response.json()["id"]
    as_core = AutomationCore(**response.json())
    update = AutomationUpdate(**as_core.model_dump())
    assert isinstance(update.actions[0], actions.RunDeployment)

    update.actions[0].job_variables = {"this": 100}

    response = await client.put(
        f"{automations_url}/{automation_id}",
        json=update.model_dump(mode="json"),
    )
    assert response.status_code == 422
    assert (
        "Error creating automation: Validation failed for field 'this'" in response.text
    )


async def test_create_run_deployment_automation_with_none_variable_value(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    """
    A regression test for broken JSON schema validation in #7555.
    """
    # The RunDeployment action will try to use a `None` value for this job var.
    # It should work because Pydantic schemas allow None values for optional
    # fields.
    run_vars = {"profile_name": None}
    *_, run_deployment_with_str_schema = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "name": "{{ profile_name }}",
            },
            "variables": {
                "properties": {
                    "profile_name": {
                        "title": "Profile Name",
                        "description": "The profile to use when creating your session.",
                        "type": "string",
                    },
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_str_schema.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    automation_id = response.json()["id"]
    response = await client.get(f"{automations_url}/{automation_id}")
    created_automation = Automation.model_validate_json(response.content)
    assert isinstance(created_automation.actions[0], actions.RunDeployment)
    assert created_automation.actions[0].job_variables == {"profile_name": None}


async def test_updating_run_deployment_automation_with_none_variable_value(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    """
    A regression test for broken JSON schema validation in #7555.
    """
    # The RunDeployment action will try to use a `None` value for this job var.
    # It should work because Pydantic schemas allow None values for optional
    # fields.
    run_vars = {"profile_name": "andrew"}
    *_, run_deployment_with_str_schema = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "name": "{{ profile_name }}",
            },
            "variables": {
                "properties": {
                    "profile_name": {
                        "title": "Profile Name",
                        "description": "The profile to use when creating your session.",
                        "type": "string",
                    },
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_str_schema.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    automation_id = response.json()["id"]
    as_core = AutomationCore(**response.json())
    update = AutomationUpdate(**as_core.model_dump())
    assert isinstance(update.actions[0], actions.RunDeployment)
    assert update.actions[0].job_variables == {"profile_name": "andrew"}

    update.actions[0].job_variables = {"profile_name": None}

    response = await client.put(
        f"{automations_url}/{automation_id}",
        json=update.model_dump(mode="json"),
    )
    assert response.status_code == 204

    response = await client.get(f"{automations_url}/{automation_id}")
    updated_automation = Automation.model_validate_json(response.content)
    assert isinstance(updated_automation.actions[0], actions.RunDeployment)
    assert updated_automation.actions[0].job_variables == {"profile_name": None}


async def test_updating_run_deployment_automation_with_valid_job_variables(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    run_vars = {"this": "that"}
    *_, run_deployment_with_str_schema = await create_objects_for_automation(
        session,
        base_job_template={
            "job_configuration": {
                "thing_one": "{{ this }}",
            },
            "variables": {
                "properties": {
                    "this": {"title": "this_one", "default": "0", "type": "string"}
                },
            },
        },
        run_deployment_job_variables=run_vars,
    )

    response = await client.post(
        f"{automations_url}/",
        json=run_deployment_with_str_schema.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    automation_id = response.json()["id"]
    as_core = AutomationCore(**response.json())
    update = AutomationUpdate(**as_core.model_dump())
    assert isinstance(update.actions[0], actions.RunDeployment)
    update.actions[0].job_variables = {"this": "something else!!"}

    response = await client.put(
        f"{automations_url}/{automation_id}",
        json=update.model_dump(mode="json"),
    )
    assert response.status_code == 204

    response = await client.get(f"{automations_url}/{automation_id}")
    updated_automation = Automation.model_validate_json(response.content)
    assert isinstance(updated_automation.actions[0], actions.RunDeployment)
    assert updated_automation.actions[0].job_variables == {"this": "something else!!"}


async def test_infrastructure_error_inside_create(
    client: AsyncClient,
    automations_url: str,
    session: AsyncSession,
) -> None:
    *_, run_deployment_with_str_schema = await create_objects_for_automation(
        session,
        base_job_template={},
        run_deployment_job_variables={"this": "that"},
    )

    with mock.patch(
        "prefect.server.api.automations.validate_job_variables_for_run_deployment_action",
        side_effect=ValidationError("Something is wrong"),
    ):
        response = await client.post(
            f"{automations_url}/",
            json=run_deployment_with_str_schema.model_dump(mode="json"),
        )
        assert response.status_code == 422, response.content
        assert "Error creating automation: Something is wrong" in response.text


async def test_create_automation_with_tags(
    client: AsyncClient,
    automations_url: str,
    automation_to_create: AutomationCreate,
) -> None:
    """Test creating an automation with tags"""
    automation_to_create.tags = ["test", "db", "critical"]

    response = await client.post(
        f"{automations_url}/",
        json=automation_to_create.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)
    assert created_automation.tags == ["test", "db", "critical"]


async def test_create_automation_with_empty_tags(
    client: AsyncClient,
    automations_url: str,
    automation_to_create: AutomationCreate,
) -> None:
    """Test creating an automation with empty tags list"""
    automation_to_create.tags = []

    response = await client.post(
        f"{automations_url}/",
        json=automation_to_create.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)
    assert created_automation.tags == []


async def test_create_automation_without_tags_defaults_to_empty(
    client: AsyncClient,
    automations_url: str,
    automation_to_create: AutomationCreate,
) -> None:
    """Test creating an automation without specifying tags defaults to empty list"""
    # Don't set tags - should default to empty list

    response = await client.post(
        f"{automations_url}/",
        json=automation_to_create.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.content

    created_automation = Automation.model_validate_json(response.content)
    assert created_automation.tags == []


async def test_update_automation_tags(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
) -> None:
    """Test updating an automation's tags"""
    update_data = existing_automation.model_dump(exclude={"id", "created", "updated"})
    update_data["tags"] = ["new", "updated", "tags"]
    automation_update = AutomationUpdate(**update_data)

    response = await client.put(
        f"{automations_url}/{existing_automation.id}",
        json=automation_update.model_dump(mode="json"),
    )
    assert response.status_code == 204, response.content

    # Verify the update
    response = await client.get(f"{automations_url}/{existing_automation.id}")
    assert response.status_code == 200, response.content

    updated_automation = Automation.model_validate_json(response.content)
    assert updated_automation.tags == ["new", "updated", "tags"]


async def test_patch_automation_does_not_affect_tags_when_not_specified(
    client: AsyncClient,
    automations_url: str,
    existing_automation: Automation,
) -> None:
    """Test that partial updates don't affect tags when not specified"""
    # First, set some tags on the automation
    update_data = existing_automation.model_dump(exclude={"id", "created", "updated"})
    update_data["tags"] = ["original", "tags"]
    automation_update = AutomationUpdate(**update_data)

    response = await client.put(
        f"{automations_url}/{existing_automation.id}",
        json=automation_update.model_dump(mode="json"),
    )
    assert response.status_code == 204, response.content

    # Now patch only the enabled field
    patch_data = AutomationPartialUpdate(enabled=False)
    response = await client.patch(
        f"{automations_url}/{existing_automation.id}",
        json=patch_data.model_dump(mode="json"),
    )
    assert response.status_code == 204, response.content

    # Verify tags are preserved
    response = await client.get(f"{automations_url}/{existing_automation.id}")
    assert response.status_code == 200, response.content

    updated_automation = Automation.model_validate_json(response.content)
    assert updated_automation.tags == ["original", "tags"]
    assert updated_automation.enabled is False
