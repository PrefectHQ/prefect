---
title: 'PIN-4: Result Objects'
sidebarDepth: 0
---

# PIN-4: Result Objects for Tracking and Serializing Task Outputs

2019-01-30
Jeremiah Lowin

## Status

Accepted; furthers the objectives of [PIN-2](PIN-2-Result-Handlers.md)

## Context

Task results are a key part of any data pipeline, and in Prefect they have special meaning. Because Prefect tasks do not merely return data, but rather `States`, we have a wide variety of possible actions beyond simply passing the output of one task to the next task.

For example, we might allow a task to cache its output and return it in the future without repeating an expensive computation. We might detect that a state is going to be retried, and therefore cache all of its inputs so they'll be available in the future. We might greedily write every task's result to disk in order to pessimistically defend against node failures. We might even... simply pass the result to the next task.

Because of all these possible actions and the need to apply them to essentially arbitrary Python objects, Prefect requires a great deal of result handling logic. This largely comes down to three buckets:

- Moving results through the system
- Knowing how to serialize results for remote storage
- Serializing results for remote storage

Some of these are far more deceptive than they seem. For example, if task A passes a result to task B, and task B needs to retry, then task **B** is responsible for serializing the result of task **A** -- after all, A has no way of knowing that its result will be reused in the future. This may be surprising to someone unfamiliar with Prefect (and fortunately is an internal detail users don't need to know!). This implies that it isn't enough for A to know how to serialize its own results; B must know how to serialize A's result as well.

As I write this, Prefect is doing a great job of handling all of the above cases. [PIN-2](PIN-2-Result-Handlers.md) introduced many of the required mechanisms for doing this in a distributed way, interacting with remote servers.

However, the logic for working with results has spread across a few classes -- it manifests with special methods in the `TaskRunner` class (where results must be parsed out of `upstream_states`), a series of `ResultHandler` objects, methods for setting/getting results on `State` objects, and a complex `State._metadata` object for tracking how to serialize results as well as whether they have, in fact, been serialized. For example, consider PRs [#581](https://github.com/PrefectHQ/prefect/pull/581) and [#595](https://github.com/PrefectHQ/prefect/pull/595).

It is desirable to consolidate all of this state handling logic into a single location, as much as possible. This has a few benefits:

- single object to test and work with, with a known API
- type safety and introspection via `mypy`
- more formal contracts for serializing results via `marshmallow` schemas
- reduction of development burden, since contributors can write methods that work with results without needing to also know exactly how to work with those results.

To be clear, this PIN represents an evolution of the mechanisms introduced by [PIN-2](PIN-2-Result-Handlers.md). It represents the same logic, just refactored with the benefit of seeing it in action.

## Proposal

### Result class

We will implement a `Result` class that contains information about:

1. the value of a task's result
2. whether that value has been serialized
3. how to serialize or deserialize the result

**Note: throughout this document I use the terms "serialized" and "serializer" where currently we use "raw" and "result_handler", because the current terms seem inconsistent if they are both attributes of the same object. Another alternative -- "handled" and "handler" -- seems insufficiently descriptive.**

The signature of this object is:

```python
class Result:
    value: Any
    serialized: bool
    serializer: `ResultSerializer`

    def serialize(self) -> Result:
        """
        Return a new Result that represents a serialized version of this Result.
        """
        value = self.value
        if not self.serialized:
            value = self.serializer.serialize(self.value)
        return Result(value=value, serialized=True, serializer=self.serializer)

    def deserialize(self) -> Result:
        """
        Return a new Result that represents a deserialized version of this Result.
        """
        value = self.value
        if self.serialized:
            value = self.serializer.deserialize(self.value)
        return Result(value=value, serialized=False, serializer=self.serializer)


class ResultSerializer:

    def serialize(self, value: Any) -> JSONLike:
        """serialize a result to a JSON-compatible object"""

    def deserialize(self, blob: JSONLike) -> Any:
        """deserialize a result from a JSON-compatible object"""
```

As an extension, we might also consider a `NoResult` class that would be the initial (default) value for any State. This would help us differentiate between a `State` that had been run and produced a `None` result, and a `State` that had no result attached.

### State

We will change states to have the following signature:

```python
class State:
    """
    I'm only showing attributes that are different from their current implementations on any State class;
    note that some of these are only defined on various State subclasses.

    Also note there is no _metadata attribute.
    """
    _result: Result
    cached_inputs: Dict[str, Result]

    @property
    def result(self) -> Any:
        """
        This property is to maintain the current user-friendly API in which state.result is
        a Python value, not a Prefect internal object
        """
        return self._result.value
```

The `_metadata` object is removed.

We will also modify the various `StateSchema` objects to use a new `ResultSchema` object as a nested field. This `ResultSchema` will automatically call `Result.serialize()` whenever it is asked to `dump()` a `Result` with `serialized=False`. While serialization could also be performed explicitly, this check will ensure that states (and their results) are JSON-compatible.

This means that user code should never have to actually serialize results. It can work with them while knowing that the Prefect serialization mechanisms will automatically apply the correct `ResultSerializer` whenever a state is serialized for transport, for example to Cloud.

However, deserialization should probably not take place automatically. We may be preloading many states, and we should only deserialize the result if and when it's actually needed. For this reason, deserialization can take place somewhere like the `get_task_inputs()` or `initialize_run()` pipeline steps.


### TaskRunner

These changes would dramatically simplify the various methods in the `TaskRunner` class. For example, right now, after assigning `state.cached_inputs = <inputs>`, the user must then call `state.update_input_metadata(<upstream_states>)` in order to hydrate the metadata for those inputs, based on information loaded out of the task's upstream states.

This new setup would allow simply setting cached inputs and moving on:

```python
inputs = {
    'x': upstream_task_1._result, #type: Result
    'y': upstream_task_2._result, #type: Result
}
state.cached_inputs = inputs
```

Now, the `cached_inputs` attribute of that state has all the information required to serialize the results that were received from the upstream state.

Given the above `inputs` dictionary, calling the task's `run()` method could just be:

```python
value = task.run(**{k: v.value} for k, v in inputs.items())
result = Result(value=value, serialized=False, serializer=task.serializer)
```

### FlowRunner

Despite all of this, the FlowRunner would require no changes. It would return an object that could still be accessed in the exact same way we do today:

```python
state = flow.run()

# the value returned by task "x"
state.result[x].result
```

### CloudRunners

If the marshmallow schemas for states were properly configured to serialize `Results` (as described in the **State** section, above), then the `CloudTaskRunner` would have to do _no new work_ to properly sanitize state results for transport. Simply serializing the `State` object would take care of all necessary work. With that said, serialization could also be done explicitly. Since serialization yields a new `Result` object, the original `State` could remain unchanged and be passed to downstream tasks with the "raw" result, while the serialized `Result` gets shipped to Cloud.

However, as described earlier, `CloudTaskRunners` should probably be responsible for deserializing results at the appropriate time (perhaps this is even something the base TaskRunner should do, as a universal check?).


## Consequences

Adopting these new classes would dramatically simplify a great deal of logic that is very important to how Prefect operates. Rather than distributing that logic throughout the `State` class, `TaskRunner` class, and `CloudTaskRunner` class; it would live in a single place: the `Result` object. Moreover, while the `Result` object contains all information for properly serializing/deserializing its value, the actual _calling_ of the serialization methods could be delegated almost exclusively to Prefect's existing schema serializers. Users (probably) would never have to do this by hand.

## Actions
