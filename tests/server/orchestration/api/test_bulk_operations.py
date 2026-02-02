"""
Comprehensive tests for bulk operation endpoints.

These tests cover:
- Basic bulk operations
- Validation errors (limit bounds)
- Filter edge cases
- Verification of actual deletion
- Cascading deletes
- Mixed results for state changes
- Parameter validation
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from starlette import status

from prefect.server import models, schemas


class TestFlowRunBulkDelete:
    """Tests for POST /flow_runs/bulk_delete endpoint."""

    async def test_bulk_delete_flow_runs(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test basic bulk deletion of flow runs."""
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

    async def test_bulk_delete_verifies_actual_deletion(
        self,
        session,
        flow,
        hosted_api_client,
        client,
    ):
        """Test that deleted flow runs are actually gone from the database."""
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()

        # Delete the flow run
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={"flow_runs": {"id": {"any_": [str(flow_run.id)]}}},
        )
        assert response.status_code == status.HTTP_200_OK
        assert str(flow_run.id) in response.json()["deleted"]

        # Verify it's actually deleted
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_bulk_delete_with_invalid_ids(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test that only valid flow runs are deleted, invalid IDs are ignored."""
        # Create 1 valid flow run
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()

        invalid_id = uuid4()
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {"id": {"any_": [str(flow_run.id), str(invalid_id)]}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # Only the valid run should be deleted
        assert len(body["deleted"]) == 1
        assert body["deleted"][0] == str(flow_run.id)

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

    async def test_bulk_delete_validation_limit_zero(
        self,
        hosted_api_client,
    ):
        """Test that limit=0 returns 422."""
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {},
                "limit": 0,
            },
        )
        assert response.status_code == 422

    async def test_bulk_delete_validation_limit_too_high(
        self,
        hosted_api_client,
    ):
        """Test that limit > max returns 422."""
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {},
                "limit": 201,
            },
        )
        assert response.status_code == 422

    async def test_bulk_delete_by_state_name(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test deleting flow runs filtered by state name (e.g., late runs)."""
        now = datetime.now(timezone.utc)

        # Create late runs (Scheduled state with name "Late")
        late_runs = []
        for i in range(3):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    name=f"late-run-{i}",
                    state=schemas.states.Scheduled(
                        name="Late", scheduled_time=now - timedelta(hours=2)
                    ),
                    expected_start_time=now - timedelta(hours=2),
                ),
            )
            late_runs.append(flow_run)

        # Create on-time scheduled runs that should NOT be deleted
        future_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="future-run",
                state=schemas.states.Scheduled(scheduled_time=now + timedelta(hours=1)),
            ),
        )

        # Create a running run
        running_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="running-run",
                state=schemas.states.Running(),
            ),
        )
        await session.commit()

        # Delete all late flow runs (by state name "Late")
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {"state": {"name": {"any_": ["Late"]}}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["deleted"]) == 3

        # Verify late runs deleted, others remain
        for run in late_runs:
            assert str(run.id) in result["deleted"]
        assert str(future_run.id) not in result["deleted"]
        assert str(running_run.id) not in result["deleted"]

    async def test_bulk_delete_by_state_type(
        self,
        session,
        flow,
        hosted_api_client,
    ):
        """Test deleting flow runs filtered by state type."""
        # Create runs in different states
        pending_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Pending(),
            ),
        )
        running_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Running(),
            ),
        )
        completed_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Completed(),
            ),
        )
        await session.commit()

        # Delete only PENDING runs
        response = await hosted_api_client.post(
            "/flow_runs/bulk_delete",
            json={
                "flow_runs": {"state": {"type": {"any_": ["PENDING"]}}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["deleted"]) == 1
        assert str(pending_run.id) in result["deleted"]
        assert str(running_run.id) not in result["deleted"]
        assert str(completed_run.id) not in result["deleted"]


class TestFlowRunBulkSetState:
    """Tests for POST /flow_runs/bulk_set_state endpoint."""

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

    async def test_bulk_set_state_verifies_state_change(
        self,
        session,
        flow,
        client,
    ):
        """Test that the state is actually changed in the database."""
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()

        # Set state to cancelled
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {"id": {"any_": [str(flow_run.id)]}},
                "state": {"type": "CANCELLED"},
                "force": True,
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify the state changed
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["state"]["type"] == "CANCELLED"

    async def test_bulk_set_state_with_force(
        self,
        session,
        flow,
        client,
    ):
        """Test force=True bypasses orchestration rules."""
        # Create a completed flow run
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Completed(),
            ),
        )
        await session.commit()

        # Normally COMPLETED -> RUNNING would be rejected, but force=True bypasses
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {"id": {"any_": [str(flow_run.id)]}},
                "state": {"type": "RUNNING"},
                "force": True,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "ACCEPT"
        assert result["results"][0]["state"]["type"] == "RUNNING"

    async def test_bulk_set_state_multiple_flow_runs_different_states(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk state change with flow runs in different states."""
        pending_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="pending-run",
                state=schemas.states.Pending(),
            ),
        )
        running_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="running-run",
                state=schemas.states.Running(),
            ),
        )
        await session.commit()

        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {
                    "id": {"any_": [str(pending_run.id), str(running_run.id)]}
                },
                "state": {"type": "CANCELLED"},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["results"]) == 2

        # Both should be processed (accepted since CANCELLED is valid target)
        for item in result["results"]:
            assert item["status"] == "ACCEPT"
            assert item["state"]["type"] == "CANCELLED"

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

    async def test_bulk_set_state_validation_limit_zero(
        self,
        client,
    ):
        """Test that limit=0 returns 422."""
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {},
                "state": {"type": "CANCELLED"},
                "limit": 0,
            },
        )
        assert response.status_code == 422

    async def test_bulk_set_state_validation_limit_too_high(
        self,
        client,
    ):
        """Test that limit > max returns 422."""
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {},
                "state": {"type": "CANCELLED"},
                "limit": 51,
            },
        )
        assert response.status_code == 422

    async def test_bulk_set_state_by_state_filter(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk state change filtered by current state type."""
        # Create runs in different states
        pending_runs = []
        for i in range(2):
            run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                ),
            )
            pending_runs.append(run)

        running_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Running(),
            ),
        )
        await session.commit()

        # Cancel only PENDING runs
        response = await client.post(
            "/flow_runs/bulk_set_state",
            json={
                "flow_runs": {"state": {"type": {"any_": ["PENDING"]}}},
                "state": {"type": "CANCELLED"},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["results"]) == 2

        # Verify running run was not affected
        response = await client.get(f"/flow_runs/{running_run.id}")
        assert response.json()["state"]["type"] == "RUNNING"


class TestDeploymentBulkDelete:
    """Tests for POST /deployments/bulk_delete endpoint."""

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

    async def test_bulk_delete_verifies_actual_deletion(
        self,
        session,
        flow,
        client,
    ):
        """Test that deleted deployments are actually gone from the database."""
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name=f"test-deployment-{uuid4()}",
                flow_id=flow.id,
            ),
        )
        await session.commit()

        # Delete the deployment
        response = await client.post(
            "/deployments/bulk_delete",
            json={"deployments": {"id": {"any_": [str(deployment.id)]}}},
        )
        assert response.status_code == status.HTTP_200_OK
        assert str(deployment.id) in response.json()["deleted"]

        # Verify it's actually deleted
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

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

    async def test_bulk_delete_deployments_respects_limit(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk delete respects the limit parameter."""
        # Create deployments
        deployments = []
        for i in range(4):
            deployment = await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"test-limit-deployment-{uuid4()}",
                    flow_id=flow.id,
                ),
            )
            deployments.append(deployment)
        await session.commit()

        # Try to delete all with a limit of 2
        response = await client.post(
            "/deployments/bulk_delete",
            json={
                "deployments": {"id": {"any_": [str(d.id) for d in deployments]}},
                "limit": 2,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["deleted"]) == 2

    async def test_bulk_delete_deployments_by_name_filter(
        self,
        session,
        flow,
        client,
    ):
        """Test bulk delete with name filter."""
        unique_prefix = str(uuid4())[:8]
        deployments = []
        for i in range(3):
            deployment = await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"{unique_prefix}-deployment-{i}",
                    flow_id=flow.id,
                ),
            )
            deployments.append(deployment)

        # Create one with different name
        other_deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="other-deployment",
                flow_id=flow.id,
            ),
        )
        await session.commit()

        # Delete by name filter
        response = await client.post(
            "/deployments/bulk_delete",
            json={
                "deployments": {"name": {"like_": f"{unique_prefix}%"}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["deleted"]) == 3
        assert str(other_deployment.id) not in result["deleted"]


class TestDeploymentBulkCreateFlowRun:
    """Tests for POST /deployments/{id}/create_flow_run/bulk endpoint."""

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

    async def test_bulk_create_with_defaults(
        self,
        deployment,
        hosted_api_client,
    ):
        """Test bulk create with default parameters (empty objects)."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[{}, {}, {}],
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 3
        for result in data["results"]:
            assert result["status"] == "CREATED"
            assert result["flow_run_id"] is not None

    async def test_bulk_create_preserves_order(
        self,
        deployment,
        hosted_api_client,
        client,
    ):
        """Results should be returned in the same order as the input."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[
                {"name": "first-run"},
                {"name": "second-run"},
                {"name": "third-run"},
            ],
        )
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]

        # Verify order by fetching each flow run
        for i, expected_name in enumerate(["first-run", "second-run", "third-run"]):
            flow_run_id = results[i]["flow_run_id"]
            fr_response = await client.get(f"/flow_runs/{flow_run_id}")
            assert fr_response.json()["name"] == expected_name

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

    async def test_bulk_create_empty_list_nonexistent_deployment(
        self,
        hosted_api_client,
    ):
        """Empty list with nonexistent deployment should return 404, not 200.

        This verifies that authorization checks run even for empty lists.
        """
        response = await hosted_api_client.post(
            f"/deployments/{uuid4()}/create_flow_run/bulk",
            json=[],
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

    async def test_bulk_create_flow_runs_with_varying_tags(
        self,
        deployment,
        hosted_api_client,
        client,
    ):
        """Test bulk create with different tags for each flow run."""
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[
                {"tags": ["batch-1"]},
                {"tags": ["batch-2"]},
                {"tags": ["batch-3"]},
            ],
        )
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 3

        # Verify each flow run has the correct tag
        for i, result in enumerate(results):
            assert result["status"] == "CREATED"
            fr_response = await client.get(f"/flow_runs/{result['flow_run_id']}")
            assert f"batch-{i + 1}" in fr_response.json()["tags"]

    async def test_bulk_create_inherits_deployment_tags(
        self,
        session,
        flow,
        hosted_api_client,
        client,
    ):
        """Test that flow runs inherit tags from deployment."""
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name=f"tagged-deployment-{uuid4()}",
                flow_id=flow.id,
                tags=["deployment-tag-1", "deployment-tag-2"],
            ),
        )
        await session.commit()

        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run/bulk",
            json=[{"tags": ["run-tag"]}],
        )
        assert response.status_code == status.HTTP_200_OK
        flow_run_id = response.json()["results"][0]["flow_run_id"]

        fr_response = await client.get(f"/flow_runs/{flow_run_id}")
        tags = fr_response.json()["tags"]
        assert "deployment-tag-1" in tags
        assert "deployment-tag-2" in tags
        assert "run-tag" in tags


class TestFlowBulkDelete:
    """Tests for POST /flows/bulk_delete endpoint."""

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

    async def test_bulk_delete_verifies_actual_deletion(
        self,
        session,
        client,
    ):
        """Test that deleted flows are actually gone from the database."""
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-{uuid4()}"),
        )
        await session.commit()

        # Delete the flow
        response = await client.post(
            "/flows/bulk_delete",
            json={"flows": {"id": {"any_": [str(flow.id)]}}},
        )
        assert response.status_code == status.HTTP_200_OK
        assert str(flow.id) in response.json()["deleted"]

        # Verify it's actually deleted
        response = await client.get(f"/flows/{flow.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

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

    async def test_bulk_delete_flows_deletes_multiple_deployments(
        self,
        session,
        client,
    ):
        """Test bulk deletion of flow deletes all its associated deployments."""
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-{uuid4()}"),
        )
        deployment_ids = []
        for i in range(3):
            deployment = await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"test-deployment-{i}",
                    flow_id=flow.id,
                ),
            )
            deployment_ids.append(deployment.id)
        await session.commit()

        # Delete the flow
        response = await client.post(
            "/flows/bulk_delete",
            json={"flows": {"id": {"any_": [str(flow.id)]}}},
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify all deployments are deleted
        for deployment_id in deployment_ids:
            response = await client.get(f"/deployments/{deployment_id}")
            assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_bulk_delete_flows_respects_limit(
        self,
        session,
        client,
    ):
        """Test bulk delete respects the limit parameter."""
        flows = []
        for i in range(4):
            flow = await models.flows.create_flow(
                session=session,
                flow=schemas.core.Flow(name=f"test-limit-flow-{uuid4()}"),
            )
            flows.append(flow)
        await session.commit()

        # Try to delete all with a limit of 2
        response = await client.post(
            "/flows/bulk_delete",
            json={
                "flows": {"id": {"any_": [str(f.id) for f in flows]}},
                "limit": 2,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["deleted"]) == 2

        # Verify only 2 were deleted
        deleted_count = 0
        remaining_count = 0
        for flow in flows:
            response = await client.get(f"/flows/{flow.id}")
            if response.status_code == status.HTTP_404_NOT_FOUND:
                deleted_count += 1
            else:
                remaining_count += 1
        assert deleted_count == 2
        assert remaining_count == 2

    async def test_bulk_delete_nonexistent_flows_returns_empty(
        self,
        client,
    ):
        """Test that bulk delete returns empty list when requested flows don't exist."""
        nonexistent_ids = [str(uuid4()) for _ in range(3)]
        response = await client.post(
            "/flows/bulk_delete",
            json={
                "flows": {"id": {"any_": nonexistent_ids}},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["deleted"] == []


class TestFlowFilterNotAny:
    """Tests for FlowFilter with not_any_ exclusion filter."""

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
                    "name": {"like_": f"%{unique_prefix}%"},
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

    async def test_flow_filter_not_any_with_any(
        self,
        session,
        client,
    ):
        """Test using both any_ and not_any_ together."""
        unique_prefix = str(uuid4())[:8]
        flows = []
        for i in range(4):
            flow = await models.flows.create_flow(
                session=session,
                flow=schemas.core.Flow(name=f"test-combo-flow-{unique_prefix}-{i}"),
            )
            flows.append(flow)
        await session.commit()

        # Include flows 0, 1, 2 but exclude flow 1
        response = await client.post(
            "/flows/filter",
            json={
                "flows": {
                    "id": {
                        "any_": [str(flows[0].id), str(flows[1].id), str(flows[2].id)],
                        "not_any_": [str(flows[1].id)],
                    },
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        flow_ids = [f["id"] for f in data]
        # Should include 0 and 2, but not 1 or 3
        assert str(flows[0].id) in flow_ids
        assert str(flows[1].id) not in flow_ids
        assert str(flows[2].id) in flow_ids
        assert str(flows[3].id) not in flow_ids
