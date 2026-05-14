---
title: How to scale worker concurrency
sidebarTitle: Scale worker concurrency
description: Configure worker concurrency limits and scale multi-worker deployments for high-throughput workloads.
keywords: ["worker limit", "concurrency", "scaling", "throughput", "work pool", "task runner"]
---

Use worker concurrency settings to control how many flow runs execute simultaneously and to scale your deployment for high-throughput workloads.

## Understand how workers handle concurrency

Each worker runs a polling loop that fetches scheduled flow runs from its work pool and submits them for execution. By default, the worker submits runs without any concurrency cap — all available scheduled runs are dispatched as fast as the poll interval allows.

Internally, the worker uses an async task group. Each submitted flow run occupies a slot in an `anyio.CapacityLimiter`. When all slots are taken the worker skips new runs until a slot is released — without blocking the main loop or queuing runs on the worker side. Unsubmitted runs remain in the server-side queue and are picked up on the next poll cycle.

The worker never waits for a flow run to finish. Flows execute in separate processes or containers, so one long-running flow does not delay others.

## Set a per-worker concurrency limit

Pass `--limit` when starting a worker to cap the number of flow runs it runs at one time:

{/* pmd-metadata: notest */}
```bash
prefect worker start --pool my-pool --limit 20
```

You can also set this in the environment when deploying workers in containers:

{/* pmd-metadata: notest */}
```bash
export PREFECT_WORKER_QUERY_SECONDS=5     # poll every 5 s instead of 10 s
export PREFECT_WORKER_PREFETCH_SECONDS=30  # fetch runs scheduled up to 30 s ahead
prefect worker start --pool my-pool --limit 20
```

| Setting | Default | Effect |
|---------|---------|--------|
| `--limit` (CLI flag) | None (unlimited) | Maximum concurrent flow runs per worker |
| `PREFECT_WORKER_QUERY_SECONDS` | 10 s | How often the worker polls for new runs |
| `PREFECT_WORKER_PREFETCH_SECONDS` | 10 s | How far into the future to prefetch scheduled runs |
| `PREFECT_WORKER_HEARTBEAT_SECONDS` | 30 s | How often the worker sends a heartbeat to the server |

## Set a work pool concurrency limit

A work pool concurrency limit caps the total number of PENDING and RUNNING flow runs across **all** workers in that pool. This is useful when you want to protect downstream systems regardless of how many worker instances are running.

{/* pmd-metadata: notest */}
```bash
prefect work-pool update my-pool --concurrency-limit 100
```

Remove the limit when you no longer need it:

{/* pmd-metadata: notest */}
```bash
prefect work-pool set-concurrency-limit my-pool 100  # set
prefect work-pool clear-concurrency-limit my-pool    # remove
```

You can also set per-queue limits to prioritize different classes of work:

{/* pmd-metadata: notest */}
```bash
prefect work-queue set-concurrency-limit --limit 10 critical-queue
```

The server enforces pool and queue limits with database row locks (`FOR UPDATE SKIP LOCKED`), so multiple workers polling the same pool never pick up the same run.

## Scale out with multiple worker instances

To increase total throughput, run multiple worker processes pointing at the same work pool. The server distributes runs across all available workers, and each worker's `--limit` contributes to the overall capacity.

{/* pmd-metadata: notest */}
```bash
# Machine A
prefect worker start --pool production-pool --limit 20

# Machine B
prefect worker start --pool production-pool --limit 20

# Machine C
prefect worker start --pool production-pool --limit 20
# effective capacity: up to 60 concurrent runs, bounded by the pool-level concurrency limit
```

### Kubernetes example

Use a `Deployment` with multiple replicas and configure the concurrency limit as an argument:

{/* pmd-metadata: notest */}
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prefect-worker
spec:
  replicas: 5
  selector:
    matchLabels:
      app: prefect-worker
  template:
    metadata:
      labels:
        app: prefect-worker
    spec:
      containers:
        - name: prefect-worker
          image: prefecthq/prefect:3-latest
          command:
            - prefect
            - worker
            - start
            - --pool
            - k8s-pool
            - --limit
            - "20"
          env:
            - name: PREFECT_API_URL
              value: "http://prefect-server:4200/api"
            - name: PREFECT_WORKER_QUERY_SECONDS
              value: "5"
            - name: PREFECT_WORKER_PREFETCH_SECONDS
              value: "30"
```

Add a Horizontal Pod Autoscaler to scale replicas automatically based on CPU or custom metrics.

## Run tasks concurrently inside a flow

Worker concurrency controls how many *flow runs* execute at once. To parallelize *tasks* within a single flow, use `.submit()` with an appropriate task runner.

<Tabs>
  <Tab title="IO-bound tasks">
    For tasks that spend most of their time waiting on network calls or external APIs, the default `ConcurrentTaskRunner` (asyncio-based) handles many tasks efficiently:

    ```python
    from prefect import flow, task

    @task
    def fetch_record(record_id: int) -> dict:
        # IO-bound work: HTTP call, database query, etc.
        ...

    @flow
    def process_records(record_ids: list[int]):
        futures = [fetch_record.submit(rid) for rid in record_ids]
        return [f.result() for f in futures]
    ```
  </Tab>
  <Tab title="Blocking or CPU-bound tasks">
    For tasks that block the event loop (synchronous SDKs, `time.sleep`, CPU-heavy code), use `ThreadPoolTaskRunner`:

    ```python
    from prefect import flow, task
    from prefect.task_runners import ThreadPoolTaskRunner

    @task
    def transform_record(record: dict) -> dict:
        # Blocking or CPU-intensive work
        ...

    @flow(task_runner=ThreadPoolTaskRunner(max_workers=20))
    def process_records(records: list[dict]):
        futures = [transform_record.submit(r) for r in records]
        return [f.result() for f in futures]
    ```
  </Tab>
</Tabs>

To prevent a single task from blocking a slot indefinitely, set a timeout:

```python
from prefect import task

@task(timeout_seconds=120)
def call_external_api(payload: dict) -> dict:
    ...
```

## Tune for high-throughput workloads

Use the following guidelines to choose settings for demanding workloads:

| Scenario | Recommendation |
|----------|----------------|
| Many short-lived flows | Lower `PREFECT_WORKER_QUERY_SECONDS` (e.g. 3–5 s), raise `--limit` |
| Flows with long-running IO tasks | Use `ConcurrentTaskRunner`; set `PREFECT_WORKER_PREFETCH_SECONDS` higher |
| Flows with blocking/CPU tasks | Use `ThreadPoolTaskRunner` with `max_workers` sized to available cores |
| Shared downstream systems | Set a work pool `--concurrency-limit` to cap total load |
| Unpredictable traffic | Deploy multiple workers; use HPA or autoscaling to add/remove replicas |

<Note>
Raising `--limit` increases memory and CPU usage on the worker host. Monitor resource utilization and adjust based on observed headroom, not just target throughput.
</Note>

## Related resources

- [Workers concept page](/v3/concepts/workers) — how workers, work pools, and work queues relate
- [Manage work pools](/v3/how-to-guides/deployment_infra/manage-work-pools) — create and configure work pools
- [Apply global concurrency and rate limits](/v3/how-to-guides/workflows/global-concurrency-limits) — limit concurrency at the task or flow level across all runs
- [Run tasks concurrently](/v3/how-to-guides/workflows/run-work-concurrently) — parallel task execution within a single flow
