# Events (Client-Side)

Client-side event system for emitting, subscribing to, and defining automations on Prefect events.

## Key Contracts

- **Event schemas are defined here, not on the server.** The server imports schemas from this module.
- Events follow the CloudEvents-inspired schema: `Event` with `Resource` and `RelatedResource`.
- Automations combine triggers (event, metric, compound, sequence) with actions.
- `DeploymentTriggerTypes` are the subset of triggers usable in `prefect.yaml` deployment definitions.

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
| Event schemas | Defined here | Imported from client |
| Emission | `clients.py` | Receives via API |
| Subscriptions | `subscribers.py` | `stream.py`, `messaging.py` |
| Trigger evaluation | Definition only | Evaluation and firing |
| Actions | Type definitions | Execution |

## Related

- `server/events/` → Server-side event processing
- `client/schemas/events.py` → Client-side event schema re-exports
