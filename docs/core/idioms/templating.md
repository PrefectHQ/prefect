# Templating names

There are several places within Prefect where names can be templated at runtime to create a value relevant to that specific run.
These names can be passed as literal strings, e.g. `"my_foo_task"`,  but to get dynamic values based on the current state, we'll need to use _template_ strings.
Here, we take advantage of Python's [format string](https://www.python.org/dev/peps/pep-3101/#format-strings) and provide various arguments.
Instead of a static string, you'll pass a string that will be formatted at runtime, e.g. `"foo-{today}"`, where `today` is the name of one of the variables we provide.

## Where can I use templating?

Templating is available for:

- [Task run names](/core/idioms/task-run-name.html)
- Task target paths
- [Task result locations](/core/concepts/results.html#templating-result-locations)

## What variables can I use?

All templatable objects are passed:

- The contents of the [Prefect context](/api/latest/utilities/context.html)
- The [Parameters](/core/concepts/parameters.html) of the flow
- The inputs to the task

## Examples

The name can just a templatable string like `"{val}"`. Make sure not to try to format the string early, e.g. `f"{val}"` as this will use whatever value of `val` is available when you write the flow, not when the flow is running (or throw an exception because there is no value yet).

Here's an example that uses the task input to determine the name.

```python
from prefect import task, Flow

@task(task_run_name="{val}")
def compute(val):
    pass

with Flow("template-example") as flow:
    compute(val="hello")
```

Templates can also be callables, which give you the ability to do more complex determinations.

```python
from prefect import task, Flow

# You can specify some arguments if you know they will be passed, but you must take
# **kwargs to consume the rest of the passed values from the context
def generate_task_run_name(val, parameters, **kwargs):
    double_val = val * 2
    return double_val


@task(task_run_name=generate_task_run_name)
def compute(val):
    pass

with Flow("template-example") as flow:
    compute(val="hello")
```


```python
import prefect
from prefect import task, Flow
from pprint import pformat

# You can specify some arguments if you know they will be passed, but you must take
# **kwargs to consume the rest of the passed values from the context
def display_available_data(**kwargs):
    prefect.context.logger.info(pformat(kwargs))
    return "ha-no-name"

@task(task_run_name=display_available_data)
def compute(val):
    pass

with Flow("template-example") as flow:
    compute(val="hello")
```