# States

## Overview
States are rich objects that contain information about the status of a particular [task](../tasks) run or [flow](../flows/) run. Transitions between States are governed by [Orchestration Rules](../orchestration/). While you don't need to know the details of the states to use Prefect, you can give your workflows superpowers by taking advantage of it.

At any moment, you can learn anything you need to know about a task or flow by examining its current state or the history of its states. For example, a state could tell you:

-   that a task is scheduled to make a third run attempt in an hour
-   that a task succeeded and what data it produced
-   that a task was scheduled to run, but later cancelled
-   that a task' used the cached result of a previous run instead of re-running
-   that a task failed because it timed out

By manipulating a relatively small number of task states, Prefect flows can harness the complexity that emerges in workflows. 

!!! note "Only runs have states"
Though we often refer to the "state" of a flow or a task, what we really mean is the state of a flow _run_ or a task _run_. Flows and tasks are templates that describe what a system does; only when we run the system does it also take on a state. So while we might refer to a task as "running" or being "successful", we really mean that a specific instance of the task is in that state.

## State Types
States have names and types. State types are canonical, with specific [Orchestration Rules](../orchestration/) that apply to transitions into and out of each state type. A state's name, is often, but not always, synonymous with its type. For example, a task run that is running for the first time has a state with the name Running and the type `RUNNING`. However, if the task retries, that same task run will have the name Retrying and the type `RUNNING`. Each time the task run transitions into the `RUNNING` state, the same orchestration rules are applied.

There are three terminal state types, from which there are no orchestrated transitions to any other state type.
- `COMPLETED`
- `CANCELLED`
- `FAILED`
  
Name | Type | Terminal? | Description
| --- | --- | --- | --- |
Scheduled | SCHEDULED | No | "The task run will begin at a particular time in the future"
Late | SCHEDULED | No | "The task run's scheduled start time has passed, but it has not transitioned to PENDING (5 seconds by default)"
Awaiting Retry | SCHEDULED | No | "The task run did not complete successfully because of a code issue and had remaining retry attempts"
Pending | PENDING | No | "The task run has been submitted to run, but is waiting on necessary preconditions to be satisfied"
Running | RUNNING | No | "The task run code is currently executing"
Retrying | RUNNING | No | "The task run code is currently executing after previously not complete successfully"
Cancelled | CANCELLED | Yes | "The task run did not complete because a user determined that it should not"
Completed | COMPLETED | Yes | "The task run completed successfully"
Retrieved Cache | COMPLETED | Yes | "The state has been retrieved from the a previously created cache"
Failed | FAILED | Yes | "The task run did not complete because of a code issue and had no remaining retry attempts"
Crashed | CRASHED | No | "_Coming Soon_ - The task run did not complete because of an infrastructure issue"

## State Details
More to come
