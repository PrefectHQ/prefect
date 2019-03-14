---
sidebarDepth: 0
---

# Prefect Design

## Tasks are functions

In a simple sense, Prefect tasks are simply functions that have special rules about when they should run: they optionally take inputs, perform some work, and optionally return an output. Each task receives metadata about its upstream dependencies before it runs, giving it an opportunity to change its behavior depending on the state of the flow.

Because Prefect is a negative engineering framework, it is agnostic to the code each task runs. There are no restrictions on what inputs and outputs can be.

## Workflows are containers

Workflows (or "flows") are containers for tasks. Flows represent the dependency structure between tasks, but do not perform any logic.

## Communication via state

Prefect uses a formal concept of `State` to reflect the behavior of the workflow at any time. Both tasks and workflows produce `States`.

## Massive concurrency

Prefect workflows are designed to be run at any time, for any reason, with any concurrency. Running a workflow on a schedule is simply a special case.

## Idempotency preferred (but not required)

We refer to idempotency as the "get out of jail free card" of workflow management systems. When tasks are idempotent, the engineering challenges become dramatically easier. However, building idempotent tasks is extremely difficult, so we designed Prefect without any assumptions of idempotency. Users should prefer idempotent tasks because they are naturally robust, but Prefect does not require them.
