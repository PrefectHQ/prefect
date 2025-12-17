"""
Tests for the ValidateDeploymentConcurrencyAtRunning orchestration rule.
"""

import contextlib
import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseHolder,
    ConcurrencyLimitLeaseMetadata,
    get_concurrency_lease_storage,
)
from prefect.server.database import orm_models
from prefect.server.orchestration.core_policy import (
    CoreFlowPolicy,
    ValidateDeploymentConcurrencyAtRunning,
)
from prefect.server.schemas import states
from prefect.server.schemas.core import ConcurrencyLimitStrategy
from prefect.server.schemas.responses import SetStateStatus


class TestValidateDeploymentConcurrencyAtRunning:
    """Tests for ValidateDeploymentConcurrencyAtRunning orchestration rule."""

    async def create_deployment_with_concurrency_limit(
        self,
        session: AsyncSession,
        limit: int,
        flow: orm_models.Flow,
        grace_period: int = 600,
        collision_strategy: ConcurrencyLimitStrategy = ConcurrencyLimitStrategy.CANCEL_NEW,
    ) -> orm_models.Deployment:
        """Helper to create a deployment with a concurrency limit."""
        deployment_schema = schemas.core.Deployment(
            name=f"test-deployment-{uuid4()}",
            flow_id=flow.id,
            concurrency_limit=limit,
            concurrency_options={
                "collision_strategy": collision_strategy.value,
                "grace_period_seconds": grace_period,
            },
        )

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=deployment_schema,
        )
        await session.flush()
        return deployment

    async def test_copies_lease_id_when_no_validation_needed(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that lease ID is copied when there's no lease to validate."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create a flow run context without a lease
        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={},  # No lease ID
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.proposed_state is not None
        assert ctx.proposed_state.state_details.deployment_concurrency_lease_id is None

    async def test_renews_lease_when_valid(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that a valid lease is renewed successfully."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow, grace_period=60
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create a lease
        assert deployment.concurrency_limit_id is not None
        lease_storage = get_concurrency_lease_storage()
        lease = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )

        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease.id)},
            client_version="3.5.0",
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.proposed_state is not None
        assert (
            ctx.proposed_state.state_details.deployment_concurrency_lease_id == lease.id
        )

    async def test_reacquires_slot_after_lease_expiry(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that a slot is re-acquired when lease has expired."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create a lease and immediately expire it by revoking
        assert deployment.concurrency_limit_id is not None
        lease_storage = get_concurrency_lease_storage()
        lease = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )

        # Revoke the lease to simulate expiry
        await lease_storage.revoke_lease(lease.id)

        # Decrement the active slots to simulate the lease reaper cleanup
        await models.concurrency_limits_v2.bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease.id)},
            client_version="3.5.0",
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.proposed_state is not None
        # Should have a new lease ID after re-acquisition
        new_lease_id = ctx.proposed_state.state_details.deployment_concurrency_lease_id
        assert new_lease_id is not None
        assert new_lease_id != lease.id

    async def test_cancels_when_no_slots_available(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that flow is cancelled when no slots available after lease expiry."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create first lease and let flow1 acquire a slot
        assert deployment.concurrency_limit_id is not None

        # Flow1 initially had a slot
        await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

        lease_storage = get_concurrency_lease_storage()
        lease1 = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )

        # Simulate lease expiry by revoking it (but slot remains occupied by another flow)
        await lease_storage.revoke_lease(lease1.id)
        # Keep the slot occupied to simulate another flow taking it

        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease1.id)},
            client_version="3.5.0",
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state is not None
        assert ctx.validated_state.type == states.StateType.CANCELLED
        assert ctx.validated_state.message is not None
        assert "concurrency slot lost" in ctx.validated_state.message.lower()

    async def test_regression_concurrent_execution_prevention(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """
        Regression test for the core bug: Ensure no concurrency violation occurs
        when a lease expires and another flow takes the slot.

        Scenario:
        1. Flow1 goes PENDING with lease
        2. Lease expires (simulated by revocation)
        3. Flow2 acquires the freed slot
        4. Flow1 tries to go RUNNING
        5. Flow1 should be cancelled (not allowed to run)
        """
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Flow1 gets a lease and slot
        assert deployment.concurrency_limit_id is not None

        # First increment slots for flow1
        await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

        lease_storage = get_concurrency_lease_storage()
        flow1_lease = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )

        # Simulate lease expiry by revoking (reaper would do this)
        # This also decrements the active slots
        await lease_storage.revoke_lease(flow1_lease.id)
        await models.concurrency_limits_v2.bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

        # Flow2 now acquires the freed slot
        flow2_acquired = await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )
        assert flow2_acquired, "Flow2 should be able to acquire the slot"

        # Flow2 gets its own lease
        await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )

        # Now Flow1 tries to transition to RUNNING
        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(flow1_lease.id)},
            client_version="3.5.0",
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        # Flow1 should be cancelled
        assert ctx.response_status == SetStateStatus.REJECT
        assert ctx.validated_state is not None
        assert ctx.validated_state.type == states.StateType.CANCELLED
        assert ctx.validated_state.message is not None
        assert "concurrency slot lost" in ctx.validated_state.message.lower()

        # Verify that only 1 slot is active (Flow2's slot)
        limit = await models.concurrency_limits_v2.read_concurrency_limit(
            session=session,
            concurrency_limit_id=deployment.concurrency_limit_id,
        )
        assert limit is not None
        assert limit.active_slots == 1, "Only Flow2 should have an active slot"

    async def test_skips_validation_for_old_client_versions(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that validation is skipped for client versions < 3.4.11."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create and expire a lease
        assert deployment.concurrency_limit_id is not None
        lease_storage = get_concurrency_lease_storage()
        lease = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )
        # Expire the lease by revoking it
        await lease_storage.revoke_lease(lease.id)

        # Old client version should skip validation and succeed
        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease.id)},
            client_version="3.4.10",  # Old version
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in CoreFlowPolicy.compile_transition_rules(
                ctx.initial_state_type, ctx.proposed_state_type
            ):
                await stack.enter_async_context(rule(ctx, *running_transition))

            await ctx.validate_proposed_state()

        # Should succeed despite expired lease because validation was skipped
        assert ctx.response_status == SetStateStatus.ACCEPT
        # The lease ID should be copied during the transition since validation was skipped
        assert ctx.proposed_state is not None
        assert (
            ctx.proposed_state.state_details.deployment_concurrency_lease_id == lease.id
        )
        # Note: RemoveDeploymentConcurrencyLeaseForOldClientVersions will remove the lease
        # in its after_transition hook, but that's not reflected in proposed_state

    async def test_default_client_version_to_2_0_0(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that missing client version defaults to 2.0.0 and skips validation."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create and expire a lease
        assert deployment.concurrency_limit_id is not None
        lease_storage = get_concurrency_lease_storage()
        lease = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )
        # Expire the lease by revoking it
        await lease_storage.revoke_lease(lease.id)

        # No client version provided - should default to 2.0.0
        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease.id)},
            # No client_version in parameters
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        # Should succeed and just copy the lease ID (no validation for old version)
        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.proposed_state is not None
        # Lease ID should be copied even though it's expired (no validation occurred)
        assert (
            ctx.proposed_state.state_details.deployment_concurrency_lease_id == lease.id
        )

    async def test_concurrent_reacquisition_only_one_succeeds(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that when multiple flows try to re-acquire after expiry, only one succeeds."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create two flows with leases
        assert deployment.concurrency_limit_id is not None
        lease_storage = get_concurrency_lease_storage()

        # Create leases for both flows
        lease1 = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )
        lease2 = await lease_storage.create_lease(
            resource_ids=[deployment.concurrency_limit_id],
            ttl=datetime.timedelta(seconds=60),
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="flow_run", id=str(uuid4())),
            ),
        )

        # Expire both leases
        await lease_storage.revoke_lease(lease1.id)
        await lease_storage.revoke_lease(lease2.id)

        # Set up two orchestration contexts
        ctx1 = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease1.id)},
            client_version="3.5.0",
        )
        ctx2 = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": str(lease2.id)},
            client_version="3.5.0",
        )

        # Try to transition both to RUNNING
        # First one should succeed in re-acquiring
        async with contextlib.AsyncExitStack() as stack:
            ctx1 = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx1, *running_transition)
            )
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT
        assert ctx1.proposed_state is not None
        new_lease_id1 = (
            ctx1.proposed_state.state_details.deployment_concurrency_lease_id
        )
        assert new_lease_id1 is not None
        assert new_lease_id1 != lease1.id  # Got a new lease

        # Second one should be cancelled (no slots available)
        async with contextlib.AsyncExitStack() as stack:
            ctx2 = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx2, *running_transition)
            )
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.REJECT
        assert ctx2.validated_state is not None
        assert ctx2.validated_state.type == states.StateType.CANCELLED
        assert ctx2.validated_state.message is not None
        assert "concurrency slot lost" in ctx2.validated_state.message.lower()

    async def test_handles_no_lease_id(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that rule handles case when there's no lease ID."""
        deployment = await self.create_deployment_with_concurrency_limit(
            session, 1, flow
        )
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={},  # No lease ID
            client_version="3.5.0",
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.proposed_state is not None
        assert ctx.proposed_state.state_details.deployment_concurrency_lease_id is None

    async def test_handles_no_deployment_concurrency_limit(
        self,
        session: AsyncSession,
        initialize_orchestration,
        flow: orm_models.Flow,
    ):
        """Test that rule handles deployments without concurrency limits."""
        # Create deployment without concurrency limit
        deployment_schema = schemas.core.Deployment(
            name=f"test-deployment-{uuid4()}",
            flow_id=flow.id,
        )
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=deployment_schema,
        )
        await session.flush()

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Create a dummy lease ID (shouldn't be validated since no limit exists)
        fake_lease_id = str(uuid4())

        ctx = await initialize_orchestration(
            session,
            "flow",
            *running_transition,
            deployment_id=deployment.id,
            initial_details={"deployment_concurrency_lease_id": fake_lease_id},
            client_version="3.5.0",
        )

        async with contextlib.AsyncExitStack() as stack:
            ctx = await stack.enter_async_context(
                ValidateDeploymentConcurrencyAtRunning(ctx, *running_transition)
            )
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT
        assert ctx.proposed_state is not None
        # Lease ID should be copied even though deployment has no limit
        assert ctx.proposed_state.state_details.deployment_concurrency_lease_id == UUID(
            fake_lease_id
        )
