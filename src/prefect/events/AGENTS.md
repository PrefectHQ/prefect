# Events (Client-Side)

Client-side event system for emitting, subscribing to, and defining automations on Prefect events.

## Key Contracts

- **Both client and server define their own event schemas.** The client-side schemas live in `schemas/` here; the server has its own parallel definitions in `server/events/schemas/`. They are structurally similar but independently maintained — the server does not import schemas from this module.
- Events follow the CloudEvents-inspired schema: `Event` with `Resource` and `RelatedResource`.
- Automations combine triggers (event, metric, compound, sequence) with actions.
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
