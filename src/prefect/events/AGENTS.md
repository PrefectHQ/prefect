# Events (Client-Side)

Client-side event system for emitting, subscribing to, and defining automations on Prefect events.

## Key Contracts

- **Both client and server define their own event schemas.** The client-side schemas live in `schemas/` here; the server has its own parallel definitions in `server/events/schemas/`. They are structurally similar but independently maintained — the server does not import schemas from this module.
- Events follow the CloudEvents-inspired schema: `Event` with `Resource` and `RelatedResource`.
- Automations combine triggers (event, metric, compound, sequence) with actions.
- **Metric triggers are Cloud-only.** OSS's `ServerTriggerTypes` excludes `MetricTrigger`, so `POST /automations` returns 422. For "alert if a flow takes too long" on OSS, use a proactive `EventTrigger` (`after={prefect.flow-run.Running}`, terminal states in `expect`, SLO in `within`).
- **Event name prefixes differ by backend.** OSS emits `prefect.*`; Cloud emits `prefect-cloud.*` for automation/action lifecycle events (e.g., `prefect-cloud.automation.triggered`). Cross-backend tooling that filters events must match both.
- **Automation schemas tolerate values Cloud adds before a client release knows them.** Unrecognized action types read as `UnknownAction` (extra fields kept) and unrecognized metric names stay plain `str`, so read→update round-trips send them back unchanged. Code consuming these models must handle the fallback (e.g. don't assume `metric.name` is a `PrefectMetric` with `.value`), and code copying automations to another backend (`prefect transfer`) skips them because the destination may not support them.
- `DeploymentTriggerTypes` are the subset of triggers usable in `prefect.yaml` deployment definitions.

## clients.py — Checkpointing Invariant

`PrefectEventsClient` uses **two independent checkpointing mechanisms** to confirm server receipt of sent events:

1. **Count-based** (`checkpoint_every`, default 700): checkpoints after N emitted events.
2. **Time-based** (`checkpoint_interval`, default 30s): a background `asyncio.Task` that fires periodically regardless of event count. Prevents unbounded buffer growth for low-throughput connections.

The background task is started in `__aenter__` and after each reconnect, and cancelled in `__aexit__`. If you subclass or mock `PrefectEventsClient`, ensure both checkpointing paths are exercised — the count threshold alone is not sufficient for low-volume scenarios.

## Structure

- `schemas/` — Pydantic models: `Event`, `Resource`, `RelatedResource`, `Automation`, triggers, deployment triggers
- `clients.py` — Event emission client (sends events to server/Cloud)
- `subscribers.py` — WebSocket subscribers for real-time event streams
- `actions.py` — Automation action types (`RunDeployment`, `PauseDeployment`, `SendNotification`, etc.)
- `worker.py` — Background event emission worker
- `filters.py` — Event query filters
- `related.py` — Related resource resolution

## Client vs Server

| Concern | Client (`events/`) | Server (`server/events/`) |
|---------|-------------------|--------------------------|
| Event schemas | Defined here | Own parallel definitions |
| Emission | `clients.py` | Receives via API |
| Subscriptions | `subscribers.py` | `stream.py`, `messaging.py` |
| Trigger evaluation | Definition only | Evaluation and firing |
| Actions | Type definitions | Execution |

## Related

- `server/events/` → Server-side event processing
- `client/schemas/events.py` → Client-side event schema re-exports
