# Mapping

Prefect introduces a flexible map/reduce model for dynamically executing parallel tasks.

Classic "map/reduce" is a powerful two-stage programming model that can be used to distribute and parallelize work (the "map" phase) before collecting and processing all the results (the "reduce" phase).

A typical map/reduce setup requires three things:

- An iterable input
- A "map" function that operates on a single item at a time
- A "reduce" function that operates on a group of items at once

For example, we could use map/reduce to take a list of numbers, increment them all by one, and sum the result:

```python
numbers = [1, 2, 3]
map_fn = lambda x: x + 1
reduce_fn = lambda x: sum(x)

mapped_result = [map_fn(n) for n in numbers]
reduced_result = reduce_fn(mapped_result)
assert reduced_result == 9
```

## Prefect approach

Prefect's version of map/reduce is far more flexible than the classic implementation.

When a task is mapped, Prefect automatically creates a copy of the task for each element of its input data. The copy -- referred to as a "child" task -- is applied only to that element. This means that mapped tasks actually represent the computations of many individual children tasks.

If a "normal" (non-mapped) task depends on a mapped task, Prefect _automatically_ applies a reduce operation to gather the mapped results and pass them to the downstream task.

However, if a mapped task relies on another mapped task, Prefect does not reduce the upstream result. Instead, it connects the _nth_ upstream child to the _nth_ downstream child, creating independent parallel pipelines.

Here's how the previous example would look as a Prefect flow:

```python
from prefect import Flow, task

numbers = [1, 2, 3]
map_fn = task(lambda x: x + 1)
reduce_fn = task(lambda x: sum(x))

with Flow('Map Reduce') as flow:
    mapped_result = map_fn.map(numbers)
    reduced_result = reduce_fn(mapped_result)

state = flow.run()
assert state.result[reduced_result].result == 9
```

::: tip Dynamically-generated children tasks are first-class tasks
Even though the user didn't create them explicitly, the children tasks of a mapped task are first-class Prefect tasks. They can do anything a "normal" task can do, including succeed, fail, retry, pause, or skip.
:::

## Simple mapping

The simplest Prefect map takes a tasks and applies it to each element of its inputs.

For example, if we define a task for adding 10 to a number, we can trivially apply that task to each element of a list:

```python
from prefect import Flow, task

@task
def add_ten(x):
    return x + 10

with Flow('simple map') as flow:
    mapped_result = add_ten.map([1, 2, 3])
```

The result of the `mapped_result` task will be `[11, 12, 13]` when the flow is run.

## Iterated mapping

Since `mapped_result` is nothing more than a task with an iterable result, we can immediately use it as the input for another round of mapping:

```python
from prefect import Flow, task

@task
def add_ten(x):
    return x + 10

with Flow('iterated map') as flow:
    mapped_result = add_ten.map([1, 2, 3])
    mapped_result_2 = add_ten.map(mapped_result)
```

When this flow runs, the result of the `mapped_result_2` task will be `[21, 22, 23]`, which is the result of applying the mapped function twice.

::: tip No reduce required
Even though we observed that the result of `mapped_result` was a list, Prefect won't apply a reduce step to gather that list unless the user requires it. In this example, we never needed the entire list (we only needed each of its elements), so no reduce took place. The two mapped tasks generated three completely-independent pipelines, each one containing two tasks.
:::

## Flat-mapping

In general, each layer of an iterated map has the same number of children: if you map over a list of N items, you produce N results. Sometimes, it's useful to produce a sequence of results for each mapped input. For example, you might map over a list of directories to load all the files in each directory, then want to map over each file. Prefect provides a `flatten` annotation to make this possible. When the input to a map is marked as `flatten`, the input is assumed to be a list-of-lists and is "un-nested" into a single list prior to applying the map.

Using `flatten()` is more efficient than adding a reduce step to an otherwise-iterated map, because Prefect will compute the flatmap without gathering all data to a single worker.

```python
from prefect import Flow, task, flatten

@task
def A():
    return [1, 2, 3]

@task
def B(x):
    return list(range(x))

@task
def C(y):
    return y + 100

with Flow('flat map') as f:
    a = A() # [1, 2, 3]
    b = B.map(x=a) # [[0], [0, 1], [0, 1, 2]]
    c = C.map(y=flatten(b)) # [100, 100, 101, 100, 101, 102]
```

::: tip
`flatten()` can be used on any task input, even if it isn't being mapped over.
:::


## Reduce

Prefect automatically gathers mapped results into a list if they are needed by a non-mapped task. Therefore, all users need to do to "reduce" a mapped result is supply it to a task!

```python
from prefect import Flow, task

@task
def add_ten(x):
    return x + 10

@task
def sum_numbers(y):
    return sum(y)

with Flow('reduce') as flow:
    mapped_result = add_ten.map([1, 2, 3])
    mapped_result_2 = add_ten.map(mapped_result)
    reduced_result = sum_numbers(mapped_result_2)
```

In this example, `sum_numbers` received an automatically-reduced list of results from `mapped_result`. It appropriately computes the sum: 66.


## Filter map output

If the output of one mapped task is used as input to another mapped task, any failed or skipped task will make the subsequent task fail/skip by default. However sometimes, we want to exclude skipped/failed tasks' output or outputs that are `None`. Prefect provides this functionality with `FilterTask()`.

```python
from prefect import task, Flow, context
from prefect.tasks.control_flow.filter import FilterTask
from prefect.engine.signals import SKIP

filter_results = FilterTask(
    filter_func=lambda x: not isinstance(x, (BaseException, SKIP, type(None)))
)

@task
def unstable_task(arg):
    if arg == 1:
        raise RuntimeError("Fail this task execution")
    if arg == 2:
        raise SKIP("Skip this task execution")
    if arg == 3:
        return None
 
    return arg

@task
def add_one(arg):
    return arg + 1

@task
def log_args(args):
    logger = context.get("logger")
    logger.info(args)

with Flow('filter') as flow:
    raw_out = unstable_task.map([0, 1, 2, 3, 4])
    # raw_out is [0, RuntimeError, SKIP, None, 4] at this point

    filtered = filter_results(raw_out)
    inc_out = add_one.map(filtered)

    log_args(inc_out)
    # [1, 5]
```

In the example above, `raw_out` will contain `[0, RuntimeError, SKIP, None, 4]`. Without filtering, the `RuntimeError` would mark downstream tasks as `TriggerFailed` and `SKIP` would cause downstream tasks to get the final state `Skipped` while `None` could make downstream tasks fail due to invalid input. Our `filter_results` task will filter out everything that evaluates to `False` according to the `filter_func`. This way, the flow will log the array `[1, 5]` at the end.

## Unmapped inputs

When a task is mapped over its inputs, it retains the same call signature and arguments, but iterates over the inputs to generate its children tasks. Sometimes, we don't want to iterate over one of the inputs -- perhaps it's a constant value, or a list that's required in its entirety. Prefect supplies a convenient `unmapped()` annotation for this case.

```python
from prefect import Flow, task, unmapped

@task
def add(x, y):
    return x + y

with Flow('unmapped inputs') as flow:
    result = add.map(x=[1, 2, 3], y=unmapped(10))
```

This map will iterate over the `x` inputs but not over the `y` input. The result will be `[11, 12, 13]`.

The `unmapped` annotation can be applied to any number of input arguments. This means that a mapped task can depend on both mapped and reduced upstream tasks seamlessly.

::: tip
Prefect also provides a `mapped()` annotation that can be used to indicate that an input should be mapped over when binding inputs without calling `.map()`
:::
## Complex mapped pipelines

Sometimes you want to encode a more complex structure in your mapped pipelines
- for example, adding conditional tasks using `prefect.case`. This can be done
using `prefect.apply_map`. This takes a function that adds multiple *scalar*
tasks to a flow, and converts those tasks to run as parallel *mapped*
pipelines.

For example, here we create a function that encodes in Prefect tasks the
following logic:

- If `x` is even, increment it
- If `x` is odd, negate it

Note that `inc_or_negate` is not a task itself - it's a function that creates
several tasks. Just as we can map single tasks like `inc` using `inc.map`, we
can map functions that create multiple tasks using `apply_map`.

```python
from prefect import Flow, task, case, apply_map
from prefect.tasks.control_flow import merge

@task
def inc(x):
    return x + 1

@task
def negate(x):
    return -x

@task
def is_even(x):
    return x % 2 == 0

def inc_or_negate(x):
    cond = is_even(x)
    # If x is even, increment it
    with case(cond, True):
        res1 = inc(x)
    # If x is odd, negate it
    with case(cond, False):
        res2 = negate(x)
    return merge(res1, res2)

with Flow("apply-map example") as flow:
    result = apply_map(inc_or_negate, range(4))
```

Running the above flow we get four parallel, conditional mapped pipelines. The
computed value of `result` is `[1, -1, 3, -3]`.

Just as with `task.map`, arguments to `apply_map` can be wrapped with
`unmapped`, allowing certain arguments to avoid being mapped. While not always
necessary, `apply_map` can be quite useful when you want to create complex
mapped pipelines, especially when using conditional logic within them.

## State behavior with mapped tasks

Whenever a mapped task is reduced by a downstream task, Prefect treats its children as the inputs to that task. This means, among other things, that trigger functions will be applied to all of the mapped children, not the mapped parent.

If a reducing task has an `all_successful` task, but one of the mapped children failed, then the reducing task's trigger will fail. This is the same behavior as if the mapped children had been created manually and passed to the reducing task. Similar behavior will take place for skips.
