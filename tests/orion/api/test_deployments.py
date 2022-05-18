import datetime
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa
from fastapi import status

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import DeploymentCreate
from prefect.orion.schemas.data import DataDocument
from prefect.settings import (
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS,
    PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME,
)


class TestCreateDeployment:
    async def test_create_deployment(self, session, client, flow, flow_function):
        flow_data = DataDocument.encode("cloudpickle", flow_function)

        data = DeploymentCreate(
            name="My Deployment",
            flow_data=flow_data,
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "My Deployment"
        assert response.json()["flow_data"] == flow_data.dict(json_compatible=True)
        assert response.json()["flow_runner"] == {"config": None, "type": None}
        deployment_id = response.json()["id"]

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment_id
        )
        assert str(deployment.id) == deployment_id
        assert deployment.name == "My Deployment"
        assert deployment.tags == ["foo"]
        assert deployment.flow_id == flow.id
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.flow_runner == schemas.core.FlowRunnerSettings(
            config=None, type=None
        )

    @pytest.mark.parametrize("with_config", [True, False])
    async def test_create_deployment_with_flow_runner(
        self, session, client, flow, flow_function, with_config
    ):
        flow_data = DataDocument.encode("cloudpickle", flow_function)

        data = DeploymentCreate(
            name="My Deployment",
            flow_data=flow_data,
            flow_id=flow.id,
            flow_runner=schemas.core.FlowRunnerSettings(
                type="test", config={"foo": "bar"} if with_config else None
            ),
        ).dict(json_compatible=True)

        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        assert response.json()["flow_runner"] == schemas.core.FlowRunnerSettings(
            type="test", config={"foo": "bar"} if with_config else None
        ).dict(json_compatible=True)

        deployment = await models.deployments.read_deployment(
            session=session, deployment_id=response.json()["id"]
        )
        assert deployment.flow_runner == schemas.core.FlowRunnerSettings(
            type="test", config={"foo": "bar"} if with_config else None
        )

    async def test_create_deployment_respects_flow_id_name_uniqueness(
        self, session, client, flow, flow_function
    ):
        flow_data = DataDocument.encode("cloudpickle", flow_function)

        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            flow_data=flow_data,
            is_schedule_active=False,
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My Deployment"
        assert response.json()["flow_data"] == flow_data.dict(json_compatible=True)
        deployment_id = response.json()["id"]

        # post the same data
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            is_schedule_active=False,
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "My Deployment"
        assert response.json()["id"] == deployment_id
        assert response.json()["flow_data"] == flow_data.dict(json_compatible=True)
        assert response.json()["flow_runner"] == {"config": None, "type": None}
        assert not response.json()["is_schedule_active"]

        # post different data, upsert should be respected
        data = DeploymentCreate(
            name="My Deployment",
            flow_id=flow.id,
            flow_data=DataDocument.encode("json", "test"),
            is_schedule_active=True,
            flow_runner=schemas.core.FlowRunnerSettings(
                type="test", config={"foo": "bar"}
            ),
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "My Deployment"
        assert response.json()["id"] == deployment_id
        assert response.json()["is_schedule_active"]
        assert response.json()["flow_data"] == DataDocument.encode("json", "test").dict(
            json_compatible=True
        )
        assert response.json()["flow_runner"] == schemas.core.FlowRunnerSettings(
            type="test", config={"foo": "bar"}
        ).dict(json_compatible=True)

    async def test_create_deployment_populates_and_returned_created(
        self, client, flow, flow_function
    ):
        now = pendulum.now(tz="UTC")

        data = DeploymentCreate(
            name="My Deployment",
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            flow_id=flow.id,
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My Deployment"
        assert pendulum.parse(response.json()["created"]) >= now
        assert pendulum.parse(response.json()["updated"]) >= now

    async def test_creating_deployment_with_active_schedule_doesnt_create_runs(
        self, session, client, flow, flow_function
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            "/deployments/",
            json=DeploymentCreate(
                name="My Deployment",
                flow_id=flow.id,
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
            ).dict(json_compatible=True),
        )

        n_runs = await models.flow_runs.count_flow_runs(
            session, flow_filter=schemas.filters.FlowFilter(id=dict(any_=[flow.id]))
        )
        assert n_runs == 0

    async def test_creating_deployment_with_inactive_schedule_creates_no_runs(
        self, session, client, flow, flow_function
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            "/deployments/",
            json=DeploymentCreate(
                name="My Deployment",
                flow_id=flow.id,
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
                is_schedule_active=False,
            ).dict(json_compatible=True),
        )

        n_runs = await models.flow_runs.count_flow_runs(
            session, flow_filter=schemas.filters.FlowFilter(id=dict(any_=[flow.id]))
        )
        assert n_runs == 0

    async def test_creating_deployment_with_no_schedule_creates_no_runs(
        self, session, client, flow, flow_function
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            "/deployments/",
            json=DeploymentCreate(
                name="My Deployment",
                flow_id=flow.id,
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                is_schedule_active=True,
            ).dict(json_compatible=True),
        )

        n_runs = await models.flow_runs.count_flow_runs(
            session, flow_filter=schemas.filters.FlowFilter(id=dict(any_=[flow.id]))
        )
        assert n_runs == 0

    async def test_upserting_deployment_with_inactive_schedule_deletes_existing_auto_scheduled_runs(
        self, client, deployment, session, flow_function
    ):

        # schedule runs
        response = await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 100

        # create a run manually to ensure it isn't deleted
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now().add(days=1)
                ),
            ),
        )
        await session.commit()

        # upsert the deployment with schedule inactive
        response = await client.post(
            "/deployments/",
            json=schemas.actions.DeploymentCreate(
                name=deployment.name,
                flow_id=deployment.flow_id,
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                schedule=deployment.schedule,
                is_schedule_active=False,
            ).dict(json_compatible=True),
        )

        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 1

    async def test_upserting_deployment_with_new_schedule_deletes_existing_auto_scheduled_runs(
        self,
        client,
        deployment,
        session,
        flow_function,
        db,
    ):

        # schedule runs
        response = await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 100

        # create a run manually to ensure it isn't deleted
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now().add(seconds=2)
                ),
            ),
        )
        await session.commit()

        # upsert the deployment with schedule inactive
        await client.post(
            "/deployments/",
            json=schemas.actions.DeploymentCreate(
                name=deployment.name,
                flow_id=deployment.flow_id,
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(seconds=1)
                ),
                is_schedule_active=True,
            ).dict(json_compatible=True),
        )

        # auto-scheduled runs should be deleted
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 1

        # check that the maximum run is from the secondly schedule
        query = sa.select(sa.func.max(db.FlowRun.expected_start_time))
        result = await session.execute(query)
        assert result.scalar() < pendulum.now().add(seconds=100)


class TestReadDeployment:
    async def test_read_deployment(self, client, flow, flow_function):

        flow_data = DataDocument.encode("cloudpickle", flow_function)

        # first create a deployment to read
        data = DeploymentCreate(
            name="My Deployment",
            flow_data=flow_data,
            flow_id=flow.id,
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        deployment_id = response.json()["id"]

        # make sure we we can read the deployment correctly
        response = await client.get(f"/deployments/{deployment_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == deployment_id
        assert response.json()["name"] == "My Deployment"
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["flow_data"] == flow_data.dict(json_compatible=True)

    async def test_read_deployment_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/deployments/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadDeploymentByName:
    async def test_read_deployment_by_name(self, client, flow, flow_function):
        # first create a deployment to read
        flow_data = DataDocument.encode("cloudpickle", flow_function)
        data = DeploymentCreate(
            name="My Deployment",
            flow_data=flow_data,
            flow_id=flow.id,
        ).dict(json_compatible=True)
        response = await client.post("/deployments/", json=data)
        deployment_id = response.json()["id"]

        # make sure we we can read the deployment correctly
        response = await client.get(f"/deployments/name/{flow.name}/{data['name']}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == deployment_id
        assert response.json()["name"] == "My Deployment"
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["flow_data"] == flow_data.dict(json_compatible=True)

    async def test_read_deployment_by_name_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/deployments/name/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_deployment_by_name_returns_404_if_just_given_flow_name(
        self, client, flow
    ):
        response = await client.get(f"/deployments/name/{flow.name}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_deployment_by_name_returns_404_if_just_given_deployment_name(
        self, client, flow, flow_function
    ):
        # create a deployment to read
        response = await client.post(
            "/deployments/",
            json=DeploymentCreate(
                name="My Deployment",
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                flow_id=flow.id,
            ).dict(json_compatible=True),
        )

        response = await client.get(f"/deployments/name/My Deployment")
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
        self, client, name, flow
    ):
        response = await client.post(
            "/deployments/",
            json=dict(
                name=name,
                flow_id=str(flow.id),
                flow_data=schemas.data.DataDocument(encoding="x", blob=b"y").dict(
                    json_compatible=True
                ),
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
        self, session, deployment_id_1, deployment_id_2, flow, flow_function
    ):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_1,
                name="My Deployment X",
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                flow_id=flow.id,
                is_schedule_active=True,
            ),
        )

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_2,
                name="My Deployment Y",
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                flow_id=flow.id,
                is_schedule_active=False,
            ),
        )
        await session.commit()

    async def test_read_deployments(self, deployments, client):
        response = await client.post("/deployments/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    async def test_read_deployments_applies_filter(
        self, deployments, deployment_id_1, deployment_id_2, flow, client
    ):
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment X"])
            ).dict(json_compatible=True)
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert {deployment["id"] for deployment in response.json()} == {
            str(deployment_id_1)
        }

        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                name=schemas.filters.DeploymentFilterName(any_=["My Deployment 123"])
            ).dict(json_compatible=True)
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

        deployment_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow.name])
            ).dict(json_compatible=True)
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
            ).dict(json_compatible=True),
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["not a flow name"])
            ).dict(json_compatible=True),
        )
        response = await client.post("/deployments/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

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

    async def test_read_deployments_returns_empty_list(self, client):
        response = await client.post("/deployments/filter")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


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


class TestSetScheduleActive:
    async def test_set_schedule_inactive(self, client, deployment, session):
        assert deployment.is_schedule_active is True
        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_inactive"
        )
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.is_schedule_active is False

    async def test_set_schedule_inactive_can_be_called_multiple_times(
        self, client, deployment, session
    ):
        assert deployment.is_schedule_active is True
        await client.post(f"/deployments/{deployment.id}/set_schedule_inactive")
        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_inactive"
        )
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.is_schedule_active is False

    async def test_set_schedule_inactive_with_missing_deployment(self, client):
        response = await client.post(f"/deployments/{uuid4()}/set_schedule_inactive")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_set_schedule_active(self, client, deployment, session):
        deployment.is_schedule_active = False
        await session.commit()

        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_active"
        )
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.is_schedule_active is True

    async def test_set_schedule_active_can_be_called_multiple_times(
        self, client, deployment, session
    ):
        deployment.is_schedule_active = False
        await session.commit()

        await client.post(f"/deployments/{deployment.id}/set_schedule_active")
        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_active"
        )
        assert response.status_code == status.HTTP_200_OK

        await session.refresh(deployment)
        assert deployment.is_schedule_active is True

    async def test_set_schedule_active_with_missing_deployment(self, client):
        response = await client.post(f"/deployments/{uuid4()}/set_schedule_active")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_set_schedule_active_toggles_active_flag(
        self, client, deployment, session
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        deployment.is_schedule_active = False
        await session.commit()

        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_active"
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await session.refresh(deployment)
        assert deployment.is_schedule_active is True

    async def test_set_schedule_active_doesnt_schedule_runs_if_no_schedule_set(
        self, client, deployment, session
    ):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        deployment.schedule = None
        deployment.is_schedule_active = False
        await session.commit()

        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_active"
        )
        await session.refresh(deployment)
        assert deployment.is_schedule_active is True
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

    async def test_set_schedule_inactive_deletes_auto_scheduled_runs(
        self, client, deployment, session
    ):

        # schedule runs
        response = await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 100

        # create a run manually
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now().add(days=1)
                ),
            ),
        )
        await session.commit()

        response = await client.post(
            f"/deployments/{deployment.id}/set_schedule_inactive"
        )

        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 1


class TestScheduleDeployment:
    async def test_schedule_deployment(self, client, session, deployment):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(f"/deployments/{deployment.id}/schedule")

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment.schedule.get_dates(
            n=PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value(),
            start=pendulum.now(),
            end=pendulum.now()
            + PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value(),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)

    async def test_schedule_deployment_max_runs(self, client, session, deployment):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule", json=dict(max_runs=5)
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment.schedule.get_dates(
            n=5,
            start=pendulum.now(),
            end=pendulum.now()
            + PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value(),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)

    async def test_schedule_deployment_start_time(self, client, session, deployment):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule",
            json=dict(start_time=str(pendulum.now().add(days=120))),
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment.schedule.get_dates(
            n=PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value(),
            start=pendulum.now().add(days=120),
            end=pendulum.now().add(days=120)
            + PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME.value(),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)

    async def test_schedule_deployment_end_time(self, client, session, deployment):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule",
            json=dict(end_time=str(pendulum.now("UTC").add(days=7))),
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment.schedule.get_dates(
            n=PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value(),
            start=pendulum.now("UTC"),
            end=pendulum.now("UTC").add(days=7),
        )
        actual_dates = {r.state.state_details.scheduled_time for r in runs}
        assert actual_dates == set(expected_dates)
        assert len(actual_dates) == 7

    async def test_schedule_deployment_backfill(self, client, session, deployment):
        n_runs = await models.flow_runs.count_flow_runs(session)
        assert n_runs == 0

        await client.post(
            f"/deployments/{deployment.id}/schedule",
            json=dict(
                start_time=str(pendulum.now("UTC").subtract(days=20)),
                end_time=str(pendulum.now("UTC")),
            ),
        )

        runs = await models.flow_runs.read_flow_runs(session)
        expected_dates = await deployment.schedule.get_dates(
            n=PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS.value(),
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
        assert response.json()["flow_runner"] == deployment.flow_runner.dict(
            json_compatible=True
        )

    async def test_create_flow_run_from_deployment_override_params(
        self, deployment, client
    ):
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                parameters={"foo": "not_bar"}
            ).dict(json_compatible=True),
        )
        assert response.json()["parameters"] == {"foo": "not_bar"}

    async def test_create_flow_run_from_deployment_override_tags(
        self, deployment, client
    ):
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(tags=["nope"]).dict(
                json_compatible=True
            ),
        )
        assert sorted(response.json()["tags"]) == ["nope"]

    async def test_create_flow_run_from_deployment_override_flow_runner(
        self, deployment, client
    ):
        response = await client.post(
            f"deployments/{deployment.id}/create_flow_run",
            json=schemas.actions.DeploymentFlowRunCreate(
                flow_runner=schemas.core.FlowRunnerSettings(
                    type="override", config={"apple": "berry"}
                )
            ).dict(json_compatible=True),
        )
        assert response.json()["flow_runner"] == schemas.core.FlowRunnerSettings(
            type="override", config={"apple": "berry"}
        ).dict(json_compatible=True)
