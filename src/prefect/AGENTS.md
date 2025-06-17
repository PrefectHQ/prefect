# Core Prefect Library

This is the core Prefect library containing the fundamental building blocks for workflow orchestration.

## Core Concepts

- **Flows**: Top-level workflow containers defined with `@flow` decorator
- **Tasks**: Individual units of work defined with `@task` decorator  
- **States**: Represent the status of flow/task runs (Pending, Running, Completed, Failed, etc.)
- **Context**: Runtime information available during flow/task execution
- **Results**: Persistence layer for task outputs and artifacts

## Key Modules

- `flows.py` - Flow definition, execution, and lifecycle management
- `tasks.py` - Task definition, execution, and dependency resolution
- `states.py` - State management and transitions
- `context.py` - Runtime context and dependency injection
- `engine.py` - Core execution engine
- `client/` - Client interfaces for communicating with Prefect server/cloud
- `runner/` - Process management for running flows
- `deployments/` - Deployment creation and management
- `blocks/` - Reusable configuration and infrastructure components

## Execution Architecture

Prefect uses an asynchronous execution model:
- Flows and tasks are async by default but support sync execution
- Task dependencies are resolved through return value tracking
- State management handles retries, caching, and failure policies
- Results are persisted and retrievable across runs

## Development Patterns

- Prefer composition over inheritance for extensibility
- Use dependency injection through context for runtime services
- Maintain backward compatibility in public APIs
- Task and flow definitions are immutable after creation 