"""
Tests for V2 Global Concurrency Limits integration in task orchestration rules.

These tests cover the integration between tag-based task concurrency (V1) and
Global Concurrency Limits V2 in SecureTaskConcurrencySlots and ReleaseTaskConcurrencySlots.
"""

import contextlib
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.concurrency.lease_storage import get_concurrency_lease_storage
from prefect.server.database.orm_models import ConcurrencyLimitV2
from prefect.server.models import concurrency_limits, concurrency_limits_v2
from prefect.server.orchestration.core_policy import (
    ReleaseTaskConcurrencySlots,
    SecureTaskConcurrencySlots,
)
from prefect.server.schemas import actions, core, states
from prefect.server.schemas.responses import SetStateStatus


class TestSecureTaskConcurrencySlotsV2Integration:
    """Test SecureTaskConcurrencySlots with V2 Global Concurrency Limits."""

    async def create_v1_concurrency_limit(
        self, session: AsyncSession, tag: str, limit: int
    ) -> None:
        """Helper to create a V1 concurrency limit."""
        cl_create = actions.ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=limit,
        ).model_dump(mode="json")

        cl_model = core.ConcurrencyLimit(**cl_create)
        await concurrency_limits.create_concurrency_limit(
            session=session, concurrency_limit=cl_model
        )

    async def create_v2_concurrency_limit(
        self, session: AsyncSession, tag: str, limit: int
    ) -> ConcurrencyLimitV2:
        """Helper to create a V2 concurrency limit."""
        gcl = await concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=actions.ConcurrencyLimitV2Create(
                name=f"tag:{tag}",
                limit=limit,
                active=True,
            ),
        )
        return gcl

    async def test_v2_limits_take_priority_over_v1(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that V2 limits are processed before V1 limits for the same tag."""
        # Create both V1 and V2 limits for the same tag
        await self.create_v1_concurrency_limit(session, "shared-tag", 2)
        v2_limit = await self.create_v2_concurrency_limit(session, "shared-tag", 1)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # First task should use V2 limit (limit 1) not V1 limit (limit 2)
        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["shared-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        # Check that V2 limit has 1 active slot
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 1

        # Second task should be delayed because V2 limit is reached (limit 1)
        ctx2 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["shared-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.WAIT

    async def test_v2_zero_limit_aborts_transition(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that V2 limits with zero limit abort transitions."""
        await self.create_v2_concurrency_limit(session, "zero-tag", 0)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["zero-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ABORT
        assert "is 0 and will deadlock" in ctx.response_details.reason

    async def test_v2_lease_creation_and_metadata(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that V2 limits create proper leases with metadata."""
        v2_limit = await self.create_v2_concurrency_limit(session, "lease-tag", 2)

        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["lease-tag"]
        )

        # Use the rule with try/finally to ensure cleanup happens
        rule = SecureTaskConcurrencySlots(ctx, *running_transition)
        try:
            async with rule as rule_ctx:
                await rule_ctx.validate_proposed_state()

            assert ctx.response_status == SetStateStatus.ACCEPT

            # Verify V2 limit active slots were incremented
            await session.refresh(v2_limit)
            assert v2_limit.active_slots == 1

            # Verify lease was created - check the rule's internal tracking
            assert len(rule._acquired_v2_lease_ids) == 1
            lease_id = rule._acquired_v2_lease_ids[0]

            # Verify lease exists and has proper metadata
            lease_storage = get_concurrency_lease_storage()
            lease = await lease_storage.read_lease(lease_id=lease_id)
            assert lease is not None
            assert lease.metadata is not None
            assert lease.metadata.slots == 1
            assert lease.metadata.holder.type == "task_run"
            assert lease.metadata.holder.id == ctx.run.id

        finally:
            # Cleanup happens in rule's cleanup method
            pass

    async def test_mixed_v1_v2_tags_on_same_task(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test task with both V1 and V2 tags processes V2 first, then V1."""
        # Create V2 limit for one tag, V1 for another
        v2_limit = await self.create_v2_concurrency_limit(session, "v2-tag", 1)
        await self.create_v1_concurrency_limit(session, "v1-tag", 1)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["v2-tag", "v1-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

        # Verify V2 limit was used
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 1

        # Verify V1 limit was also used (should have the task run ID in active_slots)
        v1_limit = await concurrency_limits.read_concurrency_limit_by_tag(
            session, "v1-tag"
        )
        assert str(ctx.run.id) in v1_limit.active_slots

    async def test_v2_lease_cleanup_on_abort(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that V2 leases are properly cleaned up when transition is aborted."""
        # Create a zero limit which will trigger abort immediately
        zero_limit = await self.create_v2_concurrency_limit(session, "zero-tag", 0)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["zero-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ABORT

        # Verify zero limit is still zero - no slots should have been acquired
        await session.refresh(zero_limit)
        assert zero_limit.active_slots == 0

    async def test_v1_limits_processed_when_no_v2_overlap(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that V1 limits are still processed for tags without V2 limits."""
        # Create V2 limit for one tag, V1 for different tags
        await self.create_v2_concurrency_limit(session, "v2-only", 2)
        await self.create_v1_concurrency_limit(session, "v1-only", 1)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        # Test with only V1 tag
        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["v1-only"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        # Verify V1 limit was used
        v1_limit = await concurrency_limits.read_concurrency_limit_by_tag(
            session, "v1-only"
        )
        assert str(ctx1.run.id) in v1_limit.active_slots

        # Test second task hits V1 limit
        ctx2 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["v1-only"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *running_transition))
            await ctx2.validate_proposed_state()

        assert ctx2.response_status == SetStateStatus.WAIT

    async def test_v2_inactive_limits_ignored(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that inactive V2 limits are ignored."""
        # Create inactive V2 limit and active V1 limit for same tag
        v2_limit = await concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=actions.ConcurrencyLimitV2Create(
                name="tag:inactive-tag",
                limit=1,
                active=False,  # Inactive
            ),
        )
        await self.create_v1_concurrency_limit(session, "inactive-tag", 2)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["inactive-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

        # Verify V2 limit was not used (should be 0 active slots)
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 0

        # Verify V1 limit was used instead
        v1_limit = await concurrency_limits.read_concurrency_limit_by_tag(
            session, "inactive-tag"
        )
        assert str(ctx.run.id) in v1_limit.active_slots

    async def test_v2_tags_excluded_from_v1_processing(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that tags with V2 limits are excluded from V1 processing."""
        # Create both V2 and V1 limits for the same tag
        v2_limit = await self.create_v2_concurrency_limit(session, "shared-tag", 5)
        await self.create_v1_concurrency_limit(session, "shared-tag", 2)

        concurrency_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["shared-tag"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in concurrency_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

        # V2 limit should be used
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 1

        # V1 limit should NOT be used (active_slots should be empty)
        v1_limit = await concurrency_limits.read_concurrency_limit_by_tag(
            session, "shared-tag"
        )
        assert str(ctx.run.id) not in v1_limit.active_slots
        assert len(v1_limit.active_slots) == 0


class TestReleaseTaskConcurrencySlotsV2Integration:
    """Test ReleaseTaskConcurrencySlots with V2 Global Concurrency Limits.

    Note: Some of these tests may fail due to a bug in the current implementation
    where holder.id (task run ID) is used as lease_id in the release logic.
    The correct behavior would require finding the lease_id associated with a holder.
    """

    async def create_v2_concurrency_limit(
        self, session: AsyncSession, tag: str, limit: int
    ) -> ConcurrencyLimitV2:
        """Helper to create a V2 concurrency limit."""
        return await concurrency_limits_v2.create_concurrency_limit(
            session=session,
            concurrency_limit=actions.ConcurrencyLimitV2Create(
                name=f"tag:{tag}",
                limit=limit,
                active=True,
            ),
        )

    async def test_v2_and_v1_integration_full_cycle(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test full cycle: secure V2+V1 limits, then release both."""
        # Set up both V2 and V1 limits
        v2_limit = await self.create_v2_concurrency_limit(session, "cycle-v2", 2)

        cl_create = actions.ConcurrencyLimitCreate(
            tag="cycle-v1",
            concurrency_limit=2,
        ).model_dump(mode="json")
        cl_model = core.ConcurrencyLimit(**cl_create)
        await concurrency_limits.create_concurrency_limit(
            session=session, concurrency_limit=cl_model
        )

        # Test acquiring slots
        secure_policy = [SecureTaskConcurrencySlots]
        release_policy = [ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        # Task gets both V2 and V1 tags
        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["cycle-v2", "cycle-v1"]
        )

        # Secure slots
        async with contextlib.AsyncExitStack() as stack:
            for rule in secure_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT

        # Verify both limits were used
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 1

        v1_limit = await concurrency_limits.read_concurrency_limit_by_tag(
            session, "cycle-v1"
        )
        assert str(ctx1.run.id) in v1_limit.active_slots

        # Now complete the task to release slots
        ctx2 = await initialize_orchestration(
            session,
            "task",
            *completed_transition,
            run_override=ctx1.run,  # Same task run
            run_tags=["cycle-v2", "cycle-v1"],
        )

        # Set validated state to completed (normally done by orchestration)
        ctx2.validated_state = states.State(type=states.StateType.COMPLETED)

        async with contextlib.AsyncExitStack() as stack:
            for rule in release_policy:
                ctx2 = await stack.enter_async_context(
                    rule(ctx2, *completed_transition)
                )

        # Verify slots were released
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 0

        await session.refresh(v1_limit)
        assert str(ctx1.run.id) not in v1_limit.active_slots

    async def test_release_only_on_terminal_transitions(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that slots are only released on terminal transitions."""
        v2_limit = await self.create_v2_concurrency_limit(session, "terminal-test", 2)

        # First acquire a slot
        secure_policy = [SecureTaskConcurrencySlots]
        release_policy = [ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx1 = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["terminal-test"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in secure_policy:
                ctx1 = await stack.enter_async_context(rule(ctx1, *running_transition))
            await ctx1.validate_proposed_state()

        assert ctx1.response_status == SetStateStatus.ACCEPT
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 1

        # Do a terminal transition (running to completed - should release)
        terminal_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        ctx2 = await initialize_orchestration(
            session,
            "task",
            *terminal_transition,
            run_override=ctx1.run,
            run_tags=["terminal-test"],
        )

        # Set validated state to completed (normally done by orchestration)
        ctx2.validated_state = states.State(type=states.StateType.COMPLETED)

        async with contextlib.AsyncExitStack() as stack:
            for rule in release_policy:
                ctx2 = await stack.enter_async_context(rule(ctx2, *terminal_transition))

        # Verify slots were released on terminal transition
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 0

    async def test_v2_release_with_no_matching_holders(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that release handles case where no holders match the task run."""
        v2_limit = await self.create_v2_concurrency_limit(session, "no-match", 2)

        release_policy = [ReleaseTaskConcurrencySlots]
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        # Task that doesn't have any leases
        ctx = await initialize_orchestration(
            session, "task", *completed_transition, run_tags=["no-match"]
        )

        # This should not raise any errors
        async with contextlib.AsyncExitStack() as stack:
            for rule in release_policy:
                ctx = await stack.enter_async_context(rule(ctx, *completed_transition))

        # No slots should be affected since no leases existed
        await session.refresh(v2_limit)
        assert v2_limit.active_slots == 0

    async def test_v2_limits_with_multiple_tags(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that a task with multiple V2 tags processes all limits."""
        v2_limit1 = await self.create_v2_concurrency_limit(session, "multi-1", 2)
        v2_limit2 = await self.create_v2_concurrency_limit(session, "multi-2", 3)

        secure_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["multi-1", "multi-2"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in secure_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        assert ctx.response_status == SetStateStatus.ACCEPT

        # Both limits should have active slots
        await session.refresh(v2_limit1)
        await session.refresh(v2_limit2)
        assert v2_limit1.active_slots == 1
        assert v2_limit2.active_slots == 1

    async def test_v2_slot_increment_lease_creation_atomicity(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """
        Test that slot increments and lease creation are atomic in orchestration policy.
        This test verifies the fix for the zombie slot bug where slots could be
        incremented but leases not created due to session/transaction boundary issues.
        The fix ensures both operations happen in a single transaction context.
        """
        # Create two limits with different capacities
        v2_limit_5 = await self.create_v2_concurrency_limit(session, "limit-5", 5)
        v2_limit_10 = await self.create_v2_concurrency_limit(session, "limit-10", 10)

        secure_policy = [SecureTaskConcurrencySlots]
        release_policy = [ReleaseTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)
        completed_transition = (states.StateType.RUNNING, states.StateType.COMPLETED)

        # Run 5 tasks to fill the smaller limit and use slots from both limits
        task_contexts = []
        for _ in range(5):
            task_ctx = await initialize_orchestration(
                session,
                "task",
                *running_transition,
                run_tags=["limit-5", "limit-10"],
            )

            async with contextlib.AsyncExitStack() as stack:
                for rule in secure_policy:
                    task_ctx = await stack.enter_async_context(
                        rule(task_ctx, *running_transition)
                    )
                await task_ctx.validate_proposed_state()

            # Each task should be accepted and increment both limits
            assert task_ctx.response_status == SetStateStatus.ACCEPT
            task_contexts.append(task_ctx)

        # Verify both limits have the expected slots and leases
        await session.refresh(v2_limit_5)
        await session.refresh(v2_limit_10)
        assert v2_limit_5.active_slots == 5
        assert v2_limit_10.active_slots == 5

        # Count leases via lease storage
        lease_storage = get_concurrency_lease_storage()
        limit_5_holders = await lease_storage.list_holders_for_limit(v2_limit_5.id)
        limit_10_holders = await lease_storage.list_holders_for_limit(v2_limit_10.id)
        assert len(limit_5_holders) == 5
        assert len(limit_10_holders) == 5

        # 6th task should be blocked because limit-5 is full
        blocked_task_ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["limit-5", "limit-10"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in secure_policy:
                blocked_task_ctx = await stack.enter_async_context(
                    rule(blocked_task_ctx, *running_transition)
                )
            await blocked_task_ctx.validate_proposed_state()

        # Should be blocked - no partial increments should occur
        assert blocked_task_ctx.response_status == SetStateStatus.WAIT

        # Slots should remain the same (no zombie slots created)
        await session.refresh(v2_limit_5)
        await session.refresh(v2_limit_10)
        assert v2_limit_5.active_slots == 5
        assert v2_limit_10.active_slots == 5

        # Complete all tasks to verify proper cleanup atomicity
        for task_ctx in task_contexts:
            completed_ctx = await initialize_orchestration(
                session,
                "task",
                *completed_transition,
                run_override=task_ctx.run,
                run_tags=["limit-5", "limit-10"],
            )

            # Set validated state to completed (normally done by orchestration)
            completed_ctx.validated_state = states.State(
                type=states.StateType.COMPLETED
            )

            async with contextlib.AsyncExitStack() as stack:
                for rule in release_policy:
                    completed_ctx = await stack.enter_async_context(
                        rule(completed_ctx, *completed_transition)
                    )

        # Both limits should be completely cleaned up
        await session.refresh(v2_limit_5)
        await session.refresh(v2_limit_10)
        assert v2_limit_5.active_slots == 0
        assert v2_limit_10.active_slots == 0

        # Verify leases were cleaned up
        limit_5_holders = await lease_storage.list_holders_for_limit(v2_limit_5.id)
        limit_10_holders = await lease_storage.list_holders_for_limit(v2_limit_10.id)
        assert len(limit_5_holders) == 0
        assert len(limit_10_holders) == 0

        # Now the previously blocked task should be able to run
        retry_task_ctx = await initialize_orchestration(
            session,
            "task",
            *running_transition,
            run_override=blocked_task_ctx.run,
            run_tags=["limit-5", "limit-10"],
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in secure_policy:
                retry_task_ctx = await stack.enter_async_context(
                    rule(retry_task_ctx, *running_transition)
                )
            await retry_task_ctx.validate_proposed_state()

        assert retry_task_ctx.response_status == SetStateStatus.ACCEPT
        await session.refresh(v2_limit_5)
        await session.refresh(v2_limit_10)
        assert v2_limit_5.active_slots == 1
        assert v2_limit_10.active_slots == 1

    async def test_v2_limit_prevents_exceeding_capacity(
        self,
        session: AsyncSession,
        initialize_orchestration: Callable[..., Any],
    ) -> None:
        """Test that V2 limits prevent tasks from exceeding capacity."""
        v2_limit = await self.create_v2_concurrency_limit(session, "capacity-test", 1)

        # First, manually fill the limit to capacity
        await concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[v2_limit.id],
            slots=1,
        )

        secure_policy = [SecureTaskConcurrencySlots]
        running_transition = (states.StateType.PENDING, states.StateType.RUNNING)

        ctx = await initialize_orchestration(
            session, "task", *running_transition, run_tags=["capacity-test"]
        )

        async with contextlib.AsyncExitStack() as stack:
            for rule in secure_policy:
                ctx = await stack.enter_async_context(rule(ctx, *running_transition))
            await ctx.validate_proposed_state()

        # Should be told to wait since capacity is already reached
        assert ctx.response_status == SetStateStatus.WAIT
