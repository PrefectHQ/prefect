# Using Result targets for efficient caching <Badge text="0.11.0+"/>

Targets in Prefect are [templatable]((/core/concepts/templating.html)) location strings that are used to check for the existence of a task [Result](/core/concepts/results.html). This is useful in cases where you might want a task to only write data to a location once or merely not rerun if some piece of data is present. If a result exists at that location then the task run will enter a cached state. This behavior is commonly referred to as caching in Prefect and it is generally used when you do not want to recompute the result of a task if it already exists and can be retrieved easily.

The flow below will write the result of the first task to a target specified with a filepath of `{task_name}-{today}`. These values are not hardcoded and instead will be interpolated using [templating](/core/concepts/templating.html). This is a powerful construct because it means that only the first run of this task on any given day will run and write the result. Any other runs up until the next calendar day will use the cached result found at `{task_name}-{today}`.

!!! warning Result Types
    Please review the [documentation for each result type](/api/latest/engine/results.html) before you configure. Some types have specific configuration options for where to write the result.

    For example: the `LocalResult` below has an optional `dir` kwargs which accepts an absolute path to a directory for storing results and in this case the `target` value will be appended to the directory of choice.
:::

Functional API:
```python
from prefect import task, Flow
from prefect.engine.results import LocalResult

@task(result=LocalResult(), target="{task_name}-{today}")
def get_data():
    return [1, 2, 3, 4, 5]

@task
def print_data(data):
    print(data)


with Flow("using-targets") as flow:
    data = get_data()
    print_data(data)
```

Imperative API:
```python
from prefect import Task, Flow
from prefect.engine.results import LocalResult

class GetData(Task):
    def run(self):
        return [1, 2, 3, 4, 5]

class PrintData(Task):
    def run(self, data):
        print(data)

flow = Flow("using-targets")

get_data = GetData(result=LocalResult(), target="{task_name}-{today}")

print_data = PrintData()
print_data.set_upstream(get_data, key="data", flow=flow)
```


!!! warning Result Locations and Targets
    If you provide a `location` to a task's `Result` and a `target` then the target will be used as the location of the result.
:::

!!! tip Flow Result
    A `Result` can be set on the flow object and then all tasks will use that Result type. This is useful when you want to easily set all tasks in your flow to write their results to a single directory or bucket and then you could use the target as a way to verify the existence of that result prior to each task run.
:::
