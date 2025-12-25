# Worker-Side Flow Run Cancellation

## Overview

This plan describes re-implementing flow run cancellation handling in workers. This capability was previously removed in PR #14611 (July 2024) when cancellation responsibility was consolidated into the Runner. However, the Runner can only handle cancellation when it is running inside the infrastructure and able to respond—if the Runner is stuck, crashed, or unresponsive, there is no fallback mechanism to terminate the infrastructure.

This plan introduces a complementary cancellation mechanism where the worker acts as a fallback to forcefully terminate infrastructure when the Runner cannot handle cancellation gracefully.

## Problem Statement

When a user cancels a flow run:

1. The Prefect API sets the flow run state to `CANCELLING`
2. The Runner (inside the pod/container) receives this signal via WebSocket or polling
3. The Runner executes `on_cancellation` hooks, kills the process, and marks the flow run as `CANCELLED`

This works well when the Runner is healthy and responsive. However, cancellation fails when:

- The flow process is stuck or hung (infinite loop, deadlock, blocking I/O)
- The Runner crashed before receiving the cancellation signal
- Network issues prevent the Runner from receiving the cancellation event
- The infrastructure is in a bad state where signals cannot be processed

In these cases, the flow run remains in `CANCELLING` state indefinitely, and the infrastructure (Kubernetes Job, Docker container, ECS task, etc.) continues running until manual intervention.

## Proposed Solution

Implement a dual-observer pattern where both the Runner and the Worker listen for cancellation events, but handle them differently:

| Component | Response to Cancellation |
|-----------|-------------------------|
| **Runner** | Handles immediately—runs `on_cancellation` hooks, kills process, marks as cancelled |
| **Worker** | Schedules a delayed check—after a grace period, forcefully terminates infrastructure if still cancelling |

This ensures:
- The Runner gets first opportunity to handle cancellation gracefully (with hooks)
- The Worker acts as a fallback for stuck/unresponsive infrastructure
- Users can configure the grace period based on their needs

## Design

### Grace Period

The grace period determines how long the Worker waits before forcefully terminating infrastructure. During this time:

- The Runner has the opportunity to handle cancellation gracefully
- `on_cancellation` hooks can execute
- Resources can be cleaned up properly

The grace period is calculated from `flow_run.state.timestamp`—when the flow run entered the `CANCELLING` state. This allows the Worker to correctly handle orphaned flow runs discovered on startup.

### Configuration

Two environment variables control the feature:

| Variable | Default | Description |
|----------|---------|-------------|
| `PREFECT_WORKER_ENABLE_CANCELLATION` | `false` | Feature flag to enable worker-side cancellation |
| `PREFECT_WORKER_CANCELLATION_GRACE_PERIOD_SECONDS` | `60` | Seconds to wait before force-cancelling. Set to `-1` to disable |

This client-side configuration allows for gradual rollout without server changes.

### Detection Mechanism

The Worker detects cancelling flow runs through two mechanisms:

1. **Startup Poll**: On worker startup, query the API for any flow runs in `CANCELLING` state belonging to this work pool. This catches orphaned flow runs from before the worker started (e.g., after a worker restart).

2. **WebSocket Events**: Subscribe to `prefect.flow-run.Cancelling` events for real-time detection of new cancellations.

No continuous polling is needed—the startup poll handles the restart case, and WebSocket events handle the steady-state case.

### Force Cancellation Flow

When the Worker detects a cancelling flow run:

1. Parse `infrastructure_pid` to verify it's infrastructure this worker can manage
2. Calculate time remaining until grace period expires based on `state.timestamp`
3. Schedule an async task to check again after the remaining time
4. When the task fires, re-fetch the flow run state
5. If still `CANCELLING`, call `kill_infrastructure()` and mark as `CANCELLED`
6. If already `CANCELLED` or other terminal state, do nothing (Runner handled it)

### Architecture

The cancellation logic lives in `BaseWorker` to avoid duplication across integrations. Each integration implements only the `kill_infrastructure()` method for their specific infrastructure type.

```
BaseWorker (src/prefect/workers/base.py)
├── _setup_cancellation_handling()     # Initialize detection
├── _poll_for_cancelling_flow_runs()   # Startup poll
├── _consume_cancellation_events()     # WebSocket consumer
├── _schedule_force_cancellation()     # Schedule delayed check
├── _force_cancel_flow_run()           # Terminate and mark cancelled
└── kill_infrastructure()              # Abstract method

KubernetesWorker
└── kill_infrastructure()              # Delete K8s Job

DockerWorker
└── kill_infrastructure()              # Stop Docker container

ECSWorker
└── kill_infrastructure()              # Stop ECS task
```

## Rollout Strategy

| Phase | `PREFECT_WORKER_ENABLE_CANCELLATION` | Behavior |
|-------|--------------------------------------|----------|
| **Initial release** | `false` (default) | Feature disabled, current behavior |
| **Opt-in testing** | `true` (user sets) | Feature enabled for testing |
| **Future release** | `true` (new default) | Feature enabled by default |

Users opt-in by setting the environment variable, allowing them to test the feature before it becomes the default.

## Trade-offs

### On-Cancellation Hooks

When the Worker force-cancels a flow run, `on_cancellation` hooks will not execute because:
- The Worker doesn't have access to the flow code
- Hooks run in the flow's execution context with its dependencies
- Force-cancellation terminates the process immediately

Users who require hooks to always run can:
- Set a longer grace period to give the Runner more time
- Set grace period to `-1` to disable worker-side cancellation entirely (accepting that stuck flows may remain in `CANCELLING` indefinitely)

### Duplicate Cancellation Attempts

Both the Runner and Worker may attempt to cancel the same flow run. This is safe because:
- Both use `force=True` when setting state, which allows `CANCELLED` → `CANCELLED` transitions
- Kubernetes/Docker/ECS handle "delete already-deleted resource" gracefully (404 errors are caught)
- The `_pending_cancellations` dict prevents duplicate scheduled tasks within the same worker

The worst case is duplicate log messages and events, which is acceptable.

## Sequence Diagram

### Normal Case: Runner Handles Cancellation

```
User                API                 Runner              Worker
  │                  │                    │                   │
  │──Cancel flow────►│                    │                   │
  │                  │                    │                   │
  │                  │──State=CANCELLING─►│                   │
  │                  │                    │                   │
  │                  │                    │──Run hooks        │
  │                  │                    │──Kill process     │
  │                  │                    │                   │
  │                  │◄─State=CANCELLED───│                   │
  │                  │                    │                   │
  │                  │──────────────────────────Event────────►│
  │                  │                    │                   │
  │                  │                    │        (schedules check)
  │                  │                    │                   │
  │                  │                    │        (after grace period)
  │                  │                    │        (checks state)
  │                  │                    │        (already CANCELLED)
  │                  │                    │        (no action needed)
```

### Fallback Case: Worker Force-Cancels

```
User                API                 Runner              Worker
  │                  │                    │                   │
  │──Cancel flow────►│                    │                   │
  │                  │                    │                   │
  │                  │──State=CANCELLING─►│ (stuck/crashed)   │
  │                  │                    │                   │
  │                  │──────────────────────────Event────────►│
  │                  │                    │                   │
  │                  │                    │        (schedules check)
  │                  │                    │                   │
  │                  │                    │        ... grace period ...
  │                  │                    │                   │
  │                  │                    │        (checks state)
  │                  │                    │        (still CANCELLING)
  │                  │                    │                   │
  │                  │                    │        (kill infrastructure)
  │                  │                    │                   │
  │                  │◄───────────────────────State=CANCELLED─│
```

---

## Implementation Details

### Settings

Add new settings to control the feature:

```python
# src/prefect/settings/models/worker.py

PREFECT_WORKER_ENABLE_CANCELLATION = Setting(
    bool,
    default=False,
    description="""
    Enable worker-side flow run cancellation. When enabled, the worker will
    forcefully terminate infrastructure for flow runs that remain in CANCELLING
    state after the grace period expires.
    """
)

PREFECT_WORKER_CANCELLATION_GRACE_PERIOD_SECONDS = Setting(
    int,
    default=60,
    description="""
    Grace period (in seconds) to wait before forcefully terminating a
    cancelling flow run's infrastructure. Set to -1 to disable worker-side
    cancellation entirely.
    """
)
```

### Base Worker Changes

Add cancellation handling to `BaseWorker`:

```python
# src/prefect/workers/base.py

class BaseWorker(abc.ABC):

    async def __aenter__(self):
        # ... existing setup ...

        if PREFECT_WORKER_ENABLE_CANCELLATION.value():
            await self._setup_cancellation_handling()

        return self

    async def _setup_cancellation_handling(self):
        """Initialize cancellation detection and handling."""
        self._pending_cancellations: dict[UUID, asyncio.Task] = {}

        # Startup poll for orphaned cancelling flow runs
        await self._poll_for_cancelling_flow_runs()

        # WebSocket subscription for real-time events
        self._cancellation_subscriber = await self._exit_stack.enter_async_context(
            get_events_subscriber(
                filter=EventFilter(
                    event=EventNameFilter(name=["prefect.flow-run.Cancelling"])
                ),
            )
        )
        self._cancellation_consumer_task = asyncio.create_task(
            self._consume_cancellation_events()
        )

    async def _poll_for_cancelling_flow_runs(self):
        """One-time poll on startup to catch orphaned cancelling flow runs."""
        # Query for CANCELLING state type
        cancelling_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLING]),
                ),
            ),
            work_pool_filter=WorkPoolFilter(
                name=WorkPoolFilterName(any_=[self._work_pool_name])
            ),
        )

        # Also query legacy representation (type=CANCELLED, name="Cancelling")
        named_cancelling = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLED]),
                    name=FlowRunFilterStateName(any_=["Cancelling"]),
                ),
            ),
            work_pool_filter=WorkPoolFilter(
                name=WorkPoolFilterName(any_=[self._work_pool_name])
            ),
        )

        for flow_run in cancelling_flow_runs + named_cancelling:
            await self._schedule_force_cancellation(flow_run)

    async def _consume_cancellation_events(self):
        """Process WebSocket events for real-time cancellation detection."""
        seen_ids: set[UUID] = set()

        async for event in self._cancellation_subscriber:
            flow_run_id = UUID(
                event.resource["prefect.resource.id"].replace("prefect.flow-run.", "")
            )

            if flow_run_id in seen_ids:
                continue
            seen_ids.add(flow_run_id)

            flow_run = await self._client.read_flow_run(flow_run_id)

            if flow_run.work_pool_name != self._work_pool_name:
                continue

            await self._schedule_force_cancellation(flow_run)

    async def _schedule_force_cancellation(self, flow_run: "FlowRun"):
        """Schedule force-cancellation after grace period expires."""
        if not flow_run.infrastructure_pid:
            return

        if flow_run.id in self._pending_cancellations:
            return

        grace_period = PREFECT_WORKER_CANCELLATION_GRACE_PERIOD_SECONDS.value()

        if grace_period == -1:
            return

        # Calculate remaining time based on when state was set
        if flow_run.state and flow_run.state.timestamp:
            time_in_cancelling = (
                pendulum.now("UTC") - flow_run.state.timestamp
            ).total_seconds()
            time_remaining = max(0, grace_period - time_in_cancelling)
        else:
            time_remaining = grace_period

        task = asyncio.create_task(
            self._delayed_force_cancel(flow_run.id, time_remaining)
        )
        self._pending_cancellations[flow_run.id] = task

    async def _delayed_force_cancel(self, flow_run_id: UUID, delay: float):
        """Wait for grace period, then force-cancel if still cancelling."""
        try:
            await asyncio.sleep(delay)

            flow_run = await self._client.read_flow_run(flow_run_id)

            if not (flow_run.state and flow_run.state.is_cancelling()):
                return  # Already handled

            configuration = await self._get_configuration(flow_run)
            await self._force_cancel_flow_run(flow_run, configuration)

        except ObjectNotFound:
            pass  # Flow run or deployment deleted
        finally:
            self._pending_cancellations.pop(flow_run_id, None)

    async def _force_cancel_flow_run(
        self,
        flow_run: "FlowRun",
        configuration: Optional[BaseJobConfiguration],
    ):
        """Forcefully terminate infrastructure and mark flow run as cancelled."""
        if flow_run.infrastructure_pid:
            try:
                await self.kill_infrastructure(
                    infrastructure_pid=flow_run.infrastructure_pid,
                    configuration=configuration,
                    grace_seconds=30,
                )
            except NotImplementedError:
                self._logger.warning(
                    f"Worker type {self.type!r} does not support killing infrastructure"
                )
                return
            except InfrastructureNotFound:
                pass  # Already gone
            except InfrastructureNotAvailable as exc:
                self._logger.warning(f"{exc}")
                return

        await self._mark_flow_run_as_cancelled(
            flow_run,
            state_updates={
                "message": (
                    "Flow run cancelled by worker after grace period. "
                    "on_cancellation hooks may not have executed."
                )
            },
        )

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: Optional[BaseJobConfiguration],
        grace_seconds: int = 30,
    ) -> None:
        """
        Kill infrastructure for a flow run. Override in subclasses.

        Raises:
            NotImplementedError: If worker doesn't support killing infrastructure
            InfrastructureNotFound: If infrastructure doesn't exist
            InfrastructureNotAvailable: If infrastructure can't be killed by this worker
        """
        raise NotImplementedError(
            f"Worker type {self.type!r} does not support killing infrastructure"
        )
```

### Kubernetes Worker Implementation

```python
# src/integrations/prefect-kubernetes/prefect_kubernetes/worker.py

class KubernetesWorker(BaseWorker):

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: Optional[KubernetesWorkerJobConfiguration],
        grace_seconds: int = 30,
    ) -> None:
        """Kill a Kubernetes job."""
        job_cluster_uid, job_namespace, job_name = self._parse_infrastructure_pid(
            infrastructure_pid
        )

        async with self._get_configured_kubernetes_client(configuration) as client:
            current_cluster_uid = await self._get_cluster_uid(client)
            if job_cluster_uid != current_cluster_uid:
                raise InfrastructureNotAvailable(
                    f"Job {job_name!r} is on a different cluster"
                )

            async with self._get_batch_client(client) as batch_client:
                try:
                    await batch_client.delete_namespaced_job(
                        name=job_name,
                        namespace=job_namespace,
                        grace_period_seconds=grace_seconds,
                        propagation_policy="Foreground",
                    )
                except ApiException as exc:
                    if exc.status == 404:
                        raise InfrastructureNotFound(f"Job {job_name!r} not found")
                    raise
```

## Usage

```bash
# Enable the feature
export PREFECT_WORKER_ENABLE_CANCELLATION=true

# Optionally adjust grace period (default 60s)
export PREFECT_WORKER_CANCELLATION_GRACE_PERIOD_SECONDS=120

# Or disable worker-side cancellation (rely only on Runner)
export PREFECT_WORKER_CANCELLATION_GRACE_PERIOD_SECONDS=-1

# Start worker
prefect worker start --pool my-pool --type kubernetes
```
