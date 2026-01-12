# Deployment CRUD Events

## Goal

Emit events for deployment create, update, and delete operations in OSS, enabling users to build automations that respond to deployment lifecycle changes.

**Issue**: https://github.com/PrefectHQ/prefect/issues/20176

## Background

### Current State

OSS currently emits:
- `prefect.deployment.{status}` - status change events (ready/not-ready)
- `prefect.work-pool.updated` - field change events for work pools
- `prefect.work-queue.updated` - field change events for work queues

Missing:
- `prefect.deployment.created`
- `prefect.deployment.updated`
- `prefect.deployment.deleted`

### Cloud Parity

Cloud emits these events via the `Auditor` system, which adds actor-related resources for audit trail. The event names use the `prefect.` prefix (not `prefect-cloud.`) because deployments are "orchestration objects":

```python
# Cloud uses prefect.* prefix for orchestration objects
orchestration_object_types: set[str] = {
    "deployment",  # Uses prefect.deployment.* naming
    "flow",
    "work-pool",
    ...
}
```

**Consistency**: OSS events will be identical in shape to Cloud, just without actor-related resources. Automations using these events will be portable between OSS and Cloud.

## Event Specifications

### prefect.deployment.created

Emitted when a new deployment is created (not on upsert/update of existing).

```python
Event(
    event="prefect.deployment.created",
    resource={
        "prefect.resource.id": f"prefect.deployment.{deployment.id}",
        "prefect.resource.name": deployment.name,
    },
    related=[
        {
            "prefect.resource.id": f"prefect.flow.{flow.id}",
            "prefect.resource.name": flow.name,
            "prefect.resource.role": "flow",
        },
        # work-queue if present
        # work-pool if present
    ],
    payload={...},  # deployment data
)
```

### prefect.deployment.updated

Emitted when an existing deployment is modified. Includes changed fields in payload.

```python
Event(
    event="prefect.deployment.updated",
    resource={
        "prefect.resource.id": f"prefect.deployment.{deployment.id}",
        "prefect.resource.name": deployment.name,
    },
    related=[...],  # flow, work-queue, work-pool
    payload={
        "updated_fields": ["description", "parameters"],
        "updates": {
            "description": {"old": "...", "new": "..."},
            "parameters": {"old": {...}, "new": {...}},
        },
    },
)
```

### prefect.deployment.deleted

Emitted when a deployment is deleted.

```python
Event(
    event="prefect.deployment.deleted",
    resource={
        "prefect.resource.id": f"prefect.deployment.{deployment.id}",
        "prefect.resource.name": deployment.name,
    },
    related=[...],  # flow, work-queue, work-pool (captured before deletion)
)
```

## Implementation

### Phase 1: Event Factory Functions

**Location**: `src/prefect/server/models/events.py`

Add three new functions following the existing `work_pool_updated_event` pattern:

```python
async def deployment_created_event(
    session: AsyncSession,
    deployment: ORMDeployment,
    occurred: DateTime,
) -> Event:
    """Create an event for deployment creation."""
    ...

async def deployment_updated_event(
    session: AsyncSession,
    deployment: ORMDeployment,
    changed_fields: Dict[str, Dict[str, Any]],
    occurred: DateTime,
) -> Event:
    """Create an event for deployment field updates."""
    ...

async def deployment_deleted_event(
    session: AsyncSession,
    deployment: ORMDeployment,
    occurred: DateTime,
) -> Event:
    """Create an event for deployment deletion."""
    ...
```

**Helper function** (similar to `_flow_run_related_resources_from_orm`):

```python
async def _deployment_related_resources(
    session: AsyncSession,
    deployment: ORMDeployment,
) -> RelatedResourceList:
    """Get related resources for a deployment event."""
    # Returns flow, work-queue, work-pool as related resources
    ...
```

**Status**:
- [ ] `deployment_created_event` function
- [ ] `deployment_updated_event` function
- [ ] `deployment_deleted_event` function
- [ ] `_deployment_related_resources` helper
- [ ] Unit tests for event factory functions

---

### Phase 2: Emit Functions

**Location**: `src/prefect/server/models/deployments.py`

Add emit wrapper functions (following `emit_work_queue_updated_event` pattern):

```python
async def emit_deployment_created_event(
    session: AsyncSession,
    deployment: ORMDeployment,
) -> None:
    """Emit an event when a deployment is created."""
    async with PrefectServerEventsClient() as events_client:
        await events_client.emit(
            await deployment_created_event(
                session=session,
                deployment=deployment,
                occurred=now("UTC"),
            )
        )

async def emit_deployment_updated_event(
    session: AsyncSession,
    deployment: ORMDeployment,
    changed_fields: Dict[str, Dict[str, Any]],
) -> None:
    """Emit an event when a deployment is updated."""
    if not changed_fields:
        return
    async with PrefectServerEventsClient() as events_client:
        await events_client.emit(
            await deployment_updated_event(
                session=session,
                deployment=deployment,
                changed_fields=changed_fields,
                occurred=now("UTC"),
            )
        )

async def emit_deployment_deleted_event(
    session: AsyncSession,
    deployment: ORMDeployment,
) -> None:
    """Emit an event when a deployment is deleted."""
    async with PrefectServerEventsClient() as events_client:
        await events_client.emit(
            await deployment_deleted_event(
                session=session,
                deployment=deployment,
                occurred=now("UTC"),
            )
        )
```

**Status**:
- [ ] `emit_deployment_created_event` function
- [ ] `emit_deployment_updated_event` function
- [ ] `emit_deployment_deleted_event` function

---

### Phase 3: Integration with Model Layer

Emit from `src/prefect/server/models/deployments.py`, following the existing work-pool/work-queue pattern.

#### Create/Upsert

In `create_deployment` model function:
- Track whether deployment is new (`created >= invocation_time`) or existing
- After successful operation, call `emit_deployment_created_event` or `emit_deployment_updated_event`
- For updates, compute `changed_fields` by comparing old vs new values

#### Update

In `update_deployment` model function:
- Capture deployment state before update
- After update, compute changed fields
- Call `emit_deployment_updated_event` with changed fields

#### Delete

In `delete_deployment` model function:
- Read deployment before deletion (to capture data for event)
- After successful deletion, call `emit_deployment_deleted_event`

**Status**:
- [ ] Integrate `created` event into create/upsert flow
- [ ] Integrate `updated` event into update flow
- [ ] Integrate `deleted` event into delete flow
- [ ] Handle bulk delete if applicable
- [ ] Integration tests

---

### Phase 4: Testing

**Unit tests** (`tests/server/models/test_events.py`):
- Test event factory functions produce correct event structure
- Test related resources are populated correctly
- Test payload structure for updated events

**Integration tests** (`tests/server/api/test_deployments.py`):
- Test that creating a deployment emits `prefect.deployment.created`
- Test that upserting (updating existing) emits `prefect.deployment.updated`
- Test that updating via PATCH emits `prefect.deployment.updated`
- Test that deleting emits `prefect.deployment.deleted`
- Test that events include correct related resources

**Status**:
- [ ] Unit tests for event factory functions
- [ ] Integration tests for API endpoints
- [ ] Tests verify event payload structure matches Cloud

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Upsert creates new deployment | Emit `created` event |
| Upsert updates existing deployment | Emit `updated` event |
| Update with no actual changes | No event emitted (changed_fields empty) |
| Delete non-existent deployment | No event (404 returned) |
| Deployment without work pool | Events still emitted, work-pool not in related |
| Bulk delete | Emit `deleted` event for each deployment |

## Verification Checklist

### Automated
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Type checker passes

### Manual
- [ ] Create deployment → verify `created` event in event stream
- [ ] Update deployment → verify `updated` event with changed fields
- [ ] Delete deployment → verify `deleted` event
- [ ] Create automation triggered by `prefect.deployment.created`
- [ ] Verify event structure matches Cloud (minus actor resources)

## Out of Scope

- Actor tracking (Cloud-only feature)
- Audit log UI/branding (Cloud-only feature)
- Events for other resources (flows, flow runs, etc.)
