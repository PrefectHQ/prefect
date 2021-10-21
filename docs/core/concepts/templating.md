# Templating names

There are several places within Prefect where names can be templated at runtime to create a value relevant to that specific run.
These names can be passed as literal strings, e.g. `"my_foo_task"`, but to get dynamic values based on the current state, we'll need to use _template_ strings.
Here, we take advantage of Python's [format string](https://www.python.org/dev/peps/pep-3101/#format-strings) and provide various arguments.
Instead of a static string, you'll pass a string that will be formatted at runtime, e.g. `"foo-{today}"`, where `today` is the name of one of the variables we provide.

## Where can I use templating?

Templating is available for:

- [Task run names](/core/idioms/task-run-names.html)
- [Task target paths](/core/idioms/targets.html)
- [Task result locations](/core/concepts/results.html#templating-result-locations)

## What variables can I use?

All templatable objects are passed:

- The [Parameters](/core/concepts/parameters.html) of the flow
- The contents of the [Prefect context](/api/latest/utilities/context.html)
- The inputs to the task

::: warning Naming collisions

The variables are loaded in the order shown above. Collisions will be resolved such that the last loaded value overwrites those above it. For example, if your a task input name is the same as the name of a variable in the context, the input variable value will overwrite context value.

:::

## Examples


### Using task inputs

The name can be a templatable string like `"{val}"`. Make sure not to try to format the string early, e.g. `f"{val}"` as this will be formatted when your flow is *defined* rather than when it is *run*.

Here's an example that uses the task input to determine the name.

```python
from prefect import task, Flow

@task(task_run_name="{val}")
def compute(val):
    pass

with Flow("template-example") as flow:
    compute(val="hello")
```

### Callable name generators

Templates can also be callables, which give you the ability to do more complex determinations.

```python
from prefect import task, Flow


def generate_task_run_name(val: str, **kwargs):
    """
    Replace spaces with '-' and truncate at 10 characters.

    You can specify some arguments if you know they will be passed, but you must take
    **kwargs to consume the rest of the passed values from the context or an exception
    will be thrown.
    """
    val = val.replace(" ", "-")
    if len(val) > 10:
        val = val[:10]
    return val

@task(task_run_name=generate_task_run_name)
def compute(val: str):
    pass

with Flow("template-example") as flow:
    compute(val="hello this is a kind of long sentence")
```


### Using flow parameters

All parameters in the flow are made available, even if not used in the task. Here's an example using a Parameter to template a local result location.

```python
import os
from prefect import task, Flow, Parameter
from prefect.engine.results import LocalResult

result_basepath = Parameter("result_basepath", default="~")

def format_location(result_basepath, task_name, **kwargs):
    # Notice we expand the user at runtime so the user of the parameter
    # does not need to worry about the path to the home directory on the
    # server that the flow runs on
    return f"{os.path.expanduser(result_basepath)}/{task_name}.prefect"

@task(result=LocalResult(location=format_location))
def my_task():
    return [1, 2, 3, 4]

with Flow("local-result-parametrized") as flow:
    my_task()

# Ensure the parameter is registered to the flow even though no task uses it
flow.add_task(result_basepath)
```

### Formatting dates

The context contains a `pendulum` `DateTime` object which allows manipulation of the timestamp. For example, this writes the result to `~/2020-12_my_task.prefect`.

```python
import os
from prefect import task, Flow,
from prefect.engine.results import LocalResult


def format_location(date, task_name, **kwargs):
    return os.path.join(
        os.path.expanduser("~"), f"{date.year}-{date.month}_{task_name}.prefect"
    )

@task(result=LocalResult(location=format_location))
def my_task():
    return [1, 2, 3, 4]

with Flow("local-result-with-date-parsing") as flow:
    my_task()
```

::: tip Python date formatting

You can also format dates with the [Python built-in formatting](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior). 
For example, the following will create a name like `Tuesday-Dec-29`

```python
from prefect import task, Flow

@task(task_run_name="{date:%A}-{date:%b}-{date:%d}")
def compute():
    pass

with Flow("template-example") as flow:
    compute()
```

:::
