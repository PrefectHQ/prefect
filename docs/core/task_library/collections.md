# Collections

The tasks in this module can be used to represent collections of task results, such as lists, tuples, sets, and dictionaries.

In general, users will not instantiate these tasks by hand; they will automatically be applied when users create dependencies between a task and a collection of other objects.

For example:

```python
@task
def count_more_than_2(inputs: set) -> int:
    return len([s for s in inputs if s > 2])

# note these tasks don't actually return a useful value
set_of_tasks = {Task(), Task(), Task()}

# automatically applies Set
count_more_than_2(inputs=set_of_tasks)
```

## List <Badge text="task"/>

Automatically combines its inputs into a Python list

[API Reference](/api/latest/tasks/collections.html#prefect-tasks-core-collections-list)

## Tuple <Badge text="task"/>

Automatically combines its inputs into a Python tuple

[API Reference](/api/latest/tasks/collections.html#prefect-tasks-core-collections-tuple)

## Set <Badge text="task"/>

Automatically combines its inputs into a Python set

[API Reference](/api/latest/tasks/collections.html#prefect-tasks-core-collections-set)

## Dict <Badge text="task"/>

Automatically combines its inputs into a Python dict

[API Reference](/api/latest/tasks/collections.html#prefect-tasks-core-collections-dict)
