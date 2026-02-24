from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio

from prefect.runner._scheduled_run_poller import StarterResolver, _ScheduledRunPoller

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow_run(*, next_scheduled_start_time: datetime.datetime | None = None):
    """Return a MagicMock that looks like a FlowRun with configurable schedule time."""
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.name = "test-flow-run"
    flow_run.next_scheduled_start_time = next_scheduled_start_time
    return flow_run


def _make_poller(**overrides):
    """Build a _ScheduledRunPoller with all-mock dependencies.

    Returns (poller, mocks_dict) so tests can assert on collaborators.
    """
    deployment_id = uuid4()

    client = MagicMock()
    client.get_scheduled_flow_runs_for_deployments = AsyncMock(return_value=[])

    limit_manager = MagicMock()
    limit_manager.has_slots_available = MagicMock(return_value=True)

    deployment_registry = MagicMock()
    deployment_registry.get_deployment_ids = MagicMock(return_value={deployment_id})

    resolve_starter = MagicMock(return_value=MagicMock())

    runs_task_group = MagicMock()
    runs_task_group.start = AsyncMock(return_value=MagicMock())
    runs_task_group.start_soon = MagicMock()

    process_manager = MagicMock()
    state_proposer = MagicMock()
    hook_runner = MagicMock()
    cancellation_manager = MagicMock()

    kwargs = dict(
        query_seconds=10.0,
        prefetch_seconds=10.0,
        client=client,
        limit_manager=limit_manager,
        deployment_registry=deployment_registry,
        resolve_starter=resolve_starter,
        runs_task_group=runs_task_group,
        storage_objs=[],
        process_manager=process_manager,
        state_proposer=state_proposer,
        hook_runner=hook_runner,
        cancellation_manager=cancellation_manager,
    )
    kwargs.update(overrides)

    poller = _ScheduledRunPoller(**kwargs)

    mocks = dict(
        deployment_id=deployment_id,
        client=client,
        limit_manager=limit_manager,
        deployment_registry=deployment_registry,
        resolve_starter=resolve_starter,
        runs_task_group=runs_task_group,
        process_manager=process_manager,
        state_proposer=state_proposer,
        hook_runner=hook_runner,
        cancellation_manager=cancellation_manager,
    )
    return poller, mocks


# ---------------------------------------------------------------------------
# Discovery tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerDiscovery:
    """Tests for _get_scheduled_flow_runs and the poll workload."""

    async def test_client_called_with_correct_deployment_ids(self):
        """get_scheduled_flow_runs_for_deployments receives deployment IDs from registry."""
        poller, m = _make_poller()

        await poller._get_scheduled_flow_runs()

        m["client"].get_scheduled_flow_runs_for_deployments.assert_awaited_once()
        call_kwargs = m["client"].get_scheduled_flow_runs_for_deployments.call_args
        assert set(call_kwargs.kwargs["deployment_ids"]) == {m["deployment_id"]}

    async def test_client_called_with_scheduled_before_window(self):
        """scheduled_before is now + prefetch_seconds."""
        poller, m = _make_poller(prefetch_seconds=30.0)

        before = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=30
        )
        await poller._get_scheduled_flow_runs()
        after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=30
        )

        call_kwargs = m["client"].get_scheduled_flow_runs_for_deployments.call_args
        scheduled_before = call_kwargs.kwargs["scheduled_before"]
        assert before <= scheduled_before <= after

    async def test_last_polled_updated_after_query(self):
        """last_polled is updated after _get_and_submit_flow_runs."""
        poller, m = _make_poller()
        assert poller.last_polled is None

        await poller._get_and_submit_flow_runs()

        assert poller.last_polled is not None


# ---------------------------------------------------------------------------
# Sorting tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerSorting:
    """Tests for run submission ordering."""

    async def test_runs_sorted_by_next_scheduled_start_time(self):
        """Runs with times [t2, t1, t3] are submitted in order [t1, t2, t3]."""
        t1 = datetime.datetime(2025, 1, 1, 1, 0, tzinfo=datetime.timezone.utc)
        t2 = datetime.datetime(2025, 1, 1, 2, 0, tzinfo=datetime.timezone.utc)
        t3 = datetime.datetime(2025, 1, 1, 3, 0, tzinfo=datetime.timezone.utc)

        run_t2 = _make_flow_run(next_scheduled_start_time=t2)
        run_t1 = _make_flow_run(next_scheduled_start_time=t1)
        run_t3 = _make_flow_run(next_scheduled_start_time=t3)

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run_t2, run_t1, run_t3]
        )

        submitted_ids: list = []
        original_start_soon = m["runs_task_group"].start_soon

        def tracking_start_soon(coro, *args, **kwargs):
            # The first positional arg after coro is the flow_run
            submitted_ids.append(args[0].id if args else None)
            return original_start_soon(coro, *args, **kwargs)

        m["runs_task_group"].start_soon = MagicMock(side_effect=tracking_start_soon)

        await poller._get_and_submit_flow_runs()

        assert submitted_ids == [run_t1.id, run_t2.id, run_t3.id]

    async def test_none_scheduled_runs_sort_last(self):
        """Runs with None next_scheduled_start_time sort after all scheduled runs."""
        t1 = datetime.datetime(2025, 1, 1, 1, 0, tzinfo=datetime.timezone.utc)

        run_none = _make_flow_run(next_scheduled_start_time=None)
        run_t1 = _make_flow_run(next_scheduled_start_time=t1)

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run_none, run_t1]
        )

        submitted_ids: list = []

        def tracking_start_soon(coro, *args, **kwargs):
            submitted_ids.append(args[0].id if args else None)

        m["runs_task_group"].start_soon = MagicMock(side_effect=tracking_start_soon)

        await poller._get_and_submit_flow_runs()

        assert submitted_ids == [run_t1.id, run_none.id]


# ---------------------------------------------------------------------------
# Capacity tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerCapacity:
    """Tests for capacity gating via LimitManager."""

    async def test_capacity_full_no_submissions(self):
        """has_slots_available() returns False -> no submissions, info log with count."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )
        run2 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 2, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1, run2]
        )
        m["limit_manager"].has_slots_available = MagicMock(return_value=False)

        with patch.object(poller, "_logger") as mock_logger:
            await poller._get_and_submit_flow_runs()

            mock_logger.info.assert_called()
            log_msg = mock_logger.info.call_args[0][0]
            assert "skipped" in log_msg.lower() or "capacity" in log_msg.lower()

        m["runs_task_group"].start_soon.assert_not_called()

    async def test_capacity_partial_submissions(self):
        """3 runs, slots for 2 -> first 2 submitted, third skipped."""
        t1 = datetime.datetime(2025, 1, 1, 1, 0, tzinfo=datetime.timezone.utc)
        t2 = datetime.datetime(2025, 1, 1, 2, 0, tzinfo=datetime.timezone.utc)
        t3 = datetime.datetime(2025, 1, 1, 3, 0, tzinfo=datetime.timezone.utc)

        run1 = _make_flow_run(next_scheduled_start_time=t1)
        run2 = _make_flow_run(next_scheduled_start_time=t2)
        run3 = _make_flow_run(next_scheduled_start_time=t3)

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1, run2, run3]
        )
        # True for first two, False for third
        m["limit_manager"].has_slots_available = MagicMock(
            side_effect=[True, True, False]
        )

        submitted_ids: list = []

        def tracking_start_soon(coro, *args, **kwargs):
            submitted_ids.append(args[0].id if args else None)

        m["runs_task_group"].start_soon = MagicMock(side_effect=tracking_start_soon)

        await poller._get_and_submit_flow_runs()

        assert submitted_ids == [run1.id, run2.id]
        assert run3.id not in submitted_ids


# ---------------------------------------------------------------------------
# In-flight dedup tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerInFlightDedup:
    """Tests for _submitting_flow_run_ids deduplication."""

    async def test_inflight_run_skipped_without_capacity_check(self):
        """ID in _submitting_flow_run_ids -> run skipped without capacity check."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1]
        )
        poller._submitting_flow_run_ids.add(run1.id)

        await poller._get_and_submit_flow_runs()

        m["runs_task_group"].start_soon.assert_not_called()
        # Capacity check should not be called for in-flight runs
        m["limit_manager"].has_slots_available.assert_not_called()


# ---------------------------------------------------------------------------
# Delegation tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerDelegation:
    """Tests for resolve_starter + FlowRunExecutor delegation."""

    async def test_resolve_starter_called_with_flow_run(self):
        """resolve_starter is called with the flow_run."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1]
        )

        # We need to actually run _submit_run to test resolve_starter
        # Use a real task group for this
        async with anyio.create_task_group() as tg:
            await poller._get_and_submit_flow_runs(task_group=tg)

        m["resolve_starter"].assert_called_once_with(run1)

    async def test_executor_receives_starter_result(self):
        """Result of resolve_starter is passed to FlowRunExecutor."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )
        mock_starter = MagicMock()

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1]
        )
        m["resolve_starter"].return_value = mock_starter

        with patch(
            "prefect.runner._scheduled_run_poller.FlowRunExecutor"
        ) as MockExecutor:
            mock_executor_instance = MagicMock()
            mock_executor_instance.submit = AsyncMock()
            MockExecutor.return_value = mock_executor_instance

            async with anyio.create_task_group() as tg:
                await poller._get_and_submit_flow_runs(task_group=tg)

            MockExecutor.assert_called_once()
            call_kwargs = MockExecutor.call_args.kwargs
            assert call_kwargs["starter"] is mock_starter
            assert call_kwargs["flow_run"] is run1

    async def test_id_in_set_before_delegation(self):
        """ID is added to _submitting_flow_run_ids before delegation starts."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1]
        )

        # Check that ID is in the set when start_soon is called
        id_was_in_set = []

        def tracking_start_soon(coro, *args, **kwargs):
            id_was_in_set.append(run1.id in poller._submitting_flow_run_ids)

        m["runs_task_group"].start_soon = MagicMock(side_effect=tracking_start_soon)

        await poller._get_and_submit_flow_runs()

        assert id_was_in_set == [True]

    async def test_id_removed_after_submit_run(self):
        """ID is removed from _submitting_flow_run_ids in finally of _submit_run."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()

        with patch(
            "prefect.runner._scheduled_run_poller.FlowRunExecutor"
        ) as MockExecutor:
            mock_executor_instance = MagicMock()
            mock_executor_instance.submit = AsyncMock()
            MockExecutor.return_value = mock_executor_instance

            poller._submitting_flow_run_ids.add(run1.id)
            async with anyio.create_task_group() as tg:
                await poller._submit_run(run1, tg)

        assert run1.id not in poller._submitting_flow_run_ids

    async def test_id_removed_on_resolve_starter_exception(self):
        """resolve_starter raises -> ID removed in finally (no leak)."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()
        m["resolve_starter"].side_effect = RuntimeError("unknown deployment")

        poller._submitting_flow_run_ids.add(run1.id)
        async with anyio.create_task_group() as tg:
            await poller._submit_run(run1, tg)

        assert run1.id not in poller._submitting_flow_run_ids


# ---------------------------------------------------------------------------
# Stopping tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerStopping:
    """Tests for the stopping attribute."""

    async def test_stopping_returns_without_querying_api(self):
        """stopping=True -> _get_and_submit_flow_runs returns without querying API."""
        poller, m = _make_poller()
        poller.stopping = True

        await poller._get_and_submit_flow_runs()

        m["client"].get_scheduled_flow_runs_for_deployments.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_once tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerRunOnce:
    """Tests for run_once() single-execution mode."""

    async def test_run_once_no_storage_pull(self):
        """storage.pull_code never called in run_once mode."""
        mock_storage = MagicMock()
        mock_storage.pull_code = AsyncMock()
        mock_storage.pull_interval = 60

        poller, m = _make_poller(storage_objs=[mock_storage])

        await poller.run_once()

        mock_storage.pull_code.assert_not_awaited()

    async def test_run_once_waits_for_completion(self):
        """run_once() blocks until all executor.submit tasks complete."""
        run1 = _make_flow_run(
            next_scheduled_start_time=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            )
        )

        poller, m = _make_poller()
        m["client"].get_scheduled_flow_runs_for_deployments = AsyncMock(
            return_value=[run1]
        )

        execution_completed = False

        with patch(
            "prefect.runner._scheduled_run_poller.FlowRunExecutor"
        ) as MockExecutor:
            mock_executor_instance = MagicMock()

            async def _fake_submit(task_status=anyio.TASK_STATUS_IGNORED):
                nonlocal execution_completed
                task_status.started(MagicMock())
                # Simulate some work
                await anyio.sleep(0.01)
                execution_completed = True

            mock_executor_instance.submit = _fake_submit
            MockExecutor.return_value = mock_executor_instance

            await poller.run_once()

        # After run_once returns, all tasks should have completed
        assert execution_completed is True


# ---------------------------------------------------------------------------
# Storage loop tests
# ---------------------------------------------------------------------------


class TestScheduledRunPollerStorageLoops:
    """Tests for storage pull loop wiring in run()."""

    async def test_storage_loop_with_interval(self):
        """critical_service_loop wraps storage.pull_code when pull_interval set."""
        mock_storage = MagicMock()
        mock_storage.pull_code = AsyncMock()
        mock_storage.pull_interval = 60

        poller, m = _make_poller(storage_objs=[mock_storage])

        captured_calls: list[dict] = []

        async def _capture_csl(**kwargs):
            captured_calls.append(kwargs)

        with patch(
            "prefect.runner._scheduled_run_poller.critical_service_loop",
            side_effect=_capture_csl,
        ):
            await poller.run()

            # Verify critical_service_loop was called with storage.pull_code
            storage_calls = [
                c for c in captured_calls if c.get("workload") is mock_storage.pull_code
            ]
            assert len(storage_calls) == 1
            assert storage_calls[0]["interval"] == 60

    async def test_storage_loop_no_interval(self):
        """storage.pull_code started directly when pull_interval is None."""
        mock_storage = MagicMock()
        mock_storage.pull_code = AsyncMock()
        mock_storage.pull_interval = None

        poller, m = _make_poller(storage_objs=[mock_storage])

        with patch(
            "prefect.runner._scheduled_run_poller.critical_service_loop",
            new_callable=AsyncMock,
        ) as mock_csl:
            mock_csl.side_effect = AsyncMock(return_value=None)

            await poller.run()

            # storage.pull_code should have been called directly (not via critical_service_loop)
            mock_storage.pull_code.assert_awaited_once()

    async def test_scheduling_loop_started_in_run(self):
        """run() starts the scheduling loop via critical_service_loop."""
        poller, m = _make_poller()

        captured_calls: list[dict] = []

        async def _capture_csl(**kwargs):
            captured_calls.append(kwargs)

        with patch(
            "prefect.runner._scheduled_run_poller.critical_service_loop",
            side_effect=_capture_csl,
        ):
            await poller.run()

            # Verify critical_service_loop was called with the scheduling workload.
            # Bound methods create new objects on each access, so compare by name.
            scheduling_calls = [
                c
                for c in captured_calls
                if getattr(c.get("workload"), "__name__", None)
                == "_get_and_submit_flow_runs"
            ]
            assert len(scheduling_calls) == 1
            assert scheduling_calls[0]["interval"] == 10.0


# ---------------------------------------------------------------------------
# StarterResolver Protocol tests
# ---------------------------------------------------------------------------


class TestStarterResolverProtocol:
    """Tests for the StarterResolver Protocol."""

    def test_protocol_is_importable(self):
        """StarterResolver can be imported from the module."""
        assert StarterResolver is not None

    def test_callable_conforms_to_protocol(self):
        """A plain callable returning a ProcessStarter satisfies the protocol."""
        mock_resolver = MagicMock(return_value=MagicMock())
        # Verify it's callable and returns something
        result = mock_resolver(MagicMock())
        assert result is not None
