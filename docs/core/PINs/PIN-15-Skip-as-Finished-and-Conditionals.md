---
title: 'PIN-15: Skip state refactor & conditionals'
sidebarDepth: 0
---

# PIN 15: Skip state as Finished + Control Flow Conditional

Date: February 24, 2020

Author: Alex Goodman

## Status

Declined (_see bottom of page for reason_)

## Context

The [ControlFlow](/api/latest/tasks/control_flow.html) Tasks allow for users to branch conditionally within the execution graph, skipping some tasks and allowing execution of others. However, [back-to-back conditions](https://github.com/PrefectHQ/prefect/issues/2017) have proven to be a problem under the existing implementation. Specifically, the problem appears to be with the semantics with the “Skip” Prefect State: it is considered to be fundamentally a “Success” state. That is, it is not easy (if impossible) to determine why a task was skipped, and if ignoring that Skipped state is OK. This means that using `skip_on_upstream_skip` is not a good enough mechanism to implement back-to-back conditions and hints that more functionality is needed. Additionally, the current semeantics imply that a Skipped Task was never run, however, it is possible for a Task to manually raise the `SKIP` signal mid-execution. Overall, the above points hint that a base class of `Success` for the `Skipped` state is probably not accurate.

Furthermore, indicating when a trigger condition is not met can also be misleading. By raising the TRIGGERFAIL, a `Failed` state propagates through downstream tasks, which could be misconstrued as these downstream tasks failing, when in fact they have semantically been skipped. Take the following flow as an example:

```python
@prefect.task()
def a(): pass

@prefect.task(trigger=prefect.triggers.any_failed)
def b(): pass

@prefect.task()
def c(): pass

with prefect.Flow("My Flow") as flow:
    flow.chain(a, b, c)
```

Running this flow will result in `A` completing successfully, followed by `B` and `C` having never been executed yet be in `TriggerFailed` states. However, consider adding an `any_failed` trigger to `C`:

```python{7}
@prefect.task()
def a(): pass

@prefect.task(trigger=prefect.triggers.any_failed)
def b(): pass

@prefect.task(trigger=prefect.triggers.any_failed)
def c(): pass

with prefect.Flow("My Flow") as flow:
    flow.chain(a, b, c)
```

This will result in `B` in a `TriggerFailed` state followed by `C` completing successfully, which is arguably surprising behavior.

Ideally, a trigger should be the gatekeeper for Task exection: either attempt to run the current Task (or not) based on upstream states. Or said another way, attempt to run the current Task or Skip it --this does not imply a `Failed` (or `Success`ful) state being determined yet, as that should be the result of the Task itself.

## Proposal

This PIN proposes to enhance conditionally executing Tasks within Flows. Ultimately, the proposal is:

1. Change the underlying base State of “Skip” from “Success” to “Finished”. This is more semantically correct: the task has neither completed successfully or in error, it has only completed. If it was not in a completed state it could be misconstrued with a pending-like state, however, we have already determined that no further action is necessary thus it has completed.

Given that it is no longer necessary to stop the continued execution now that Skip is no longer a “Success” state, there are further implied changes:

2. Any triggers that raise `TRIGGERFAILED` signal should now raise `SKIP` instead.

3. Remove `skip_on_upstream_skip` as a Task argument (this can be handled by a user electing to use the new `no_failed` trigger, introduced later).

4. Remove the `TaskRunner.check_upstream_skipped` state logic.

Once these changes are made there is an opportunity to add additional functionality:

5. Add a new `no_failed` trigger, which passes if there are no failed states upstream.

6. Introduce a `conditional` object that acts similar to `switch`, supporting only a single case (the `True` case). This will be a `task.run` wrapper instead of adding an additional CompareValue task. Any task can be a condition, a truthy value will be determined by the result of the given task, and if determined to be “False” then `FAIL` is raised.

   Example usage (within a flow context):
   `conditional(is_b_enabled, b_task)`
   instead of
   `switch(is_b_enabled, {True: b_task})`

7. Add the ability to combine conditions: add `any_condition` and `all_conditions` reducing functions to `prefect.tasks.control_flow.conditional`. This would add an additional task to the flow, with upstreams being the individual conditions, and the new task emitting a “True” result or raising a `FAIL`.

   Example usage (within a flow context):
   `conditional(all_conditions(is_a_enabled, another_task), a_task)`

## Consequences

Back-to-back `switch` usage would be possible (since `skip_on_upstream_skip` is no longer the mechanism used to determine if a task should respond to upstream Skip).

## Actions

Release the changes in two batches:

1. First release (breaking changes):

   a. Add deprecation warnings for uses of `TRIGGERFAIL` signal, `TriggerFailed` state, and `skip_on_upstream_skip` Task option usage

   b. Implement proposal items 1-7

2. Second release (breaking changes):

   a. Remove functionality for `TRIGGERFAIL` signal, `TriggerFailed` state, `skip_on_upstream_skip`

### Reason for declining

The motivations for this PIN are sound however they require the designing of a new API in order to support. This proposal focuses on using triggers as the place for conditional logic however that fails to keep in tune with the original purpose of triggers. Changing the main state function of triggers to skip instead of failure when not satisfied will cause even simple flows to not behave properly as originally defined by the paradigm of the Prefect engine.

Say there existed a flow containing the edge `Task_1 -> Task_2`. Under this proposal if `Task_1` were to enter a `Failed` state then the default `all_successful` trigger of `Task_2` would raise a `SKIP` signal instead of a `TriggerFailed`. Since `Task_2` is a reference task for this flow the final state will be `Success` even though the intendened state is for the flow to enter `Failed`.

There is no doubt room for a better API which encapsulates the ideas outlined here, perhaps something that lives next to triggers on tasks called _conditions_. However, this PIN is not the official proposal for that functionality and is being declined.
