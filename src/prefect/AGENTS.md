# Core Prefect SDK

The foundation for building and executing workflows with Python.

## Key Components

- **Flows & Tasks**: Workflow definition with `@flow` and `@task` decorators
- **States**: Execution status tracking (Pending, Running, Completed, Failed)
- **Context**: Runtime information and dependency injection
- **Results**: Task output persistence and retrieval
- **Deployments**: Packaging flows for scheduled/triggered execution
- **Blocks**: Reusable configuration for external systems

## Main Modules

- `flows.py` - Flow lifecycle and execution
- `tasks.py` - Task definition and dependency resolution
- `engine.py` - Core execution engine
- `client/` - Server/Cloud API communication
- `deployments/` - Deployment management
- `blocks/` - Infrastructure and storage blocks

## SDK-Specific Notes

- Async-first execution model with sync support
- Immutable flow/task definitions after creation
- State transitions handle retries and caching
- Backward compatibility required for public APIs