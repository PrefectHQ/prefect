# Architecture

**Analysis Date:** 2026-02-03

## Pattern Overview

**Overall:** Layered monolith with separation between SDK (user-facing workflow definitions), engine (execution layer), client (API communication), and server (backend orchestration infrastructure).

**Key Characteristics:**
- Client-server architecture with async-first design
- Event-driven state machine for workflow execution
- Pluggable infrastructure blocks for deployment and storage
- Separation of concerns: declarations (@flow, @task) vs execution (engine)
- Context-based dependency injection for runtime information

## Layers

**SDK Layer - User-Facing API:**
- Purpose: Decorators and classes for defining workflows, tasks, flows
- Location: `src/prefect/flows.py`, `src/prefect/tasks.py`, `src/prefect/main.py`
- Contains: Flow and Task class definitions, decorators (@flow, @task), transaction support
- Depends on: context, states, futures, client, logging
- Used by: End-user code, deployments, CLI

**Engine Layer - Execution:**
- Purpose: Executes flows and tasks, manages state transitions, handles concurrency and retries
- Location: `src/prefect/flow_engine.py`, `src/prefect/task_engine.py`
- Contains: Execution logic for sync/async flows and tasks, state management, orchestration
- Depends on: context, states, client, concurrency, results, infrastructure
- Used by: Runner implementations, CLI execution, task runners

**Client Layer - API Communication:**
- Purpose: HTTP client for communicating with Prefect server or cloud
- Location: `src/prefect/client/`
- Contains: PrefectClient (async), SyncPrefectClient, API schema definitions, HTTP utilities
- Depends on: httpx, pydantic, schemas
- Used by: engine, blocks, logging, deployments

**Context Layer - Runtime State:**
- Purpose: Thread-safe and async-safe storage of execution context (flow run, task run, settings, etc)
- Location: `src/prefect/context.py`
- Contains: FlowRunContext, TaskRunContext, SettingsContext, AssetContext, context managers for serialization
- Depends on: client, settings, states, logging
- Used by: engine, tasks, flows, logging, utilities

**Server Layer - Backend Orchestration:**
- Purpose: REST API, orchestration policies, database models, state machine rules
- Location: `src/prefect/server/`
- Contains: API endpoints, ORM models, orchestration core/policies, database migrations
- Depends on: SQLAlchemy, FastAPI, pydantic, schemas
- Used by: Prefect Server deployment, orchestration engine

**Storage & Results:**
- Purpose: Persisting task and flow results, managing result serialization and retrieval
- Location: `src/prefect/results.py`, `src/prefect/filesystems.py`
- Contains: ResultStore, ResultSerializer, WritableFileSystem implementations (local, S3, GCS, etc)
- Depends on: client, blocks, serializers
- Used by: engine, tasks, blocks

**Infrastructure & Deployment:**
- Purpose: Infrastructure blocks (Docker, Kubernetes, etc), deployment runners, build steps
- Location: `src/prefect/infrastructure/`, `src/prefect/deployments/`, `src/prefect/runner/`
- Contains: Infrastructure block types, deployment configuration, build/push/pull steps, process/container execution
- Depends on: blocks, client, engine, filesystems
- Used by: deployment system, CLI

**Utilities & Cross-Cutting:**
- Purpose: Shared helpers for async dispatch, hashing, importtools, collections, etc
- Location: `src/prefect/utilities/`, `src/prefect/_internal/`
- Contains: Async utilities, filesystem helpers, import/reflection tools, compatibility layers
- Depends on: standard library, typing
- Used by: All layers

## Data Flow

**Flow/Task Definition to Execution:**

1. User decorates function with `@flow` or `@task`
2. Decorator creates Flow or Task object with metadata (name, version, caching, etc)
3. User calls flow/task, which returns a PrefectFuture (pending execution)
4. In local execution: Future triggers engine.execute() immediately
5. In deployed execution: Flow run is submitted to server via client; runner picks up and executes

**Execution Flow:**

1. FlowRunContext is created with flow run details from server or local context
2. Engine enters execution context: settings, logging, client, events, concurrency limits
3. For each task in flow:
   - TaskRunContext is created
   - Task result caching is checked
   - Task execution handler runs task function
   - Result is persisted based on result_storage configuration
   - State transition happens (Pending -> Running -> Completed/Failed)
4. Flow state is determined by task states and orchestration policy
5. Results are serialized and stored per configuration
6. State transitions emit events (for automations, monitoring)

**State Machine:**

- Scheduled → Pending → Running → Completed/Failed/Cancelled/Paused
- Retries advance: Failed → Scheduled → Pending → Running → ...
- Each transition can have state_details and data attached
- Server applies global and flow-specific orchestration policies
- Concurrency policies can block/delay state transitions

## Key Abstractions

**Flow:**
- Purpose: Top-level workflow definition and execution unit
- Examples: `src/prefect/flows.py` (Flow class), `src/prefect/main.py` (exported flow decorator)
- Pattern: Decorator on async/sync function, tracks task calls, manages parameters and retries

**Task:**
- Purpose: Discrete unit of work within a flow
- Examples: `src/prefect/tasks.py` (Task class)
- Pattern: Decorator on async/sync function, supports caching, retries, concurrency limits

**Block:**
- Purpose: Pluggable configuration for external systems (filesystems, notifications, secrets, etc)
- Examples: `src/prefect/blocks/core.py`, `src/prefect/filesystems.py`
- Pattern: Pydantic BaseModel with save()/load() for serialization, injectable into flows/tasks

**State:**
- Purpose: Representation of run status with associated data
- Examples: `src/prefect/states.py`, `src/prefect/client/schemas/objects.py`
- Pattern: Immutable data class with type, message, data (result), state_details, timestamp

**Future:**
- Purpose: Reference to a pending or completed task/flow result
- Examples: `src/prefect/futures.py` (PrefectFuture, PrefectFlowRunFuture)
- Pattern: Lazy-evaluated container that resolves to actual result or state

**Deployment:**
- Purpose: Configuration for scheduling and deploying flows to workers
- Examples: `src/prefect/deployments/deployments.py`
- Pattern: YAML-driven with build/push/pull steps, work pool assignment, schedule definition

## Entry Points

**CLI Entry:**
- Location: `src/prefect/cli/` (typer-based command structure)
- Triggers: `prefect flow run`, `prefect deploy`, `prefect server start`, etc
- Responsibilities: Command parsing, local execution context setup, server interaction

**Python API Entry:**
- Location: `src/prefect/main.py`
- Triggers: `from prefect import flow, task` and decorator usage
- Responsibilities: Module initialization, plugin system setup, logging configuration

**Server Entry:**
- Location: `src/prefect/server/api/` (FastAPI routes)
- Triggers: HTTP requests to running server
- Responsibilities: Request validation, orchestration, database operations, event emission

**Runner Entry:**
- Location: `src/prefect/runner/` (ProcessWorker, ThreadWorker implementations)
- Triggers: Flow run created on server or worker polling
- Responsibilities: Fetch flow definition, execute in configured infrastructure, report state

## Error Handling

**Strategy:** Custom exception hierarchy with context-aware handling at engine boundaries.

**Patterns:**
- Engine catches exceptions at flow/task boundaries and converts to Failed/Crashed states
- TaskRunErrors wrap upstream failures for dependency propagation
- TerminationSignals (Abort, Pause) interrupt execution via exception raising
- Retry logic catches specific exception types via cache_policy and task_run_policy
- User exceptions preserved in state.data for inspection

## Cross-Cutting Concerns

**Logging:** Each execution level (flow, task) gets a dedicated logger via `get_run_logger()` which includes run IDs in log records; server-side log aggregation via `src/prefect/server/logs/`

**Validation:** Pydantic models validate all API inputs; flow/task parameters validated during submission; state machine validates legal transitions

**Authentication:** Client-based via API key in headers or cloud authentication; server validates all requests; CLI uses stored profiles

**Events:** Task completion/failure emits events to event system for automations; can be disabled per setting; processed by `src/prefect/events/` worker
