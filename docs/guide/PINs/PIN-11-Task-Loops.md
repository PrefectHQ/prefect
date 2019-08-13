# PIN 11: Task Loops

Date: July 27, 2019
Author: Jeremiah Lowin

# Status

Accepted

# Context

Prefect currently exposes a few important control-flow mechanisms, including `ifelse` and, more dynamically, `mapping`. However, users who want to either loop over tasks sequentially (mapping does not work sequentially), or loop over tasks with an unknown terminal condition (mapping requires known inputs) have no first-class operation available. They must implement the loop logic themselves, inside a task.

Examples where looping matters:

- accumulation: a result is generated in each iteration that matters for later iterations. Training a machine learning model is a complex example of this; Fibonacci sequences are a simpler one.

- querying with pagination: if the number of pages is unknown, we want to continue the operation until a terminal condition is met.

Most workflow frameworks act as if looping is impossible (stressing the *A*cyclic part of the DAG), but it's actually trivial to implement. We simply dynamically unroll the loop, similar to how RNN gradients are sometimes computed.

# Proposal

A new state is introduced, `Loop` (or `Rerun` or something else). In addition to `map_index`, the TaskRunner also tracks a `loop_index`.

If a task raises a `Loop` state, the TaskRunner intercepts it and immediately re-runs the task with two modifications:

- the `loop_index` of the taskrun is incremented by one (it defaults to 0)
- the `Loop` state's `result` attribute is added to context (perhaps `prefect.context.loop_result`).

If the task does not raise a state, and simply returns as normal, the loop ends.

```python
@task
def accumulate(x, iterations):
    result = x + prefect.context.get("loop_result", 0)
	if prefect.context.loop_index < iterations:
        raise LOOP(result=result)
    return result

with Flow("looping accumulator") as flow:
    y = accumulate(x=1, iterations=5)

flow.run() # y = 6
```

# Consequences

Users will be able to create single-task loops that immediately comply with all existing assumptions of Prefect (including Cloud with no changes if we reuse `map_index` for `loop_index`).

# Actions
