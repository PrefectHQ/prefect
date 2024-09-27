import datetime
from typing import List
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa
from httpx._client import AsyncClient
from starlette import status

from prefect.client.schemas.responses import DeploymentResponse
from prefect.server import models, schemas
from prefect.server.database.orm_models import Flow
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import DeploymentCreate, DeploymentUpdate
from prefect.server.utilities.database import get_dialect
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
    PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS,
)


def assert_status_events(deployment_name: str, events: List[str]):
    deployment_specific_events = [
        event
        for item in AssertingEventsClient.all
        for event in item.events
        if event.resource.name == deployment_name
    ]

    assert len(events) == len(
        deployment_specific_events
    ), f"Expected events {events}, but found {deployment_specific_events}"

    for i, event in enumerate(events):
        assert event == deployment_specific_events[i].event


class TestCreateDeployment:
    async def test_create_oldstyle_deployment(
        self,
        session,
        hosted_api_client,
        flow,
        flow_function,
        storage_document_id,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            storage_document_id=storage_document_id,
        ).model_dump(mode="json")
        response = await hosted_api_client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "My Deployment"
        assert response.json()["version"] == "mint"
        assert response.json()["storage_document_id"] == str(storage_document_id)
        deployment_id = response.json()["id"]

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
        assert str(deployment.id) == deployment_id
        assert deployment.name == "My Deployment"
        assert deployment.tags == ["foo"]
        assert deployment.flow_id == flow.id
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.storage_document_id == storage_document_id

    async def test_create_deployment(
        self,
        session,
        hosted_api_client,
        flow,
        flow_function,
        storage_document_id,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables={"cpu": 24},
            storage_document_id=storage_document_id,
        ).model_dump(mode="json")
        response = await hosted_api_client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        deployment_response = DeploymentResponse(**response.json())
        assert deployment_response.name == "My Deployment"
        assert deployment_response.version == "mint"
        assert deployment_response.path == "/"
        assert deployment_response.entrypoint == "/file.py:flow"
        assert deployment_response.storage_document_id == storage_document_id
        assert deployment_response.job_variables == {"cpu": 24}
        assert deployment_response.status == "NOT_READY"

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_response.id
        )
        assert deployment.id == deployment_response.id
        assert deployment.name == "My Deployment"
        assert deployment.tags == ["foo"]
        assert deployment.flow_id == flow.id
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.storage_document_id == storage_document_id
        assert deployment.job_variables == {"cpu": 24}

    async def test_create_deployment_with_single_schedule(
        self,
        session,
        client,
        flow,
    ):
        schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )

        data = DeploymentCreate(  # type: ignore
            name="My Deployment",
            version="mint",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            schedules=[schemas.actions.DeploymentScheduleCreate(schedule=schedule)],
        ).model_dump(mode="json")
        response = await client.post(
            "/deployments/",
            json=data,
        )

        data = response.json()
        deployment_id = data["id"]

        assert response.status_code == 201
        assert data["name"] == "My Deployment"
        assert len(data["schedules"]) == 1
        assert (
            schemas.core.DeploymentSchedule(**data["schedules"][0]).schedule == schedule
        )

        schedules = await models.deployments.read_deployment_schedules(
            session=session,
            deployment_id=deployment_id,
        )

        assert len(schedules) == 1
        assert schedules[0] == schemas.core.DeploymentSchedule(**data["schedules"][0])

    async def test_create_deployment_with_multiple_schedules(
        self,
        client,
        flow,
    ):
        schedule1 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )
        schedule2 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=2)
        )

        data = DeploymentCreate(  # type: ignore
            name="My Deployment",
            version="mint",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule1,
                    active=True,
                ),
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule2,
                    active=False,
                ),
            ],
        ).model_dump(mode="json")
        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 201

        deployment_id = response.json()["id"]
        data = response.json()
        schedules = [schemas.core.DeploymentSchedule(**s) for s in data["schedules"]]

        assert len(schedules) == 2
        assert schedules == [
            schemas.core.DeploymentSchedule(
                schedule=schedule2,
                active=False,
                deployment_id=deployment_id,
            ),
            schemas.core.DeploymentSchedule(
                schedule=schedule1,
                active=True,
                deployment_id=deployment_id,
            ),
        ]

    async def test_create_deployment_with_multiple_schedules_populates_legacy_schedule(
        self,
        session,
        client,
        flow,
    ):
        schedule1 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )
        schedule2 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=2)
        )

        data = DeploymentCreate(  # type: ignore
            name="My Deployment",
            version="mint",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule1,
                    active=True,
                ),
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule2,
                    active=True,
                ),
            ],
        ).model_dump(mode="json")
        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 201

        deployment_id = response.json()["id"]

        # Just to make sure this test is deterministic, let's update one of the
        # schedules so that it's updated datetime is after the other schedule.
        first_schedule = schemas.core.DeploymentSchedule(
            **response.json()["schedules"][0]
        )

        await models.deployments.update_deployment_schedule(
            session=session,
            deployment_id=deployment_id,
            deployment_schedule_id=first_schedule.id,
            schedule=schemas.actions.DeploymentScheduleUpdate(active=False),
        )

        await session.commit()

        # Then we'll read the deployment again and ensure that the schedules
        # are returned in the correct order.

        response = await client.get(f"/deployments/{deployment_id}")
        assert response.status_code == 200

        data = response.json()
        schedules = [schemas.core.DeploymentSchedule(**s) for s in data["schedules"]]

        assert data["name"] == "My Deployment"

        assert len(schedules) == 2
        assert schedules[0].id == first_schedule.id

    async def test_default_work_queue_name_is_none(self, session, client, flow):
        data = DeploymentCreate(name="My Deployment", flow_id=flow.id).model_dump(
            mode="json"
        )
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["work_queue_name"] is None

    async def test_create_deployment_respects_flow_id_name_uniqueness(
        self,
        session,
        hosted_api_client,
        flow,
        storage_document_id,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            paused=True,
            storage_document_id=storage_document_id,
        ).model_dump(mode="json")
        response = await hosted_api_client.post("/deployments/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My Deployment"
        deployment_id = response.json()["id"]

        # post the same data
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            paused=True,
            storage_document_id=storage_document_id,
        ).model_dump(mode="json")
        response = await hosted_api_client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "My Deployment"
        assert response.json()["id"] == deployment_id
        assert response.json()["paused"]
        assert response.json()["storage_document_id"] == str(storage_document_id)

        # post different data, upsert should be respected
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            paused=False,  # CHANGED
            storage_document_id=storage_document_id,
        ).model_dump(mode="json")
        response = await hosted_api_client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "My Deployment"
        assert response.json()["id"] == deployment_id
        assert not response.json()["paused"]

    async def test_create_deployment_populates_and_returned_created(
        self,
        client,
        flow,
    ):
        now = pendulum.now(tz="UTC")

        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My Deployment"
        assert pendulum.parse(response.json()["created"]) >= now
        assert pendulum.parse(response.json()["updated"]) >= now

    async def test_creating_deployment_with_inactive_schedule_creates_no_runs(
        self, session, client, flow
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            "/deployments/",
            json=DeploymentCreate(
                name="My Deployment",
                flow_id=flow.id,
                schedules=[
                    schemas.actions.DeploymentScheduleCreate(
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(days=1),
                            anchor_date=pendulum.datetime(2020, 1, 1),
                        ),
                        active=False,
                    )
                ],
            ).model_dump(mode="json"),
        )

        n_runs = await models.flow_runs.count_flow_runs(
            session, flow_filter=schemas.filters.FlowFilter(id=dict(any_=[flow.id]))
        )
        assert n_runs == 0

    async def test_creating_deployment_with_no_schedule_creates_no_runs(
        self, session, client, flow
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            "/deployments/",
            json=DeploymentCreate(
                name="My Deployment",
                flow_id=flow.id,
                paused=False,
            ).model_dump(mode="json"),
        )

        n_runs = await models.flow_runs.count_flow_runs(
            session, flow_filter=schemas.filters.FlowFilter(id=dict(any_=[flow.id]))
        )
        assert n_runs == 0

    async def test_upserting_deployment_with_inactive_schedule_deletes_existing_auto_scheduled_runs(
        self, client, deployment, session
    ):
        # schedule runs
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()

        # create a run manually to ensure it isn't deleted
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC").add(days=1)
                ),
            ),
        )
        await session.commit()

        # upsert the deployment to be paused and have no schedules
        await client.post(
            "/deployments/",
            json=schemas.actions.DeploymentCreate(
                name=deployment.name,
                flow_id=deployment.flow_id,
                schedules=[
                    schemas.actions.DeploymentScheduleCreate(
                        schedule=deployment.schedules[0].schedule, active=False
                    )
                ],
                paused=True,
            ).model_dump(mode="json"),
        )

        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 1

    async def test_upserting_deployment_with_new_schedule_deletes_existing_auto_scheduled_runs(
        self,
        client,
        deployment,
        session,
        db,
    ):
        # schedule runs
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()

        # create a run manually to ensure it isn't deleted
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC").add(seconds=2)
                ),
            ),
        )
        await session.commit()

        # upsert the deployment a new schedule active
        await client.post(
            "/deployments/",
            json=schemas.actions.DeploymentCreate(
                name=deployment.name,
                flow_id=deployment.flow_id,
                schedules=[
                    schemas.actions.DeploymentScheduleCreate(
                        active=True,
                        schedule=schemas.schedules.IntervalSchedule(
                            interval=datetime.timedelta(seconds=1),
                            anchor_date=pendulum.datetime(2020, 1, 1),
                        ),
                    )
                ],
                paused=False,
            ).model_dump(mode="json"),
        )

        # auto-scheduled runs should be deleted
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 1

        # check that the maximum run is from the secondly schedule
        query = sa.select(sa.func.max(db.FlowRun.expected_start_time))
        result = await session.execute(query)
        assert result.scalar() < pendulum.now("UTC").add(seconds=100)

    async def test_create_deployment_throws_useful_error_on_missing_blocks(
        self,
        client,
        flow,
        storage_document_id,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            storage_document_id=uuid4(),
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            "Error creating deployment. Could not find storage block with id"
            in response.json()["detail"]
        ), "Error message identifies storage block could not be found."

    async def test_create_deployment_with_pool_and_queue(
        self,
        client,
        flow,
        session,
        work_pool,
        work_queue_1,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables={"cpu": 24},
            work_pool_name=work_pool.name,
            work_queue_name=work_queue_1.name,
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        deployment_response = DeploymentResponse(**response.json())
        assert deployment_response.name == "My Deployment"
        assert deployment_response.version == "mint"
        assert deployment_response.path == "/"
        assert deployment_response.entrypoint == "/file.py:flow"
        assert deployment_response.job_variables == {"cpu": 24}
        assert deployment_response.work_pool_name == work_pool.name
        assert deployment_response.work_queue_name == work_queue_1.name

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_response.id
        )
        assert deployment.id == deployment_response.id
        assert deployment.name == "My Deployment"
        assert deployment.tags == ["foo"]
        assert deployment.flow_id == flow.id
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.work_queue_id == work_queue_1.id

    async def test_create_deployment_with_only_work_pool(
        self,
        client,
        flow,
        session,
        work_pool,
    ):
        default_queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables={"cpu": 24},
            work_pool_name=work_pool.name,
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        deployment_response = DeploymentResponse(**response.json())
        assert deployment_response.name == "My Deployment"
        assert deployment_response.version == "mint"
        assert deployment_response.path == "/"
        assert deployment_response.entrypoint == "/file.py:flow"
        assert deployment_response.job_variables == {"cpu": 24}
        assert deployment_response.work_pool_name == work_pool.name
        assert deployment_response.work_queue_name == default_queue.name

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_response.id
        )

        assert deployment.id == deployment_response.id
        assert deployment.name == "My Deployment"
        assert deployment.tags == ["foo"]
        assert deployment.flow_id == flow.id
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.work_queue_id == work_pool.default_queue_id

    async def test_create_deployment_creates_work_queue(
        self,
        client,
        flow,
        session,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables={"cpu": 24},
            work_pool_name=work_pool.name,
            work_queue_name="new-queue",
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["work_pool_name"] == work_pool.name
        assert response.json()["work_queue_name"] == "new-queue"
        deployment_id = response.json()["id"]

        work_queue = await models.workers.read_work_queue_by_name(
            session=session, work_pool_name=work_pool.name, work_queue_name="new-queue"
        )
        assert work_queue is not None

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
        assert deployment.work_queue_id == work_queue.id

    @pytest.mark.parametrize(
        "template, overrides",
        [
            (  # test with no overrides
                {
                    "job_configuration": {"thing_one": "{{ var1 }}"},
                    "variables": {
                        "properties": {
                            "var1": {
                                "type": "string",
                            }
                        },
                        "required": ["var1"],
                    },
                },
                {},  # no overrides
            ),
            (  # test with incomplete overrides
                {
                    "job_configuration": {
                        "thing_one": "{{ var1 }}",
                        "thing_two": "{{ var2 }}",
                    },
                    "variables": {
                        "properties": {
                            "var1": {
                                "type": "string",
                            },
                            "var2": {
                                "type": "string",
                            },
                        },
                        "required": ["var1", "var2"],
                    },
                },
                {"var2": "hello"},  # wrong override
            ),
        ],
    )
    async def test_create_deployment_ignores_required_fields(
        self,
        client,
        flow,
        session,
        template,
        overrides,
    ):
        """
        Test that creating a deployment does not require required fields to be overridden
        as job variables. We don't know the full set of overrides until a flow run is
        running because the flow run may have overridden required fields.
        """
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name="Test Work Pool", base_job_template=template
            ),
        )
        await session.commit()

        await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )

        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables=overrides,
            work_pool_name=work_pool.name,
        ).model_dump(mode="json")

        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "template, overrides",
        [
            (  # test with no overrides, no required
                {
                    "job_configuration": {"thing_one": "{{ var1 }}"},
                    "variables": {
                        "properties": {"var1": {"type": "string", "default": "hello"}},
                        "required": [],
                    },
                },
                {},  # no overrides
            ),
            (  # test with override
                {
                    "job_configuration": {
                        "thing_one": "{{ var1 }}",
                    },
                    "variables": {
                        "properties": {
                            "var1": {
                                "type": "string",
                            },
                        },
                        "required": ["var1"],
                    },
                },
                {"var1": "hello"},  # required override
            ),
            (  # test with override and multiple variables
                {
                    "job_configuration": {
                        "thing_one": "{{ var1 }}",
                        "thing_two": "{{ var2 }}",
                    },
                    "variables": {
                        "properties": {
                            "var1": {
                                "type": "string",
                            },
                            "var2": {"type": "string", "default": "world"},
                        },
                        "required": ["var1"],
                    },
                },
                {"var1": "hello"},  # required override
            ),
        ],
    )
    async def test_create_deployment_with_job_variables_succeeds(
        self,
        client,
        flow,
        session,
        template,
        overrides,
    ):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name="Test Work Pool", base_job_template=template
            ),
        )
        await session.commit()

        await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )

        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables=overrides,
            work_pool_name=work_pool.name,
        ).model_dump(mode="json")

        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201

    async def test_create_deployment_can_create_work_queue(
        self,
        client,
        flow,
        session,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables={"cpu": 24},
            work_pool_name=work_pool.name,
            work_queue_name="new-work-pool-queue",
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        assert response.json()["work_queue_name"] == "new-work-pool-queue"
        deployment_id = response.json()["id"]

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )

        work_queue = await models.workers.read_work_queue_by_name(
            session=session,
            work_pool_name=work_pool.name,
            work_queue_name="new-work-pool-queue",
        )

        assert deployment.work_queue_id == work_queue.id

    async def test_create_deployment_returns_404_for_non_existent_work_pool(
        self,
        client,
        flow,
        session,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            job_variables={"cpu": 24},
            work_pool_name="imaginary-work-pool",
            work_queue_name="default",
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == 'Work pool "imaginary-work-pool" not found.'

    async def test_create_deployment_rejects_invalid_parameter_schemas(
        self,
        client,
        flow,
        work_pool,
    ):
        data = dict(
            name="My Deployment",
            flow_id=str(flow.id),
            work_pool_name=work_pool.name,
            enforce_parameter_schema=True,
            parameter_openapi_schema={
                "type": "object",
                "properties": {"foo": {"type": "blork"}},
            },
            parameters={"foo": 1},
        )

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 422
        assert "'blork' is not valid under any of the given schemas" in response.text

    async def test_create_deployment_does_not_reject_invalid_parameter_schemas_by_default(
        self,
        client,
        flow,
        work_pool,
    ):
        data = dict(
            name="My Deployment",
            flow_id=str(flow.id),
            work_pool_name=work_pool.name,
            parameter_openapi_schema={
                "type": "object",
                "properties": {"foo": {"type": "blork"}},
            },
            parameters={"foo": 1},
        )

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 201

    async def test_create_deployment_enforces_parameter_schema(
        self,
        client,
        flow,
        work_pool,
    ):
        data = dict(
            name="My Deployment",
            flow_id=str(flow.id),
            work_pool_name=work_pool.name,
            enforce_parameter_schema=True,
            parameter_openapi_schema={
                "type": "object",
                "properties": {"foo": {"type": "string"}},
            },
            parameters={"foo": 1},
        )

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 422
        assert (
            "Validation failed for field 'foo'. Failure reason: 1 is not of type"
            " 'string'" in response.text
        )

    async def test_create_deployment_enforces_schema_by_default(
        self,
        client,
        flow,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            work_pool_name=work_pool.name,
            parameter_openapi_schema={
                "type": "object",
                "properties": {"foo": {"type": "string"}},
            },
            parameters={"foo": 1},
        ).model_dump(mode="json")

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 422

    async def test_create_deployment_parameter_enforcement_allows_partial_parameters(
        self,
        client,
        flow,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            work_pool_name=work_pool.name,
            enforce_parameter_schema=True,
            parameter_openapi_schema={
                "type": "object",
                "required": ["person"],
                "properties": {
                    "name": {
                        "type": "string",
                        "default": "world",
                        "position": 1,
                    },
                    "person": {
                        "allOf": [{"$ref": "#/definitions/Person"}],
                        "position": 0,
                    },
                },
                "definitions": {
                    "Person": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "greeting": {
                                "type": "string",
                                "default": "Hello",
                            },
                        },
                    }
                },
            },
            parameters={"person": {"greeting": "sup"}},
        ).model_dump(mode="json")

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 201

    async def test_can_pause_deployment_by_upserting_paused(
        self,
        client,
        deployment,
    ):
        assert deployment.paused is False

        data = DeploymentCreate(  # type: ignore
            name=deployment.name,
            flow_id=deployment.flow_id,
            paused=True,
        ).model_dump(mode="json")

        response = await client.post("/deployments/", json=data)
        assert response.status_code == 200
        assert response.json()["paused"] is True

    async def test_create_deployment_with_concurrency_limit(
        self,
        client: AsyncClient,
        flow: Flow,
    ):
        response = await client.post(
            "/deployments/",
            json=dict(
                name="My Deployment",
                flow_id=str(flow.id),
                concurrency_limit=3,
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED

        json_response = response.json()
        assert (
            json_response["concurrency_limit"] is None
        ), "Deprecated int-only field should be None for backwards-compatibility"

        global_concurrency_limit = json_response.get("global_concurrency_limit")
        assert global_concurrency_limit is not None
        assert global_concurrency_limit.get("limit") == 3
        assert global_concurrency_limit.get("active") is True
        assert (
            global_concurrency_limit.get("name") == f"deployment:{json_response['id']}"
        )

    async def test_create_deployment_retains_concurrency_limit_on_upsert_if_not_specified(
        self,
        client: AsyncClient,
        flow: Flow,
    ):
        """Ensure that old prefect clients that don't know about concurrency limits can still use them server-side.
        This means that if a deployment has a concurrency limit (possibly created through the Cloud UI), but the client
        is an old version that doesn't know about concurrency limits, then when using `prefect deploy`, the old client
        should not remove the concurrency limit from the existing deployment.
        """
        # Create deployment with a concurrency limit
        data = {
            "name": "Deployment with concurrency limit",
            "flow_id": str(flow.id),
            "concurrency_limit": 3,
        }
        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201
        global_concurrency_limit = response.json().get("global_concurrency_limit")
        assert global_concurrency_limit is not None
        assert global_concurrency_limit.get("limit") == 3

        # Upsert the deployment without specifying a concurrency limit
        updated_data = data.copy()
        updated_data.pop("concurrency_limit", None)
        updated_data["version"] = "1.0.1"
        response = await client.post("/deployments/", json=updated_data)

        # Ensure that the concurrency limit is still present
        assert response.status_code == 200
        updated_global_concurrency_limit = response.json().get(
            "global_concurrency_limit"
        )
        assert updated_global_concurrency_limit is not None
        assert updated_global_concurrency_limit.get("limit") == 3

    async def test_upsert_deployment_can_remove_schedules(
        self,
        client: AsyncClient,
        flow: Flow,
    ):
        # Create deployment with a schedule
        data = DeploymentCreate(  # type: ignore
            name="Deployment with schedules",
            flow_id=flow.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(  # type: ignore [call-arg]
                    active=True,
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                ),
            ],
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201
        schedules_in_response = response.json().get("schedules")
        assert schedules_in_response

        # Upsert the deployment without schedules
        updated_data = data.copy()
        updated_data["schedules"] = []
        updated_data["version"] = "1.0.1"
        response = await client.post("/deployments/", json=updated_data)

        # Ensure that the schedules are removed
        assert response.status_code == 200
        assert response.json().get("schedules") == []


class TestReadDeployment:
    async def test_read_deployment(
        self,
        client,
        deployment,
    ):
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(deployment.id)
        assert response.json()["name"] == deployment.name
        assert response.json()["flow_id"] == str(deployment.flow_id)

    async def test_read_deployment_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/deployments/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_deployment_with_concurrency_limit(
        self, session, client, deployment
    ):
        update = DeploymentUpdate(concurrency_limit=4)
        await models.deployments.update_deployment(session, deployment.id, update)
        await session.commit()

        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == status.HTTP_200_OK

        json_response = response.json()
        assert (
            json_response["concurrency_limit"] is None
        ), "Deprecated int-only field should be None for backwards-compatibility"

        global_concurrency_limit = json_response.get("global_concurrency_limit")
        assert global_concurrency_limit is not None
        assert global_concurrency_limit.get("limit") == update.concurrency_limit
        assert global_concurrency_limit.get("active") is True
        assert (
            global_concurrency_limit.get("name") == f"deployment:{json_response['id']}"
        )


class TestReadDeploymentByName:
    async def test_read_deployment_by_name(self, client, flow, deployment):
        response = await client.get(f"/deployments/name/{flow.name}/{deployment.name}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(deployment.id)
        assert response.json()["name"] == deployment.name
        assert response.json()["flow_id"] == str(deployment.flow_id)

    async def test_read_deployment_by_name_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/deployments/name/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_deployment_by_name_returns_404_if_just_given_flow_name(
        self, client, flow
    ):
        response = await client.get(f"/deployments/name/{flow.name}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_deployment_by_name_returns_404_if_just_given_deployment_name(
        self, client, deployment
    ):
        response = await client.get(f"/deployments/name/{deployment.name}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        "name",
        [
            "my deployment",
            "my:deployment",
            r"my\deployment",
            "my👍deployment",
            "my|deployment",
        ],
    )
    async def test_read_deployment_by_name_with_nonstandard_characters(
        self,
        client,
        name,
        flow,
    ):
        response = await client.post(
            "/deployments/",
            json=dict(
                name=name,
                flow_id=str(flow.id),
            ),
        )
        deployment_id = response.json()["id"]

        response = await client.get(f"/deployments/name/{flow.name}/{name}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == deployment_id

    @pytest.mark.parametrize(
        "name",
        [
            "my/deployment",
            "my%deployment",
        ],
    )
    async def test_read_deployment_by_name_with_invalid_characters_fails(
        self, client, name, flow
    ):
        response = await client.get(f"/deployments/name/{flow.name}/{name}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadDeployments:
    @pytest.fixture
    async def deployment_id_1(self):
        return uuid4()

    @pytest.fixture
    async def deployment_id_2(self):
        return uuid4()

    @pytest.fixture
    async def deployments(
        self,
        session,
        deployment_id_1,
        deployment_id_2,
        flow,
        flow_function,
    ):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_1,
                name="My Deployment X",
                flow_id=flow.id,
                paused=False,
            ),
        )

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_2,
                name="My Deployment Y",
                flow_id=flow.id,
                paused=True,
            ),
        )
        await session.commit()

    async def test_read_deployments(self, deployments, client):
        response = await client.post("/deployments/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

        assert response.json()[0]["status"] == "NOT_READY"

    async def test_read_deployments_applies_filter(
        self, deployments, deployment_id_1, deployment_id_2, flow, client
    ):
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment X"])
            ).model_dump(mode="json")
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()} == {
            str(deployment_id_1)
        }

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment 123"])
            ).model_dump(mode="json")
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

        deployment_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow.name])
            ).model_dump(mode="json")
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()} == {
            str(deployment_id_1),
            str(deployment_id_2),
        }

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment X"])
            ).model_dump(mode="json"),
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["not a flow name"])
            ).model_dump(mode="json"),
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                flow_or_deployment_name=schemas.filters.DeploymentOrFlowNameFilter(
                    like_=flow.name
                )
            ).model_dump(mode="json")
        )

        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()} == {
            str(deployment_id_1),
            str(deployment_id_2),
        }

    async def test_read_deployments_applies_limit(self, deployments, client):
        response = await client.post("/deployments/filter", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_deployments_offset(self, deployments, client, session):
        response = await client.post("/deployments/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        # sorted by name by default
        assert response.json()[0]["name"] == "My Deployment Y"

    async def test_read_deployments_sort(self, deployments, client):
        response = await client.post(
            "/deployments/filter",
            json=dict(sort=schemas.sorting.DeploymentSort.NAME_ASC),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["name"] == "My Deployment X"

        response_desc = await client.post(
            "/deployments/filter",
            json=dict(sort=schemas.sorting.DeploymentSort.NAME_DESC),
        )
        assert response_desc.status_code == status.HTTP_200_OK
        assert response_desc.json()[0]["name"] == "My Deployment Y"

    async def test_read_deployments_returns_empty_list(self, client):
        response = await client.post("/deployments/filter")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestPaginateDeployments:
    @pytest.fixture
    async def deployment_id_1(self):
        return uuid4()

    @pytest.fixture
    async def deployment_id_2(self):
        return uuid4()

    @pytest.fixture
    async def deployments(
        self,
        session,
        deployment_id_1,
        deployment_id_2,
        flow,
        flow_function,
    ):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_1,
                name="My Deployment X",
                flow_id=flow.id,
                paused=False,
            ),
        )

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_2,
                name="My Deployment Y",
                flow_id=flow.id,
                paused=True,
            ),
        )
        await session.commit()

    async def test_paginate_deployments(self, deployments, client):
        response = await client.post("/deployments/paginate")
        assert response.status_code == status.HTTP_200_OK

        assert response.json()["page"] == 1
        assert response.json()["pages"] == 1
        assert response.json()["count"] == 2
        assert len(response.json()["results"]) == 2

        assert response.json()["results"][0]["status"] == "NOT_READY"

    async def test_paginate_deployments_applies_filter(
        self, deployments, deployment_id_1, deployment_id_2, flow, client
    ):
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment X"])
            ).model_dump(mode="json")
        )
        response = await client.post("/deployments/paginate", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()["results"]} == {
            str(deployment_id_1)
        }

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment 123"])
            ).model_dump(mode="json")
        )
        response = await client.post("/deployments/paginate", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 0

        deployment_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow.name])
            ).model_dump(mode="json")
        )
        response = await client.post("/deployments/paginate", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()["results"]} == {
            str(deployment_id_1),
            str(deployment_id_2),
        }

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment X"])
            ).model_dump(mode="json"),
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["not a flow name"])
            ).model_dump(mode="json"),
        )
        response = await client.post("/deployments/paginate", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 0

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                flow_or_deployment_name=schemas.filters.DeploymentOrFlowNameFilter(
                    like_=flow.name
                )
            ).model_dump(mode="json")
        )

        response = await client.post("/deployments/paginate", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()["results"]} == {
            str(deployment_id_1),
            str(deployment_id_2),
        }

    async def test_paginate_deployments_applies_limit(self, deployments, client):
        response = await client.post("/deployments/paginate", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 1

    async def test_paginate_deployments_page(self, deployments, client, session):
        response = await client.post(
            "/deployments/paginate", json=dict(page=2, limit=1)
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 1
        # sorted by name by default
        assert response.json()["results"][0]["name"] == "My Deployment Y"

    async def test_paginate_deployments_sort(self, deployments, client):
        response = await client.post(
            "/deployments/paginate",
            json=dict(sort=schemas.sorting.DeploymentSort.NAME_ASC),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"][0]["name"] == "My Deployment X"

        response_desc = await client.post(
            "/deployments/paginate",
            json=dict(sort=schemas.sorting.DeploymentSort.NAME_DESC),
        )
        assert response_desc.status_code == status.HTTP_200_OK
        assert response_desc.json()["results"][0]["name"] == "My Deployment Y"

    async def test_paginate_deployments_returns_empty_list(self, client):
        response = await client.post("/deployments/paginate")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == []


class TestUpdateDeployment:
    async def test_update_deployment_enforces_parameter_schema(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        response = await client.patch(
            f"/deployments/{deployment_with_parameter_schema.id}",
            json={"parameters": {"x": 1}},
        )
        assert response.status_code == 409
        assert (
            "Validation failed for field 'x'. Failure reason: 1 is not of type 'string'"
            in response.text
        )

    async def test_update_deployment_does_not_enforce_parameter_schema_by_default(
        self,
        deployment,
        client,
    ):
        response = await client.patch(
            f"/deployments/{deployment.id}",
            json={"parameters": {"x": 1}},
        )
        assert response.status_code == 204

    async def test_update_deployment_can_toggle_parameter_schema_validation(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        # Turn off parameter schema enforcement
        response = await client.patch(
            f"/deployments/{deployment_with_parameter_schema.id}",
            json={"parameters": {"x": 1}, "enforce_parameter_schema": False},
        )
        assert response.status_code == 204

        response = await client.get(
            f"/deployments/{deployment_with_parameter_schema.id}"
        )
        assert response.json()["parameters"] == {"x": 1}
        assert response.json()["enforce_parameter_schema"] is False

        # Turn on parameter schema enforcement, but parameters are still invalid
        response = await client.patch(
            f"/deployments/{deployment_with_parameter_schema.id}",
            json={"enforce_parameter_schema": True},
        )

        assert response.status_code == 409

        # Turn on parameter schema enforcement, and parameters are now valid
        response = await client.patch(
            f"/deployments/{deployment_with_parameter_schema.id}",
            json={"parameters": {"x": "y"}, "enforce_parameter_schema": True},
        )
        assert response.status_code == 204

        response = await client.get(
            f"/deployments/{deployment_with_parameter_schema.id}"
        )
        assert response.json()["parameters"] == {"x": "y"}
        assert response.json()["enforce_parameter_schema"] is True

    async def test_update_deployment_parameter_enforcement_allows_partial_parameters(
        self,
        client,
        flow,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            work_pool_name=work_pool.name,
            enforce_parameter_schema=True,
            parameter_openapi_schema={
                "type": "object",
                "required": ["person"],
                "properties": {
                    "name": {
                        "type": "string",
                        "default": "world",
                        "position": 1,
                    },
                    "person": {
                        "allOf": [{"$ref": "#/definitions/Person"}],
                        "position": 0,
                    },
                },
                "definitions": {
                    "Person": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "greeting": {
                                "type": "string",
                                "default": "Hello",
                            },
                        },
                    }
                },
            },
        ).model_dump(mode="json")

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 201

        deployment_id = response.json()["id"]

        response = await client.patch(
            f"/deployments/{deployment_id}",
            json={"parameters": {"person": {"greeting": "*head nod*"}}},
        )

        assert response.status_code == 204

    async def test_update_deployment_hydrates_json_kind_parameters(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        response = await client.patch(
            f"/deployments/{deployment_with_parameter_schema.id}",
            json={
                "parameters": {
                    "x": {"__prefect_kind": "json", "value": '"str_of_json"'}
                }
            },
        )
        assert response.status_code == 204

        response = await client.get(
            f"/deployments/{deployment_with_parameter_schema.id}"
        )
        assert response.json()["parameters"] == {"x": "str_of_json"}

    async def test_update_deployment_hydrates_jinja_kind_parameters(
        self,
        deployment,
        client,
    ):
        response = await client.patch(
            f"/deployments/{deployment.id}",
            json={
                "parameters": {
                    "x": {"__prefect_kind": "jinja", "template": "{{ 1 + 2 }}"}
                }
            },
        )
        assert response.status_code == 204

        response = await client.get(f"/deployments/{deployment.id}")
        assert response.json()["parameters"] == {"x": "3"}

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
    async def test_update_deployment_hydrates_workspace_variable_kind_parameters(
        self,
        deployment,
        client,
        session,
        value,
    ):
        await models.variables.create_variable(
            session,
            schemas.actions.VariableCreate(name="my_variable", value=value),
        )
        await session.commit()

        response = await client.patch(
            f"/deployments/{deployment.id}",
            json={
                "parameters": {
                    "x": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my_variable",
                    }
                }
            },
        )
        assert response.status_code == 204, str(response.content)

        response = await client.get(f"/deployments/{deployment.id}")
        assert response.json()["parameters"] == {"x": value}

    async def test_update_deployment_can_remove_schedules(
        self,
        client,
        deployment,
        session,
    ):
        update_data = DeploymentUpdate(
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1)
                    ),
                    active=True,
                )
            ]
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(f"/deployments/{deployment.id}", json=update_data)
        assert response.status_code == 204

        schedules = await models.deployments.read_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
        )
        assert len(schedules) == 1
        assert isinstance(schedules[0].schedule, schemas.schedules.IntervalSchedule)
        assert schedules[0].schedule.interval == datetime.timedelta(days=1)

        # Now remove the schedule.
        update_data = DeploymentUpdate(schedules=[]).model_dump(
            mode="json", exclude_unset=True
        )

        response = await client.patch(f"/deployments/{deployment.id}", json=update_data)
        assert response.status_code == 204

        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == 200
        assert response.json()["schedules"] == []

    async def test_update_deployment_with_multiple_schedules(
        self, session, client, flow, simple_parameter_schema
    ):
        schedule1 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )
        schedule2 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=2)
        )

        data = DeploymentCreate(  # type: ignore
            name="My Deployment",
            version="mint",
            flow_id=flow.id,
            tags=["foo"],
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule1,
                    active=True,
                ),
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule2,
                    active=False,
                ),
            ],
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
        ).model_dump(mode="json")
        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201, response.json()

        deployment_id = response.json()["id"]
        original_schedule_ids = [
            schedule["id"] for schedule in response.json()["schedules"]
        ]

        # When we receive a PATCH request with schedules, we should replace the
        # existing schedules with the newly created ones.

        schedule3 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=3)
        )
        schedule4 = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=7)
        )

        update_data = DeploymentUpdate(
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule3,
                    active=True,
                ),
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schedule4,
                    active=False,
                ),
            ],
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(f"/deployments/{deployment_id}", json=update_data)
        assert response.status_code == 204, response.json()

        response = await client.get(
            f"/deployments/{deployment_id}",
        )

        schedules = [
            schemas.core.DeploymentSchedule(**s) for s in response.json()["schedules"]
        ]

        assert len(schedules) == 2
        assert [schedule.id for schedule in schedules] != original_schedule_ids

        assert isinstance(schedules[0].schedule, schemas.schedules.IntervalSchedule)
        assert schedules[0].schedule.interval == schedule4.interval
        assert schedules[0].active is False

        assert isinstance(schedules[1].schedule, schemas.schedules.IntervalSchedule)
        assert schedules[1].schedule.interval == schedule3.interval
        assert schedules[1].active is True

    async def test_can_pause_deployment_by_updating_paused(
        self,
        client,
        deployment,
        session,
    ):
        assert deployment.paused is False

        response = await client.patch(
            f"/deployments/{deployment.id}", json={"paused": True}
        )
        assert response.status_code == 204

        await session.refresh(deployment)

        assert deployment
        assert deployment.paused is True

    async def test_updating_paused_does_not_change_schedule(
        self,
        client,
        deployment,
        session,
    ):
        # This is a regression test for a bug where pausing a deployment would
        # copy the schedule from the existing deployment to the new one, even
        # if the schedule was not provided in the request.
        # https://github.com/PrefectHQ/nebula/issues/6994

        legacy_schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )
        response = await client.patch(
            f"/deployments/{deployment.id}",
            json={
                "schedules": [
                    {
                        "schedule": legacy_schedule.model_dump(mode="json"),
                        "active": True,
                    }
                ]
            },
        )
        assert response.status_code == 204

        await session.refresh(deployment)

        new_schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(hours=1)
        )

        assert deployment.paused is False
        assert len(deployment.schedules) > 0
        assert deployment.schedules[0].schedule.interval != new_schedule.interval

        await models.deployments.delete_schedules_for_deployment(
            session=session, deployment_id=deployment.id
        )
        await models.deployments.create_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(  # type: ignore [call-arg]
                    active=True, schedule=new_schedule
                )
            ],
        )

        await session.commit()

        response = await client.patch(
            f"/deployments/{deployment.id}", json={"paused": True}
        )
        assert response.status_code == 204

        schedules = await models.deployments.read_deployment_schedules(
            session=session, deployment_id=deployment.id
        )

        assert len(schedules) == 1
        assert isinstance(schedules[0].schedule, schemas.schedules.IntervalSchedule)
        assert schedules[0].schedule.interval == new_schedule.interval
        assert schedules[0].active is True

    async def test_updating_deployment_with_concurrency_limit(
        self,
        client,
        deployment,
        session,
    ):
        assert deployment.global_concurrency_limit is None

        response = await client.patch(
            f"/deployments/{deployment.id}", json={"concurrency_limit": 1}
        )
        assert response.status_code == 204

        await session.refresh(deployment)
        assert deployment
        assert deployment._concurrency_limit == 1
        assert deployment.global_concurrency_limit.limit == 1


class TestGetScheduledFlowRuns:
    @pytest.fixture
    async def flows(self, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1"),
        )
        flow_2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-2"),
        )
        await session.commit()
        return flow_1, flow_2

    @pytest.fixture(autouse=True)
    async def deployments(
        self,
        session,
        flows,
    ):
        flow_1, flow_2 = flows
        deployment_1 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment X",
                flow_id=flow_1.id,
            ),
        )
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment Y",
                flow_id=flow_2.id,
            ),
        )
        await session.commit()
        return deployment_1, deployment_2

    @pytest.fixture(autouse=True)
    async def flow_runs(
        self,
        session,
        deployments,
    ):
        deployment_1, deployment_2 = deployments
        # flow run 1 is in a SCHEDULED state 5 minutes ago
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment_1.flow_id,
                deployment_id=deployment_1.id,
                flow_version="0.1",
                state=schemas.states.State(
                    type=schemas.states.StateType.SCHEDULED,
                    timestamp=pendulum.now("UTC").subtract(minutes=5),
                    state_details=dict(
                        scheduled_time=pendulum.now("UTC").subtract(minutes=5)
                    ),
                ),
            ),
        )

        # flow run 2 is in a SCHEDULED state 1 minute ago for deployment 1
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment_1.flow_id,
                deployment_id=deployment_1.id,
                flow_version="0.1",
                tags=["tb12", "goat"],
                state=schemas.states.State(
                    type=schemas.states.StateType.SCHEDULED,
                    timestamp=pendulum.now("UTC").subtract(minutes=1),
                    state_details=dict(
                        scheduled_time=pendulum.now("UTC").subtract(minutes=1)
                    ),
                ),
            ),
        )
        # flow run 3 is in a SCHEDULED state 1 minute ago for deployment 2
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment_2.flow_id,
                deployment_id=deployment_2.id,
                flow_version="0.1",
                tags=["tb12", "goat"],
                state=schemas.states.State(
                    type=schemas.states.StateType.SCHEDULED,
                    timestamp=pendulum.now("UTC").subtract(minutes=1),
                    state_details=dict(
                        scheduled_time=pendulum.now("UTC").subtract(minutes=1)
                    ),
                ),
            ),
        )
        await session.commit()
        return flow_run_1, flow_run_2, flow_run_3

    async def test_get_scheduled_runs_for_a_deployment(
        self,
        client,
        deployments,
        flow_runs,
    ):
        deployment_1, _deployment_2 = deployments
        response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(deployment_ids=[str(deployment_1.id)]),
        )
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {
            str(flow_run.id) for flow_run in flow_runs[:2]
        }

        assert_status_events(deployment_1.name, ["prefect.deployment.ready"])

    async def test_get_scheduled_runs_for_multiple_deployments(
        self,
        client,
        deployments,
        flow_runs,
    ):
        deployment_1, deployment_2 = deployments
        response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(deployment_ids=[str(deployment_1.id), str(deployment_2.id)]),
        )
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {
            str(flow_run.id) for flow_run in flow_runs
        }

        assert_status_events(deployment_1.name, ["prefect.deployment.ready"])
        assert_status_events(deployment_2.name, ["prefect.deployment.ready"])

    async def test_get_scheduled_runs_respects_limit(
        self,
        client,
        flow_runs,
        deployments,
    ):
        deployment_1, _deployment_2 = deployments
        response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(deployment_ids=[str(deployment_1.id)], limit=1),
        )
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {str(flow_runs[0].id)}

        # limit should still be constrained by Orion settings though
        response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(limit=9001),
        )
        assert response.status_code == 422

    async def test_get_scheduled_runs_respects_scheduled_before(
        self,
        client,
        flow_runs,
        deployments,
    ):
        deployment_1, _deployment_2 = deployments
        # picks up one of the runs for the first deployment, but not the other
        response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(
                deployment_ids=[str(deployment_1.id)],
                scheduled_before=str(pendulum.now("UTC").subtract(minutes=2)),
            ),
        )
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {str(flow_runs[0].id)}

    async def test_get_scheduled_runs_sort_order(
        self,
        client,
        flow_runs,
        deployments,
    ):
        """Should sort by next scheduled start time ascending"""
        deployment_1, deployment_2 = deployments
        response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(deployment_ids=[str(deployment_1.id), str(deployment_2.id)]),
        )
        assert response.status_code == 200
        assert [res["id"] for res in response.json()] == [
            str(flow_run.id) for flow_run in flow_runs[:3]
        ]

    async def test_get_scheduled_flow_runs_updates_last_polled_time_and_status(
        self,
        client,
        flow_runs,
        deployments,
    ):
        deployment_1, deployment_2 = deployments

        response1 = await client.get(f"/deployments/{deployment_1.id}")
        assert response1.status_code == 200
        assert response1.json()["last_polled"] is None
        assert response1.json()["status"] == "NOT_READY"

        response2 = await client.get(f"/deployments/{deployment_2.id}")
        assert response2.status_code == 200
        assert response2.json()["last_polled"] is None
        assert response2.json()["status"] == "NOT_READY"

        updated_response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(deployment_ids=[str(deployment_1.id)]),
        )
        assert updated_response.status_code == 200

        updated_response_deployment_1 = await client.get(
            f"/deployments/{deployment_1.id}"
        )
        assert updated_response_deployment_1.status_code == 200

        assert (
            updated_response_deployment_1.json()["last_polled"]
            > pendulum.now("UTC").subtract(minutes=1).isoformat()
        )
        assert updated_response_deployment_1.json()["status"] == "READY"

        same_response_deployment_2 = await client.get(f"/deployments/{deployment_2.id}")
        assert same_response_deployment_2.status_code == 200
        assert same_response_deployment_2.json()["last_polled"] is None
        assert same_response_deployment_2.json()["status"] == "NOT_READY"

    async def test_get_scheduled_flow_runs_updates_last_polled_time_and_status_multiple_deployments(
        self,
        client,
        flow_runs,
        deployments,
    ):
        deployment_1, deployment_2 = deployments

        response_1 = await client.get(f"/deployments/{deployment_1.id}")
        assert response_1.status_code == 200
        assert response_1.json()["last_polled"] is None
        assert response_1.json()["status"] == "NOT_READY"

        response_2 = await client.get(f"/deployments/{deployment_2.id}")
        assert response_2.status_code == 200
        assert response_2.json()["last_polled"] is None
        assert response_2.json()["status"] == "NOT_READY"

        updated_response = await client.post(
            "/deployments/get_scheduled_flow_runs",
            json=dict(deployment_ids=[str(deployment_1.id), str(deployment_2.id)]),
        )
        assert updated_response.status_code == 200

        updated_response_1 = await client.get(f"/deployments/{deployment_1.id}")
        assert updated_response_1.status_code == 200
        assert (
            updated_response_1.json()["last_polled"]
            > pendulum.now("UTC").subtract(minutes=1).isoformat()
        )
        assert updated_response_1.json()["status"] == "READY"

        updated_response_2 = await client.get(f"/deployments/{deployment_2.id}")
        assert updated_response_2.status_code == 200
        assert (
            updated_response_2.json()["last_polled"]
            > pendulum.now("UTC").subtract(minutes=1).isoformat()
        )
        assert updated_response_2.json()["status"] == "READY"


class TestDeleteDeployment:
    async def test_delete_deployment(self, session, client, deployment):
        # schedule both an autoscheduled and manually scheduled flow run
        # for this deployment id, these should be deleted when the deployment is deleted
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="1.0",
                auto_scheduled=False,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC"),
                    message="Flow run scheduled",
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="1.0",
                auto_scheduled=True,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC"),
                    message="Flow run scheduled",
                ),
            ),
        )
        await session.commit()

        # delete the deployment
        response = await client.delete(f"/deployments/{deployment.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # make sure it's deleted
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # make sure scheduled flow runs are deleted
        n_runs = await models.flow_runs.count_flow_runs(
            session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id={"any_": [flow_run_1.id, flow_run_2.id]}
            ),
        )
        assert n_runs == 0

    async def test_delete_deployment_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/deployments/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPauseAndResumeDeployment:
    async def test_pause_deployment(self, client, deployment, session):
        assert deployment.paused is False
        response = await client.post(f"/deployments/{deployment.id}/pause_deployment")
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.paused is True

    async def test_pause_deployment_multiple_times(self, client, deployment, session):
        assert deployment.paused is False
        await client.post(f"/deployments/{deployment.id}/pause_deployment")
        response = await client.post(f"/deployments/{deployment.id}/pause_deployment")
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.paused is True

    async def test_pause_deployment_with_missing_deployment(self, client):
        response = await client.post(f"/deployments/{uuid4()}/pause_deployment")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_pause_deployment_does_not_set_child_schedule_inactive(
        self,
        client,
        deployment,
        session,
    ):
        await models.deployments.delete_schedules_for_deployment(
            session=session, deployment_id=deployment.id
        )

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        deployment.paused = False

        await models.deployments.create_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    active=True,
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                )
            ],
        )

        await session.commit()

        # The child deployment schedules should be untouched when pausing the deployment
        response = await client.post(f"/deployments/{deployment.id}/pause_deployment")
        assert response.status_code == 200

        schedules = await models.deployments.read_deployment_schedules(
            session=session, deployment_id=deployment.id
        )
        assert len(schedules) == 1
        assert schedules[0].active is True

    async def test_resume_deployment(self, client, deployment, session):
        deployment.paused = True
        await session.commit()

        response = await client.post(f"/deployments/{deployment.id}/resume_deployment")
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.paused is False

    async def test_resume_deployment_can_be_called_multiple_times(
        self, client, deployment, session
    ):
        deployment.paused = True
        await session.commit()

        await client.post(f"/deployments/{deployment.id}/resume_deployment")
        response = await client.post(f"/deployments/{deployment.id}/resume_deployment")
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.paused is False

    async def test_resume_deployment_with_missing_deployment(self, client):
        response = await client.post(f"/deployments/{uuid4()}/resume_deployment")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_resume_deployment_does_not_update_child_schedule(
        self,
        client,
        deployment,
        session,
    ):
        await models.deployments.delete_schedules_for_deployment(
            session=session, deployment_id=deployment.id
        )

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        deployment.paused = True

        await models.deployments.create_deployment_schedules(
            session=session,
            deployment_id=deployment.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    active=False,
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(hours=1)
                    ),
                )
            ],
        )

        await session.commit()

        response = await client.post(f"/deployments/{deployment.id}/resume_deployment")
        assert response.status_code == 200

        schedules = await models.deployments.read_deployment_schedules(
            session=session, deployment_id=deployment.id
        )
        assert len(schedules) == 1
        assert schedules[0].active is False

    async def test_resume_deployment_doesnt_schedule_runs_if_no_schedule_set(
        self, client, deployment, session
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        deployment.schedule = None
        deployment.paused = True
        await session.commit()

        await client.post(f"/deployments/{deployment.id}/resume_deployment")
        await session.refresh(deployment)
        assert deployment.paused is False
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

    async def test_pause_deployment_deletes_auto_scheduled_runs(
        self, client, deployment, session
    ):
        # schedule runs
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value()

        # create a run manually
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC").add(days=1)
                ),
            ),
        )
        await session.commit()

        await client.post(f"/deployments/{deployment.id}/pause_deployment")

        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 1


class TestScheduleDeployment:
    @pytest.fixture
    async def deployment_schedule(self, session, deployment):
        schedules = await models.deployments.read_deployment_schedules(
            session=session, deployment_id=deployment.id
        )
        assert len(schedules) == 1
        return schedules[0]

    async def test_schedule_deployment(
        self, client, session, deployment, deployment_schedule
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(f"/deployments/{deployment.id}/schedule")

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment_schedule.schedule.get_dates(
            n=PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value(),
            start=pendulum.now("UTC"),
            end=pendulum.now("UTC")
            + PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value(),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)

    async def test_schedule_deployment_provide_runs(
        self, client, session, deployment, deployment_schedule
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule", json=dict(min_runs=5)
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment_schedule.schedule.get_dates(
            n=5,
            start=pendulum.now("UTC"),
            end=pendulum.now("UTC")
            + PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value(),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)

    async def test_schedule_deployment_start_time(
        self, client, session, deployment, deployment_schedule
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule",
            json=dict(start_time=str(pendulum.now("UTC").add(days=120))),
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment_schedule.schedule.get_dates(
            n=PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS.value(),
            start=pendulum.now("UTC").add(days=120),
            end=pendulum.now("UTC").add(days=120)
            + PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value(),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)

    async def test_schedule_deployment_end_time(
        self, client, session, deployment, deployment_schedule
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule",
            json=dict(
                end_time=str(pendulum.now("UTC").add(days=7)),
                # schedule a large number of min runs to see the effect of end_time
                min_runs=100,
            ),
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment_schedule.schedule.get_dates(
            n=100,
            start=pendulum.now("UTC"),
            end=pendulum.now("UTC").add(days=7),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)
        assert len(actual_dates) == 7

    async def test_schedule_deployment_backfill(
        self, client, session, deployment, deployment_schedule
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule",
            json=dict(
                start_time=str(pendulum.now("UTC").subtract(days=20)),
                end_time=str(pendulum.now("UTC")),
                min_runs=100,
            ),
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment_schedule.schedule.get_dates(
            n=100,
            start=pendulum.now("UTC").subtract(days=20),
            end=pendulum.now("UTC"),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)
        assert len(actual_dates) == 20


class TestCreateFlowRunFromDeployment:
    async def test_create_flow_run_from_deployment_with_defaults(
        self, deployment, client
    ):
        # should use default parameters, tags, and flow runner
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run", json={}
        )
        assert sorted(response.json()["tags"]) == sorted(deployment.tags)
        assert response.json()["parameters"] == deployment.parameters
        assert response.json()["flow_id"] == str(deployment.flow_id)
        assert response.json()["deployment_id"] == str(deployment.id)
        assert response.json()["work_queue_name"] == deployment.work_queue_name
        assert response.json()["state_type"] == schemas.states.StateType.SCHEDULED
        assert response.json()["deployment_version"] is None

    async def test_create_flow_run_from_deployment_with_deployment_version(
        self, deployment_with_version, client
    ):
        # should use default parameters, tags, and flow runner
        response = await client.post(
            f"deployments/{deployment_with_version.id}/create_flow_run", json={}
        )
        assert response.status_code == 201
        assert response.json()["deployment_version"] == "1.0"

    async def test_create_flow_run_from_deployment_uses_work_queue_name(
        self, deployment, client, session
    ):
        await client.patch(
            f"deployments/{deployment.id}", json=dict(work_queue_name="wq-test")
        )
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run", json={}
        )
        assert response.json()["work_queue_name"] == "wq-test"

    async def test_create_flow_run_from_deployment_allows_queue_override(
        self, deployment, client, session
    ):
        await client.patch(
            f"deployments/{deployment.id}", json=dict(work_queue_name="wq-test")
        )
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                work_queue_name="my-new-test-queue"
            ).model_dump(mode="json"),
        )
        assert response.json()["work_queue_name"] == "my-new-test-queue"

    async def test_create_flow_run_from_deployment_does_not_reset_default_queue(
        self, deployment, client, session
    ):
        default_queue = deployment.work_queue_name

        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                work_queue_name="my-new-test-queue"
            ).model_dump(mode="json"),
        )
        assert response.json()["work_queue_name"] == "my-new-test-queue"
        await session.commit()

        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run", json={}
        )
        assert response.json()["work_queue_name"] == default_queue

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )

        assert deployment.work_queue_name == default_queue

    async def test_create_flow_run_from_deployment_includes_job_variables(
        self, deployment, client, session
    ):
        job_vars = {"foo": "bar"}
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                job_variables=job_vars
            ).model_dump(mode="json"),
        )
        assert response.status_code == 201
        flow_run_id = response.json()["id"]

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run.job_variables == job_vars

        response = await client.get(f"flow_runs/{flow_run_id}")
        assert response.status_code == 200
        assert response.json()["job_variables"] == job_vars

    async def test_create_flow_run_from_deployment_disambiguates_queue_name_from_other_pools(
        self, deployment, client, session
    ):
        """
        This test ensures that if a user provides a common queue name, the correct work pool is used.
        """
        # create a bunch of pools with "default" named queues
        for idx in range(3):
            await models.workers.create_work_pool(
                session=session,
                work_pool=schemas.actions.WorkPoolCreate(
                    name=f"Bogus Work Pool {idx}", base_job_template={}
                ),
            )
        await session.commit()

        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                work_queue_name="default"
            ).model_dump(mode="json"),
        )
        assert response.json()["work_queue_name"] == "default"
        assert response.json()["work_queue_id"] == str(
            deployment.work_queue.work_pool.default_queue_id
        )

    async def test_create_flow_run_from_deployment_override_params(
        self, deployment, client
    ):
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                parameters={"foo": "not_bar"}
            ).model_dump(mode="json"),
        )
        assert response.json()["parameters"] == {"foo": "not_bar"}

    async def test_create_flow_run_from_deployment_override_tags(
        self, deployment, client
    ):
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(tags=["nope"]).model_dump(
                mode="json"
            ),
        )
        assert sorted(response.json()["tags"]) == sorted(["nope"] + deployment.tags)

    async def test_create_flow_run_enforces_parameter_schema(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment_with_parameter_schema.id}/create_flow_run",
            json={"parameters": {"x": 1}},
        )

        assert response.status_code == 409
        assert (
            "Validation failed for field 'x'. Failure reason: 1 is not of type 'string'"
            in response.text
        )

        response = await client.post(
            f"/deployments/{deployment_with_parameter_schema.id}/create_flow_run",
            json={"parameters": {"x": "y"}},
        )

        assert response.status_code == 201

    async def test_create_flow_run_respects_per_run_validation_flag(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment_with_parameter_schema.id}/create_flow_run",
            json={"parameters": {"x": 1}},
        )

        assert response.status_code == 409
        assert (
            "Validation failed for field 'x'. Failure reason: 1 is not of type 'string'"
            in response.text
        )

        response = await client.post(
            f"/deployments/{deployment_with_parameter_schema.id}/create_flow_run",
            json={"parameters": {"x": 1}, "enforce_parameter_schema": False},
        )

        assert response.status_code == 201

    async def test_create_flow_run_does_not_enforce_parameter_schema_when_enforcement_is_toggled_off(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        await client.patch(
            f"/deployments/{deployment_with_parameter_schema.id}",
            json={"enforce_parameter_schema": False},
        )

        response = await client.post(
            f"/deployments/{deployment_with_parameter_schema.id}/create_flow_run",
            json={"parameters": {"x": 1}},
        )

        assert response.status_code == 201

    async def test_create_flow_run_from_deployment_parameter_enforcement_rejects_partial_parameters(
        self,
        client,
        flow,
        work_pool,
    ):
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            work_pool_name=work_pool.name,
            enforce_parameter_schema=True,
            parameter_openapi_schema={
                "type": "object",
                "required": ["person"],
                "properties": {
                    "name": {
                        "type": "string",
                        "default": "world",
                        "position": 1,
                    },
                    "person": {
                        "allOf": [{"$ref": "#/definitions/Person"}],
                        "position": 0,
                    },
                },
                "definitions": {
                    "Person": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "greeting": {
                                "type": "string",
                                "default": "Hello",
                            },
                        },
                    }
                },
            },
        ).model_dump(mode="json")

        response = await client.post(
            "/deployments/",
            json=data,
        )
        assert response.status_code == 201

        deployment_id = response.json()["id"]

        response = await client.post(
            f"/deployments/{deployment_id}/create_flow_run",
            json={"parameters": {"person": {"greeting": "*half hearted wave*"}}},
        )

        assert response.status_code == 409
        assert "Validation failed for field 'person'" in response.text
        assert "Failure reason: 'name' is a required property" in response.text

    async def test_create_flow_run_basic_parameters(
        self,
        deployment,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"parameters": {"param1": 1, "param2": 2}},
        )
        assert response.status_code == 201
        res = response.json()
        assert res["parameters"] == {"param1": 1, "param2": 2}

    async def test_create_flow_run_none_prefect_kind(
        self,
        deployment,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"parameters": {"param": {"__prefect_kind": "none", "value": 5}}},
        )
        assert response.status_code == 201
        res = response.json()
        assert res["parameters"] == {"param": 5}

    async def test_create_flow_run_json_prefect_kind(
        self,
        deployment,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={
                "parameters": {
                    "x": {"__prefect_kind": "json", "value": '"str_of_json"'}
                }
            },
        )

        assert response.status_code == 201
        assert response.json()["parameters"]["x"] == "str_of_json"

    async def test_create_flow_run_jinja_prefect_kind(
        self,
        deployment,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={
                "parameters": {
                    "param": {"__prefect_kind": "jinja", "template": "{{ 1 + 2 }}"}
                }
            },
        )
        assert response.status_code == 201
        res = response.json()
        assert res["parameters"] == {"param": "3"}

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
    async def test_update_deployment_hydrates_workspace_variable_kind_parameters(
        self,
        deployment,
        client,
        session,
        value,
    ):
        await models.variables.create_variable(
            session,
            schemas.actions.VariableCreate(name="my_variable", value=value),
        )
        await session.commit()

        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={
                "parameters": {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my_variable",
                    }
                }
            },
        )
        assert response.status_code == 201, str(response.content)
        res = response.json()
        assert res["parameters"] == {"param": value}

    async def test_create_flow_run_from_deployment_hydration_error(
        self,
        deployment_with_parameter_schema,
        client,
    ):
        response = await client.post(
            f"/deployments/{deployment_with_parameter_schema.id}/create_flow_run",
            json={
                "parameters": {
                    "x": {"__prefect_kind": "json", "value": '{"invalid": json}'}
                }
            },
        )

        assert response.status_code == 400
        assert (
            "Error hydrating flow run parameters: Invalid JSON: Expecting value:"
            in response.json()["detail"]
        )


class TestGetDeploymentWorkQueueCheck:
    async def test_404_on_bad_id(self, client):
        response = await client.get(f"deployments/{uuid4()}/work_queue_check")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_well_formed_response(
        self,
        session,
        client,
        flow,
    ):
        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="First",
                filter=schemas.core.QueueFilter(tags=["a"]),
            ),
        )
        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="Second",
                filter=schemas.core.QueueFilter(tags=["b"]),
            ),
        )

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                tags=["a", "b", "c"],
            ),
        )
        await session.commit()

        response = await client.get(f"deployments/{deployment.id}/work_queue_check")
        assert response.status_code == status.HTTP_200_OK

        connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
        dialect = get_dialect(connection_url)

        if dialect.name == "postgresql":
            assert len(response.json()) == 2

            q1, q2 = response.json()
            assert {q1["name"], q2["name"]} == {"First", "Second"}
            assert set(q1["filter"]["tags"] + q2["filter"]["tags"]) == {"a", "b"}
            assert (
                q1["filter"]["deployment_ids"] == q2["filter"]["deployment_ids"] is None
            )

        else:
            # sqlite picks up the default queue because it has no filter
            assert len(response.json()) == 3

            q1, q2, q3 = response.json()
            assert {q1["name"], q2["name"], q3["name"]} == {
                "First",
                "Second",
                "default",
            }
            assert set(q2["filter"]["tags"] + q3["filter"]["tags"]) == {"a", "b"}
            assert (
                q2["filter"]["deployment_ids"] == q3["filter"]["deployment_ids"] is None
            )
