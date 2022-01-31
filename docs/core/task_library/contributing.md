# Contributing

Contributing to Prefect's task library is a great way to assist in open source development! Generally
users have contributed tasks to the task library that accomplish a specific goal or action.

There are a few key reasons why users would want to contribute tasks to the task library:

- Gain experience contributing to an open source project
- Increase adoption for libraries, tools, and frameworks by making an easy route for users of Prefect to
interact with
- Allow for tasks to _evolve_ with Prefect meaning that as paradigms and abstractions change in Prefect
the task in the open source library will change with it
- Open up collaboration to thousands of other developers who could use your task (they might fix bugs in
the task you weren't aware of!)

Not to mention that we occasionally also send Prefect swag to some of our open source contributors!

## Task Structure

In order to build a task for the task library you need to define the task's `__init__` and `run`
functions. The `__init__` of the task will be called before the flow runs and the `run` function is where
any of your task's logic will live to be executed at runtime. Allowing for kwargs to be set both during
initialization and at runtime is key to improving a task's functionality.

One example of this separation in action would be initializing a `ShellTask` with a specific `shell` and
then passing in a different `command` at runtime. This will create two tasks in the flow, each with
different commands, without having to redefine the shell type.

```python
my_shell = ShellTask(shell="bash")

with Flow("shell_commands") as flow:
    task1 = my_shell(command="ls")
    task2 = my_shell(command="ls | wc -l")
```

(For more in depth information on the components of Prefect tasks take a look at
[The Anatomy of a Prefect Task](/core/advanced_tutorials/task-guide.html) guide.)

This snippet below is the general structure of a task contained in the task library.

```python
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

class YourTask(Task):
    """
    Task for doing something

    Args:
        - your_kwarg (string, optional): an optional kwarg
        - **kwargs: additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        your_kwarg: str = None,
        **kwargs: Any
    ):
        self.your_kwarg = your_kwarg
        super().__init__(**kwargs)

    @defaults_from_attrs("your_kwarg")
    def run(self, your_kwarg: str = None) -> str:
        """
        Run your task

        Args:
            - your_kwarg (string, optional): an optional kwarg

        Returns:
            - string: description of what it returned
        """

        # Place your specific task run logic inside this function
        return use_your_library(your_kwarg)
```

In the snippet above there is a special decorator `defaults_from_attrs`. This decorator serves the purpose
of reducing the amount of boilerplate code in the task. If a value is set via initialization of the task
and is not set again at runtime then the value set at initialization will be used in place of the absent
runtime value. However, values set at runtime will always override those set during initialization.

For more examples of how the other tasks in the task library look check out the directory
containing all of the [task library code](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/tasks).

For more information on contributing to the Prefect library as whole check out the
[development documentation](/core/development/overview.html).

### Secrets and Authentication

It is common for tasks in the task library to require some sort of authentication when interacting with
services. Prefect has a desired implementation when it comes to using credentials in a task and that is
through the use of a [Secret task](/api/latest/tasks/secrets.html). A `PrefectSecret` is a special type
of task for interacting with Prefect [secrets](/core/concepts/secrets.html) that securely represents
the retrieval of sensitive data.

Secret tasks are only able to retrieve secret data during runtime therefore it is required that your
secret values be passed into your tasks through the `run` kwargs:

```python
class YourTask(Task):
    def __init__(self, your_kwarg: str = None, **kwargs: Any):
        ...

    # Allows init kwargs to be passed to the run function if they are not overridden
    @defaults_from_attrs("your_kwarg")
    def run(self, your_kwarg: str = None, your_secret: str = None) -> str:
        authenticate_with_your_service(your_secret)
        ...
```

This allows users of the task to use Prefect Secrets to securely pass sensitive information to the task using whatever secret storage mechanism they prefer:

```python
from prefect import Flow
from prefect.tasks.secrets import PrefectSecret
from prefect.tasks.your_framework import YourTask

your_task = YourTask(your_kwarg="init kwarg")

with Flow("your-flow") as flow:
    your_secret = PrefectSecret("your_secret_name")
    your_task(your_secret=your_secret)
```

## Testing

Due to the nature of the tasks in the task library interacting with a wide range of services from various
contributors it is not always possible for Prefect to maintain tests that communicate with
all of these services. Because of this, it is integral that users who are contributing tasks to the task
library test their tasks themselves against whichever services the tasks interact with.

However, we do still encourage the contribution of unit tests! The unit tests for tasks in the task
library generally test that proper variables are set and used with accompanying mocks for the services
that they interact with. For examples of how some of the other tasks in the task library are tested check
out the [tasks testing directory](https://github.com/PrefectHQ/prefect/tree/master/tests/tasks).

## Documentation

Tasks in the task library follow Prefect's standard documentation practices as outlined in the development
[page on Documentation](/core/development/documentation.html). This means that kwargs in the task's
`__init__` and `run` function must be documented in the docstring. Check out any of the other
[tasks in the task library](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/tasks) as a
point of reference!

In order for new tasks to appear in the API documentation they need to be added to the
[`outline.toml`](https://github.com/PrefectHQ/prefect/blob/master/docs/outline.toml) file in the docs
directory:

```toml
[pages.tasks.your_task]
title = "Your Task"
module = "prefect.tasks.your_task"
classes = ["YourTask"]
```
