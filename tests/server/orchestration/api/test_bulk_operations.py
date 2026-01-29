"""
Tests for bulk operation endpoints.
"""

from uuid import uuid4

from starlette import status

from prefect.server import models, schemas


class TestFlowRunBulkDelete:
    async def test_bulk_delete_flow_runs(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test bulk deletion of flow runs."""
        # Create flow runs
        flow_runs = []
        for _ in range(3):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                ),
            )
            flow_runs.append(flow_run)
        await session.commit()

        # Bulk delete
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {"id": {"any_": [str(fr.id) for fr in flow_runs[:2]]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["deleted"]) == 2
        assert set(data["deleted"]) == {str(flow_runs[0].id), str(flow_runs[1].id)}

    async def test_bulk_delete_flow_runs_empty_filter(
        self,
        hosted_api_client,
    ):
        """Test bulk deletion with empty filter returns empty list."""
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {"id": {"any_": [str(uuid4())]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == []

    async def test_bulk_delete_flow_runs_respects_limit(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test bulk deletion respects limit."""
        # Create flow runs
        flow_runs = []
        for _ in range(5):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                ),
            )
            flow_runs.append(flow_run)
        await session.commit()

        # Bulk delete with limit
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {"id": {"any_": [str(fr.id) for fr in flow_runs]}},
                "limit": 2,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["deleted"]) == 2

    async def test_bulk_delete_flow_runs_no_filter(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test bulk deletion with no filter."""
        # Create flow runs
        for _ in range(3):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                ),
            )
        await session.commit()

        # Bulk delete with no filter - should delete up to limit
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={"limit": 2},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["deleted"]) == 2


class TestFlowRunBulkSetState:
    async def test_bulk_set_state(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk state setting for flow runs."""
        # Create flow runs
        flow_runs = []
        for _ in range(3):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                ),
            )
            flow_runs.append(flow_run)
        await session.commit()

        # Bulk set state
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {"id": {"any_": [str(fr.id) for fr in flow_runs[:2]]}},
                "state": {"type": "CANCELLED", "name": "Cancelled"},
                "force": True,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 2
        for result in data["results"]:
            assert result["status"] == "ACCEPT"

    async def test_bulk_set_state_empty_filter(
        self,
        client,
    ):
        """Test bulk set state with empty filter returns empty list."""
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {"id": {"any_": [str(uuid4())]}},
                "state": {"type": "CANCELLED", "name": "Cancelled"},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["results"] == []

    async def test_bulk_set_state_respects_limit(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk set state respects limit."""
        # Create flow runs
        flow_runs = []
        for _ in range(5):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                ),
            )
            flow_runs.append(flow_run)
        await session.commit()

        # Bulk set state with limit
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {"id": {"any_": [str(fr.id) for fr in flow_runs]}},
                "state": {"type": "CANCELLED", "name": "Cancelled"},
                "force": True,
                "limit": 2,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 2


class TestDeploymentBulkDelete:
    async def test_bulk_delete_deployments(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk deletion of deployments."""
        # Create deployments
        deployments = []
        for i in range(3):
            deployment = await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"test-deployment-{uuid4()}",
                    flow_id=flow.id,
                ),
            )
            deployments.append(deployment)
        await session.commit()

        # Bulk delete
        response = await client.post(
            "/deployments/bulk_delete",
            json={
                "deployments": {"id": {"any_": [str(d.id) for d in deployments[:2]]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["deleted"]) == 2

    async def test_bulk_delete_deployments_empty_filter(
        self,
        client,
    ):
        """Test bulk deletion with empty filter returns empty list."""
        response = await client.post(
            "/deployments/bulk_delete",
            json={
                "deployments": {"id": {"any_": [str(uuid4())]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == []


class TestDeploymentBulkCreateFlowRun:
    async def test_bulk_create_flow_runs(
        self,
        deployment,
        hosted_api_client,
    ):
        """Test bulk creation of flow runs from a deployment."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[
                {"name": "run-1"},
                {"name": "run-2"},
                {"name": "run-3"},
            ],
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 3
        for result in data["results"]:
            assert result["status"] == "CREATED"
            assert result["flow_run_id"] is not None

    async def test_bulk_create_flow_runs_empty_list(
        self,
        deployment,
        hosted_api_client,
    ):
        """Test bulk creation with empty list returns empty list."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[],
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["results"] == []

    async def test_bulk_create_flow_runs_deployment_not_found(
        self,
        hosted_api_client,
    ):
        """Test bulk creation with non-existent deployment returns 404."""
        response = await hosted_api_client.post(
            f"/deployments/{uuid4()}/create_flow_run/bulk",
            json=[{"name": "run-1"}],
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_bulk_create_flow_runs_exceeds_limit(
        self,
        deployment,
        hosted_api_client,
    ):
        """Test bulk creation with too many items returns 400."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[{"name": f"run-{i}"} for i in range(101)],
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_bulk_create_flow_runs_with_parameters(
        self,
        deployment,
        hosted_api_client,
    ):
        """Test bulk creation of flow runs with custom parameters."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[
                {"name": "run-1", "parameters": {"x": 1}},
                {"name": "run-2", "parameters": {"x": 2}},
            ],
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 2
        for result in data["results"]:
            assert result["status"] == "CREATED"


class TestFlowBulkDelete:
    async def test_bulk_delete_flows(
        self,
        session,
        client,
    ):
        """Test bulk deletion of flows."""
        # Create flows
        flows = []
        for i in range(3):
            flow = await models.flows.create_flow(
                session=session,
                flow=schemas.core.Flow(name=f"test-flow-{uuid4()}"),
            )
            flows.append(flow)
        await session.commit()

        # Bulk delete
        response = await client.post(
            "/flows/bulk_delete",
            json={
                "flows": {"id": {"any_": [str(f.id) for f in flows[:2]]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["deleted"]) == 2

    async def test_bulk_delete_flows_empty_filter(
        self,
        client,
    ):
        """Test bulk deletion with empty filter returns empty list."""
        response = await client.post(
            "/flows/bulk_delete",
            json={
                "flows": {"id": {"any_": [str(uuid4())]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"] == []

    async def test_bulk_delete_flows_deletes_deployments(
        self,
        session,
        client,
    ):
        """Test bulk deletion of flows also deletes their deployments."""
        # Create a flow and deployment
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-{uuid4()}"),
        )
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="test-deployment",
                flow_id=flow.id,
            ),
        )
        await session.commit()

        # Bulk delete flow
        response = await client.post(
            "/flows/bulk_delete",
            json={
                "flows": {"id": {"any_": [str(flow.id)]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert str(flow.id) in response.json()["deleted"]

        # Verify deployment is also deleted
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFlowFilterNotAny:
    async def test_flow_filter_not_any(
        self,
        session,
        client,
    ):
        """Test FlowFilter with not_any_ filter."""
        # Create flows with unique names to avoid conflicts
        unique_prefix = str(uuid4())[:8]
        flows = []
        for i in range(3):
            flow = await models.flows.create_flow(
                session=session,
                flow=schemas.core.Flow(name=f"test-filter-flow-{unique_prefix}-{i}"),
            )
            flows.append(flow)
        await session.commit()

        # Query flows excluding one
        response = await client.post(
            "/flows/filter",
            json={
                "flows": {
                    "id": {"not_any_": [str(flows[0].id)]},
                    "name": {"like_": unique_prefix},
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should not include the excluded flow
        flow_ids = [f["id"] for f in data]
        assert str(flows[0].id) not in flow_ids
        # Should include the other flows
        assert str(flows[1].id) in flow_ids
        assert str(flows[2].id) in flow_ids
