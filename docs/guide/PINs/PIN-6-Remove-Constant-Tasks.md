---
sidebarDepth: 0
---

# PIN-6: Remove Constant Tasks

Date: March 19, 2019

Author: Jeremiah Lowin

## Status

Declined

## Context

When a dependency is created between a task and any non-task value, Prefect automatically wraps the upstream value in a `Constant` Task and creates an appropriate edge. This "works" in the sense that it properly models a relationship between a computational node (the constant value) and a task that consumes it; but it adds noise to flow graphs that is confusing to users that don't expect it. Furthermore, it adds edge-case potential for error in some circumstance where the constant task fails (for any reason including a node crashing) and results in a difficult-to-diagnose flow failure. In addition, it creates difficulties with triggers, as the `Constant` task always succeeds.

Simply put: `Constant` tasks are confusing and do not add helpful information for users.

## Proposal

`Constant` tasks will no longer be automatically created (though they can stay in the task library, as they may be useful for particularly large objects that users only want to reference once in their flow).

Instead, if a task is attached to any constant (non-Task) value, that value is added to a new flow attribute, `flow.constant_values`. This attribute is a dictionary `Dict[Task, Dict[str, Any]]` that maps each task to a collection of input argument values. For example, if task `t` is called in the functional API as `t(x=1)`, then `flow.constants[t]` would be updated to `{t: {x: 1}}`. An additional "validation" step would ensure that the keys of `flow.constants` were always a strict subset of `flow.tasks`.

In addition, the `TaskRunner.run()` method will accept a `constant_inputs` kwarg and `FlowRunner.run()` will read and provide the appropriate values for each task. The TaskRunner is responsible for combining those with the upstream state values in order to provide all input arguments for the task itself.

## Consequences

`Constant` tasks will no longer be created (though they can remain in existence in case users find them useful for encapsulating some piece of information). Constant values that are used in a flow will be stored in a nested dictionary attached to the flow itself.

## Actions

### Reason for decline
A great deal of Prefect's execution logic is contained in the `Edge` objects - for example: the keyword (named input) for passing data, and whether the upstream value is being mapped over. In order to support constant values, we either have to duplicate the edge structure in some other form, or allow edges to connect constants to tasks (see for example [#915](https://github.com/PrefectHQ/prefect/issues/915)). Duplicating the logic is almost certainly the wrong approach, and any approach that involves extending the edge model essentially re-implements the existing task model, just without calling constants "tasks". As such, we've decided that the current approach -- constant values are represented as tasks and consequently inherit all task abilities (like named input passing and mapping) -- is the best one for now.
