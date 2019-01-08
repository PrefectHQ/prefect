# Getting Started

## Thinking Prefectly

When you build an application in Prefect, you're defining a series of computations that you want to be performed. Each **Task** represents something you want done; the **Flow** keeps track of how all the tasks interact. In this tutorial, we'll slowly build up more complex graphs to introduce new features.

## "Hello, world!"

Prefect applications are made up of discrete actions, or `Tasks`. A `Task` is like a function: it optionally accepts inputs, performs an action, and produces an optional result.

In fact, the easiest way to create a task is simply by decorating a Python function and calling it:

```python
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow('Hello, world!') as flow:
    say_hello()
```

`Flows` organize `Tasks` into workflows. Here, we created a `Flow` context and called our decorated function inside it. This tells Prefect to automatically add the task to our flow.

::: tip Delayed Execution
It's important to note that while it _looks_ like we're calling the `say_hello` function, the function isn't actually running. Calling a `Task` like a function is just a convenient way to build data pipelines that looks and feels like writing Python. In the background, Prefect keeps track of our function calls and defines a computational graph to execute in the future.
:::
Now we can run our flow:

```python
flow.run() # prints "Hello, world!"
```

## "Hello, user!"

We're only scratching the surface. Let's make a more complicated flow that says "hello!" to a particular user.

For this, we'll need to modify our task to take a `name` argument and also introduce a special kind of task called a `Parameter`. Parameters are placeholders for values that will be provided when the Flow is run. You can think of them as turning flows into functions.

```python
from prefect import Parameter

@task
def say_hello_to_name(name):
    print("Hello, {}!".format(name))

with Flow('Hello, User!') as flow:
    say_hello_to_name(name=Parameter('name'))
```

Notice how we create the `Parameter` and pass it to `say_hello_to_name` as an argument. This tells Prefect that when the flow is run, the parameter result needs to be given to `say_hello_to_name` under the keyword argument `name`.

::: tip Functional API
The easiest way to use Prefect is through its **functional API**, which is what we've used so far in this tutorial. The functional API is available inside any flow context, and allows us to call tasks on other tasks (or any value, in fact) while Prefect automatically builds the computational graph in the background.
:::
Now we can provide a parameter value whenever we run the flow:

```python
flow.run(parameters=dict(name='Marvin')) # prints "Hello, Marvin!"
flow.run(parameters=dict(name='Arthur')) # prints "Hello, Arthur!"
```

## Triggers & Reference tasks

So far, we've dealt exclusively with task dependencies that transmit data from one task to another. Prefect also supports **state dependencies** that don't involve data at all.

In this example, we create a task that always fails and another task that we want to run whenever the upstream task fails. To set up the flow, we pass `failed` to `clean_up_task` under the special keyword argument `upstream_tasks`. This argument expects a list of tasks that will have state dependencies, but no data dependency.

Note that we passed a `trigger` argument to the clean up task: `any_failed`. This means that the task will run if any of its upstream tasks fail. The default `trigger` is `all_successful`. If a trigger fails, the task itself is considered to fail.

::: tip @task arguments
The @task decorator accepts all of the initialization arguments for the `Task` class, including `trigger`, as demonstrated here.
:::

```python
import prefect

@task
def bad_task():
    1/0

@task(trigger=prefect.triggers.any_failed)
def clean_up_task():
    print('All set!')

with Flow('triggers') as flow:
    failed = bad_task()
    clean_up = clean_up_task(upstream_tasks=[failed])

flow.set_reference_tasks([failed])

flow.run() # prints "All set!"
```

::: tip Imperative API
In addition to the functional API, Prefect has an imperative API that allows finer-grained control over task dependencies. `Tasks` and `Flows` have a `set_dependencies()` method that allows dependencies -- both state and data -- to be set explicitly. The imperative API is most commonly used when building flows programmatically, or when the flow is characterized more by state dependencies than data dependencies.
:::

By default, Prefect decides the state of a flow run by examining the states of the flow's terminal tasks. If all terminal tasks succeeded, the flow succeeds; if any terminal tasks failed, the flow fails.

In this flow, the main task failed but a terminal clean-up task succeeded. Therefore, Prefect would conclude that the flow worked as intended and mark it successful. However, you might prefer this flow to be considered a failure -- after all, its main task failed.

Prefect has a feature called `reference_tasks` for this purpose. By default, a flow's `reference_tasks` are its terminal tasks, but users can change them by calling `flow.set_reference_tasks()`. In this case, setting the `failed` as a reference task would result in the flow being considered failed when it was run.

## Custom Tasks & Signals

We can easily create custom task classes. All a task requires is a `run()` method. One advantage of custom tasks is they can access attributes created in their `__init__()` method.

Here, we create an addition class that raises an error if the values aren't above a certain threshold. This also introduces a new concept: `signals`. Prefect tries very hard to guess the right state for a task - if the `run()` method succeeds, it's successful; if it has an error, it fails. Sometimes, you want more control over a task's state. Prefect provides various `signals` to indicate desired state changes. Common ones include `RETRY` and `SKIP`, to force those behaviors, but `FAIL` and `SUCCESS` can be useful as well.

::: tip __init__() vs run()
In general, anything that can be provided to a custom task's `__init__()` function could also be provided as an argument to the `run()` function. The decision of how to parameterize a custom task class largely depends on how you want users to interact with the class.

As a guideline, consider whether the information needs to be available to any other tasks besides this one (including other instances of the same class). If it does, it may represent a key part of your pipeline and belong in the flow itself; if not, it's a local variable and more appropriate for `__init__()`.
:::

```python
from prefect import Task, Flow, Parameter
from prefect.engine import signals

class ThresholdAddition(Task):
    def __init__(self, threshold, **kwargs):
        self.threshold = threshold
        super().__init__(**kwargs)

    def run(self, x, y):
        result =  x + y
        if result < self.threshold:
            raise signals.FAIL('Result was too low!')
        return result

with Flow('Custom Tasks - Functional') as flow:
    add = ThresholdAddition(threshold=10)

    x = Parameter('x')
    y = Parameter('y')

    add(x, y)


state = flow.run(parameters=dict(x=1, y=2)) # FAILED
state = flow.run(parameters=dict(x=10, y=20)) # SUCCESS
```

::: warning Tasks Don't Have a Memory
Inside a task's `run()` method, it can be tempting to assign a value to `self` in order to access it later, perhaps on a future run of the task. An example would be to count the number of times a task was called.

While that might work in local testing, it won't work in a distributed Prefect environment. The `Task` object that gets evaluated each run won't be the same one that was evaluated previously -- in fact, it may not even be running in the same process, or on the same computer!

Prefect has other mechanisms for storing state; do not use task classes to do so.
:::

## What's Next?

Check out the [Prefect tutorials](/tutorials/) for more examples, or the [core concepts](/concepts/) for a more detailed look at specific features.
