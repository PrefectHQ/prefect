import urllib.parse
from uuid import UUID, uuid4

import pytest
from starlette import status

from prefect.server import models, schemas
from prefect.types._datetime import now, parse_datetime
from prefect.utilities.pydantic import parse_obj_as


class TestCreateFlow:
    async def test_create_flow(self, session, client):
        flow_data = {"name": "my-flow", "labels": {"env": "dev"}}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "my-flow"
        flow_id = response.json()["id"]

        flow = await models.flows.read_flow(session=session, flow_id=flow_id)
        assert flow
        assert str(flow.id) == flow_id
        assert flow.labels == {"env": "dev"}

    async def test_create_flow_populates_and_returned_created(self, client):
        current_time = now("UTC")
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "my-flow"
        assert parse_datetime(response.json()["created"]) >= current_time
        assert parse_datetime(response.json()["updated"]) >= current_time

    async def test_create_flow_gracefully_fallsback(self, client):
        """If the flow already exists, we return a 200 code"""
        flow_data = {"name": "my-flow"}
        response_1 = await client.post("/flows/", json=flow_data)
        assert response_1.status_code == status.HTTP_201_CREATED
        assert response_1.json()["name"] == "my-flow"
        response_2 = await client.post("/flows/", json=flow_data)
        assert response_2.status_code == status.HTTP_200_OK
        assert response_2.json()["name"] == "my-flow"

    @pytest.mark.parametrize(
        "name",
        [
            "my flow",
            "my:flow",
            r"my\flow",
            "my👍flow",
            "my|flow",
        ],
    )
    async def test_create_flow_with_nonstandard_characters(self, client, name):
        response = await client.post("/flows/", json=dict(name=name))
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "name",
        [
            "my/flow",
            r"my%flow",
        ],
    )
    async def test_create_flow_with_invalid_characters_fails(self, client, name):
        response = await client.post("/flows/", json=dict(name=name))
        assert response.status_code == 422


class TestUpdateFlow:
    async def test_update_flow_succeeds(self, session, client):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await session.commit()
        current_time = now("UTC")

        response = await client.patch(
            f"/flows/{str(flow.id)}",
            json=schemas.actions.FlowUpdate(tags=["TB12"]).model_dump(),
        )
        assert response.status_code == 204

        response = await client.get(f"flows/{flow.id}")
        updated_flow = parse_obj_as(schemas.core.Flow, response.json())
        assert updated_flow.tags == ["TB12"]
        assert updated_flow.updated > current_time

    async def test_update_flow_does_not_update_if_fields_not_set(self, session, client):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await session.commit()

        response = await client.patch(
            f"/flows/{str(flow.id)}",
            json={},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"flows/{flow.id}")
        updated_flow = parse_obj_as(schemas.core.Flow, response.json())
        assert updated_flow.tags == ["db", "blue"]

    async def test_update_flow_raises_error_if_flow_does_not_exist(self, client):
        response = await client.patch(
            f"/flows/{str(uuid4())}",
            json={},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadFlow:
    async def test_read_flow(self, client):
        # first create a flow to read
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        flow_id = response.json()["id"]

        # make sure we we can read the flow correctly
        response = await client.get(f"/flows/{flow_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == flow_id
        assert response.json()["name"] == "my-flow"

    async def test_read_flow_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flows/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_flow_by_name(self, client):
        # first create a flow to read
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        flow_id = response.json()["id"]

        # make sure we we can read the flow correctly
        response = await client.get("/flows/name/my-flow")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == flow_id
        assert response.json()["name"] == "my-flow"

    async def test_read_flow_by_name_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flows/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        "name",
        [
            "my flow",
            "my:flow",
            r"my\flow",
            "my👍flow",
            "my|flow",
        ],
    )
    async def test_read_flow_by_name_with_nonstandard_characters(self, client, name):
        response = await client.post("/flows/", json=dict(name=name))
        flow_id = response.json()["id"]

        response = await client.get(f"/flows/name/{name}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == flow_id

        response = await client.get(urllib.parse.quote(f"/flows/name/{name}"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == flow_id
        assert response.json()["name"] == name

    @pytest.mark.parametrize(
        "name",
        [
            "my/flow",
            r"my%flow",
        ],
    )
    async def test_read_flow_by_name_with_invalid_characters_fails(self, client, name):
        response = await client.get(f"/flows/name/{name}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadFlows:
    @pytest.fixture
    async def flows(self, client):
        await client.post("/flows/", json={"name": "my-flow-1"})
        await client.post("/flows/", json={"name": "my-flow-2"})

    @pytest.mark.usefixtures("flows")
    async def test_read_flows(self, client):
        response = await client.post("/flows/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    @pytest.mark.usefixtures("flows")
    async def test_read_flows_applies_limit(self, client):
        response = await client.post("/flows/filter", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_flows_applies_flow_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        await session.commit()

        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["my-flow-1"])
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/filter", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_applies_flow_run_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_1.id),
        )
        await session.commit()

        flow_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_1.id])
            ).model_dump(mode="json")
        )

        response = await client.post("/flows/filter", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_applies_task_run_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_1.id),
        )
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run_1.id,
                task_key="my-key",
                dynamic_key="0",
            ),
        )
        await session.commit()

        flow_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_1.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/filter", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_applies_work_pool(self, client, session, work_pool):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        await session.commit()

        response = await client.post("/flows/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

        # work queue
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="test-queue"),  # type: ignore
        )
        # deployment
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment X",
                flow_id=flow_1.id,
                work_queue_id=work_queue.id,
            ),
        )
        await session.commit()

        work_pool_filter = dict(
            work_pools=schemas.filters.WorkPoolFilter(
                id=schemas.filters.WorkPoolFilterId(any_=[work_pool.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/filter", json=work_pool_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_applies_deployment_is_null(self, client, session):
        undeployed_flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="undeployment_flow"),
        )
        deployed_flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="deployed_flow")
        )
        await session.commit()

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="Mr. Deployment",
                flow_id=deployed_flow.id,
            ),
        )
        await session.commit()

        deployment_filter_isnull = dict(
            flows=schemas.filters.FlowFilter(
                deployment=schemas.filters.FlowFilterDeployment(is_null_=True)
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/filter", json=deployment_filter_isnull)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == undeployed_flow.id

        deployment_filter_not_isnull = dict(
            flows=schemas.filters.FlowFilter(
                deployment=schemas.filters.FlowFilterDeployment(is_null_=False)
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/filter", json=deployment_filter_not_isnull)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == deployed_flow.id

    async def test_read_flows_offset(self, flows, client):
        # right now this works because flows are ordered by name
        # by default, when ordering is actually implemented, this test
        # should be re-written
        response = await client.post("/flows/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "my-flow-2"

    async def test_read_flows_sort(self, flows, client):
        response = await client.post(
            "/flows/filter", json=dict(sort=schemas.sorting.FlowSort.NAME_ASC)
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["name"] == "my-flow-1"

        response_desc = await client.post(
            "/flows/filter", json=dict(sort=schemas.sorting.FlowSort.NAME_DESC)
        )
        assert response_desc.status_code == status.HTTP_200_OK
        assert response_desc.json()[0]["name"] == "my-flow-2"

    async def test_read_flows_returns_empty_list(self, client):
        response = await client.post("/flows/filter")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestDeleteFlow:
    async def test_delete_flow(self, client):
        # first create a flow to delete
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        flow_id = response.json()["id"]

        # delete the flow
        response = await client.delete(f"/flows/{flow_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # make sure it's deleted
        response = await client.get(f"/flows/{flow_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_flow_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/flows/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPaginateFlows:
    @pytest.fixture
    async def flows(self, client):
        await client.post("/flows/", json={"name": "my-flow-1"})
        await client.post("/flows/", json={"name": "my-flow-2"})

    @pytest.mark.usefixtures("flows")
    async def test_paginate_flows(self, client):
        response = await client.post("/flows/paginate")
        assert response.status_code == status.HTTP_200_OK

        json = response.json()

        assert len(json["results"]) == 2
        assert json["page"] == 1
        assert json["pages"] == 1
        assert json["count"] == 2

    @pytest.mark.usefixtures("flows")
    async def test_paginate_flows_applies_limit(self, client):
        response = await client.post("/flows/paginate", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK

        json = response.json()

        assert len(json["results"]) == 1
        assert json["page"] == 1
        assert json["pages"] == 2
        assert json["count"] == 2

    async def test_paginate_flows_applies_flow_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        await session.commit()

        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["my-flow-1"])
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/paginate", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert UUID(results[0]["id"]) == flow_1.id

    async def test_paginate_flows_applies_flow_run_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_1.id),
        )
        await session.commit()

        flow_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_1.id])
            ).model_dump(mode="json")
        )

        response = await client.post("/flows/paginate", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert UUID(results[0]["id"]) == flow_1.id

    async def test_paginate_flows_applies_task_run_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_1.id),
        )
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run_1.id,
                task_key="my-key",
                dynamic_key="0",
            ),
        )
        await session.commit()

        flow_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_1.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/paginate", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert UUID(results[0]["id"]) == flow_1.id

    async def test_paginate_flows_applies_work_pool(self, client, session, work_pool):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        await session.commit()

        response = await client.post("/flows/paginate")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 2

        # work queue
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="test-queue"),  # type: ignore
        )
        # deployment
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment X",
                flow_id=flow_1.id,
                work_queue_id=work_queue.id,
            ),
        )
        await session.commit()

        work_pool_filter = dict(
            work_pools=schemas.filters.WorkPoolFilter(
                id=schemas.filters.WorkPoolFilterId(any_=[work_pool.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/paginate", json=work_pool_filter)
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert UUID(results[0]["id"]) == flow_1.id

    async def test_paginate_flows_applies_deployment_is_null(self, client, session):
        undeployed_flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="undeployment_flow"),
        )
        deployed_flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="deployed_flow")
        )
        await session.commit()

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="Mr. Deployment",
                flow_id=deployed_flow.id,
            ),
        )
        await session.commit()

        deployment_filter_isnull = dict(
            flows=schemas.filters.FlowFilter(
                deployment=schemas.filters.FlowFilterDeployment(is_null_=True)
            ).model_dump(mode="json")
        )
        response = await client.post("/flows/paginate", json=deployment_filter_isnull)
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert UUID(results[0]["id"]) == undeployed_flow.id

        deployment_filter_not_isnull = dict(
            flows=schemas.filters.FlowFilter(
                deployment=schemas.filters.FlowFilterDeployment(is_null_=False)
            ).model_dump(mode="json")
        )
        response = await client.post(
            "/flows/paginate", json=deployment_filter_not_isnull
        )
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert UUID(results[0]["id"]) == deployed_flow.id

    async def test_paginate_flows_page(self, flows, client):
        # right now this works because flows are ordered by name
        # by default, when ordering is actually implemented, this test
        # should be re-written
        response = await client.post("/flows/paginate", json=dict(page=2, limit=1))
        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["name"] == "my-flow-2"

    async def test_paginate_flows_sort(self, flows, client):
        response = await client.post(
            "/flows/paginate", json=dict(sort=schemas.sorting.FlowSort.NAME_ASC)
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"][0]["name"] == "my-flow-1"

        response_desc = await client.post(
            "/flows/paginate", json=dict(sort=schemas.sorting.FlowSort.NAME_DESC)
        )
        assert response_desc.status_code == status.HTTP_200_OK
        assert response_desc.json()["results"][0]["name"] == "my-flow-2"

    async def test_read_flows_returns_empty_list(self, client):
        response = await client.post("/flows/paginate")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == []
