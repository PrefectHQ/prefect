---
sidebarDepth: 0
---

# The Anatomy of a Prefect Task

> Everything you wanted to know about Prefect Tasks and more.

**Contents**

- [The Basics](#the-basics)
- [Running Tasks](#running-tasks)
- [Task Inputs and Outputs](#task-inputs-and-outputs)
- [Adding Tasks to Flows](#adding-tasks-to-flows)
- [Mapping](#mapping)
- [Best Practices in Writing Tasks](#best-practices-in-writing-tasks)
- [State Handlers](#state-handlers)

## The Basics

In simple terms, a Prefect Task represents an individual unit of work. For example, all of the following could qualify as a Prefect Task:

- querying a database
- formatting a string
- spinning up a Spark cluster
- sending a message on Slack
- running a Kubernetes Job
- creating a simple dictionary

In addition to performing some action, Tasks can optionally receive inputs and / or return outputs. _All_ of this "runtime" logic lives inside a single method on your Task class: the `run` method.

!!! tip If you can write it in Python, you can do it in a Prefect Task
    When the run method of your task is called, it is executed as Python code. Consequently, if you can do it in Python, you can put it inside the `run` method of a Prefect Task.

    There are still a few considerations though:

    - if you utilize timeouts, this sometimes relies on multiprocessing / multithreading which can interfere with how resource intensive your Task can be
    - make sure that you understand the possible restrictions on [Task inputs and outputs](#task-inputs-and-outputs)

Generally speaking, there are two preferred methods for creating your own Prefect Tasks: using the `@task` decorator on a function, or subclassing the Prefect `Task` class. Let's take a look at an example of each of these individually by writing a custom task which adds two numbers together.

#### Subclassing the `Task` class

Subclassing the `Task` class is the preferred method for creating Tasks when you want a reusable, parametrizable Task interface (for example, when adding a Task to the [Prefect Task Library](https://docs.prefect.io/core/task_library/)). All of your runtime logic is implemented inside of the Task's `run` method:

```python
from prefect import Task


class AddTask(Task):
    def run(self, x, y):
        return x + y

add_task = AddTask(name="Add")
add_task # <Task: Add>
```

Here we have created a Prefect Task named "Add" which receives two inputs (called x and y), and returns a single output. Note that we had to _instantiate_ our custom Task class in order to reach a proper Prefect Task object.

#### The `@task` decorator

We can avoid the object-oriented boilerplate altogether by writing a custom Python function and using the `@task` decorator:

```python
from prefect import task

@task(name="Add")
def add_task(x, y):
    return x + y

add_task # <Task: Add>
```

Here we have created an equivalent Task to the one above - the `@task` decorator essentially assigns this function as the `run` method of the underlying Task class for us. A few observations are in order:

- the `@task` decorator _instantiates_ a Prefect Task automatically
- all [Task initialization keywords](https://docs.prefect.io/api/latest/core/task.html#task-2) can be provided to the decorator
- if you choose not to provide a name, the function name will be used as the Task name

!!! warning Call signatures cannot be arbitrary
    When implementing a Prefect Task, whether via subclassing or the decorator, there _are_ some minor restrictions on your Task's call signature:

    First, all arguments to Prefect Tasks are ultimately treated as keyword arguments. This means that arbitrary positional arguments (usually written `*args`) are _not_ allowed.

    In addition to disallowing `*args`, the following keywords are reserved and cannot be used by custom Prefect Tasks:

    - `upstream_tasks`: reserved for specifying upstream dependencies which do not exchange data
    - `mapped`: reserved for internal implementation details of mapping
    - `task_args`: reserved as a way of overriding task attributes when creating copies in the functional API
    - `flow`: reserved for internal implementation details

    Lastly, Prefect must be able to `inspect` the function signature in order to apply these rules. Some functions, including `builtins` and many `numpy` functions, can not be inspected. To use them, wrap them in a normal Python task:

    ```python
    @task
    def prefect_bool(x):
        """
        `prefect.task(bool)` doesn't work because `bool` is
        a `builtin`, but this wrapper function gets around the restriction.
        """
        return bool(x)
    ```

    If you violate any of these restrictions, an error will be thrown immediately at Task creation informing you.


### Prefect Context contains useful information

Sometimes it is useful to have additional information within your Task's runtime logic. Such information is provided via Prefect's `Context` object. `prefect.context` is a dictionary-like object (with attribute access for keys) containing useful runtime information. For example, your Task's logger is stored in Prefect Context for adding custom logs to your task.

```python
import prefect

@prefect.task
def log_hello():
    logger = prefect.context["logger"]
    logger.info("Hello!")
```

Note that context is only populated _within a Flow run_. This is important to be aware of when testing your task outside of a Flow run. For a complete list of information available in Prefect Context, [see the API documentation](https://docs.prefect.io/api/latest/utilities/context.html). For more information on how context works, see the associated [Concept Doc](https://docs.prefect.io/core/concepts/execution.html#context). Note that `context` has a graceful `.get` method for accessing keys which are not guaranteed to exist.

## Running Tasks

Most users want to run their tasks outside of a Flow to test that their logic is sound. There are a few different ways of running your Task locally, with varying complexity:

#### Calling your Task's `run` method

This is the most straightforward way to test your Task's runtime logic. Using our `add_task` from above (the method of creation is irrelevant at this stage), we have:

```python
add_task.run(1, 2) # returns 3
add_task.run(x=5, y=-10) # returns -5
add_task.run(x=[1, 2], y=[3, 4]) # returns [1, 2, 3, 4]
```

In this way, testing and running your Task is as simple as testing any class method, with very minimal Prefect overhead to get in your way.

#### Using a `TaskRunner`

If you're interested in testing your Task as Prefect sees it, using a `TaskRunner` can be beneficial. Prefect `TaskRunner`s are designed to handle all of the surface area _around_ your runtime logic, such as:

- are the upstream tasks finished?
- are the upstream tasks in an appropriate state, as specified by your Task's trigger?
- is your Task mapped, and should it spawn multiple copies of itself?
- is your Task running on Cloud, and should it set its state in the Cloud database?
- does your Task have result persistence configured, or state handlers that need to be called?
- what State should your Task run be in after it has run?

To see this in action, let's run a Task which requires no inputs.

```python
from prefect import task
from prefect.engine import TaskRunner


@task
def number_task():
    return 42

runner = TaskRunner(task=number_task)
state = runner.run()

assert state.is_successful()
assert state.result == 42
```

In this case, the `TaskRunner` doesn't actually return the value of the Task's `run` method, but instead returns a [Prefect `Success` state](https://docs.prefect.io/api/latest/engine/state.html#success) which has the return value stored in its `result` attribute.

We can now begin to do more interesting things, such as provide upstream states to test our trigger logic:

```python
from prefect import Task
from prefect.core import Edge
from prefect.engine.state import Failed

# the base Task class provides a useful stand-in for a no-op Task
upstream_edge = Edge(Task(), number_task)
upstream_state = Failed(message="Failed for some reason")

state = runner.run(upstream_states={upstream_edge: upstream_state})

# our Task run is in a TriggerFailed state
# and its corresponding result is the exception that was caught
assert state.is_failed()
assert isinstance(state.result, Exception)
```

This brings you into Prefect implementation details very quickly, but the important takeaway here is that using a `TaskRunner` allows us to test all of the Prefect settings on our Task as a standalone unit (without the backdrop of a Flow).

If you are interested in pursuing this further, the following API reference documents may be useful:

- [Edges](https://docs.prefect.io/api/latest/core/edge.html)
- [TaskRunner](https://docs.prefect.io/api/latest/engine/task_runner.html#taskrunner-2)
- [States](https://docs.prefect.io/api/latest/engine/state.html#state-2)
- [Triggers](https://docs.prefect.io/core/concepts/execution.html#triggers)

!!! tip Flows have runners, too
    In addition to `TaskRunner`s, Prefect also has a concept of a `FlowRunner`, which is the object responsible for making a _single_ pass through your Flow and its task states. The keyword arguments on the `run` method of both Task and Flow runners are useful to explore when testing your Flows.


## Task Inputs and Outputs

In many workflow systems, individual "Tasks" are only allowed to report a minimal set of information about their state (for example, "Finished", "Failed" or "Successful"). In Prefect, we encourage Tasks to actually exchange richer information, including "arbitrary" data objects.

However, there _can_ be restrictions on what tasks can receive as inputs and return as outputs. In particular, Prefect's most popular executor is the `DaskExecutor`, which allows users to execute tasks on a cluster; because each machine is running a different Python process, Dask must convert Python objects to bytecode that can be shared between different processes. Consequently, the data that is passed around the Prefect platform must be compatible with this serialization protocol. Specifically, tasks must operate on objects that are serializable by the [`cloudpickle` library](https://github.com/cloudpipe/cloudpickle).

**What can cloudpickle serialize?**

- most data structures, including lists, sets, and dictionaries
- functions (including lambda functions)
- most classes, as long as their attributes are serializable

**What can’t cloudpickle serialize?**

- generators
- file objects
- thread locks
- deeply recursive classes

**How can I determine if something is serializable?**

Import `cloudpickle` and attempt to make the round trip:

```python
import cloudpickle

cloudpickle.dumps(None)
# b'\x80\x04\x95\x02\x00\x00\x00\x00\x00\x00\x00N.'

obj = cloudpickle.loads(cloudpickle.dumps(None))
assert obj is None

custom_generator = (x for x in range(5))
cloudpickle.dumps(custom_generator)
# TypeError: can't pickle generator objects
```

This subtle and technical constraint actually informs a lot of design decisions in the Task library ([as we will see shortly](#best-practices-in-writing-tasks)). Moreover, users will undoubtedly run into this situation on occasion, and it’s important to recognize the types of errors that arise when this constraint is violated. Also, as you write your own flows, keep this in mind when you design your Tasks and how they communicate information.

## Adding Tasks to Flows

Now that you've written your Tasks, it's time to add them to a Flow. Sticking with the `number_task` created above, let's add this Task to our Flow using Prefect's Imperative API:

```python
from prefect import Flow

f = Flow("example")
f.add_task(number_task)

print(f.tasks) # {<Task: number_task>}
```

So far, so good - our Flow now consists of a single task. How might we add a single task to a Flow using the Functional API? In this instance, we have to perform some _action_ on the Task to "register" it with the Flow. In general, Tasks will be auto-added to a Flow in the functional API if one of the following is true:

- the task is _called_ within a Flow context _or_
- the task is called as a dependency of another task

In this case, because we have a single Task and no dependencies, we must resort to _calling_ the instantiated Task:

```python
with Flow("example-v2") as f:
    result = number_task()

print(f.tasks) # {<Task: number_task>}
```

!!! warning Calling Tasks creates copies
    Using the example above, you might be surprised to find:

    ```python
    number_task in f.tasks # False
    result in f.tasks # True
    ```

    This is because _calling_ a Prefect Task actually creates a _copy_ of that Task and _returns_ that copy. This allows for natural feeling Python patterns such as calling a Task multiple times with different inputs to create different outputs.

    Whenever a copy is created, you can optionally override any / all task attributes via the special `task_args` keyword:

    ```python
    with Flow("example-v3") as f:
        result = number_task(task_args={"name": "new-name"})

    print(f.tasks) # {<Task: new-name>}
    ```

    This can be useful for overriding Task triggers, tags, names, etc.



To see some of these subtleties in action, let's work out a more complicated example using our `add_task` Task created above. First, let's use the [`set_dependencies` method](https://docs.prefect.io/api/latest/core/flow.html#prefect-core-flow-flow-set-dependencies) of the imperative API:

```python
f = Flow("add-example")

f.set_dependencies(add_task, keyword_tasks={"x": 1, "y": 2})
print(f.tasks) # {<Task: add_task>}
```

Now, let's switch our attention to the functional API and reproduce the above example exactly:

```python
with Flow("add-example-v2") as f:
    result = add_task(x=1, y=2)

print(f.tasks) # {<Task: add_task>}

add_task in f.tasks # False
result in f.tasks # True
```

We see here that a _copy_ of the `add_task` was created and added to the Flow.

!!! warning Auto-generation of Tasks
    Note that Prefect will autogenerate Tasks to represent Python collections; so, for example, adding a dictionary to a Flow will actually create Tasks for the dictionary's keys and its values.

    ```python
    from prefect import task, Flow

    @task
    def do_nothing(arg):
        pass

    with Flow("constants") as flow:
        do_nothing({"x": 1, "y": [9, 10]})

    flow.tasks

    #  <Task: Dict>,
    #  <Task: List>, # corresponding to [9, 10]
    #  <Task: List>, # corresponding to the dictionary keys
    #  <Task: List>, # corresponding to the dictionary values
    #  <Task: do_nothing>}
    ```

    This can be burdensome for deeply nested Python collections. To prevent this granular auto-generation from occurring, you can always wrap Python objects in a `Constant` Task:

    ```python
    from prefect.tasks.core.constants import Constant

    with Flow("constants") as flow:
        do_nothing(Constant({"x": 1, "y": [9, 10]}))

    flow.tasks

    # {<Task: Constant[dict]>, <Task: do_nothing>}
    ```

    The `Constant` Task tells Prefect to treat its input as a raw constant, with no further introspection.



As a final illustration of how / when Tasks are added to Flows in the functional API, let's elevate these values to `Parameter`s with default values:

```python
from prefect import Parameter

with Flow("add-example-v3") as f:
    # we will instantiate these Parameters here
    # but note that does NOT add them to the flow yet
    x = Parameter("x", default=1)
    y = Parameter("y", default=2)

    result = add_task(x=x, y=y) # <-- the moment at which x, y are added to the Flow

print(f.tasks) # {<Task: add_task>, <Parameter: y>, <Parameter: x>}

add_task in f.tasks # False
result in f.tasks # True

x in f.tasks # True
y in f.tasks # True
```

Our final observation is that the Parameters were added to the Flow as-is (no copies were made). Copies will only be created when you _call_ a Task.

!!! tip You can specify non-data dependencies with the functional API
    A common misconception is that the functional API does not allow users to specify non-data dependent tasks (Task B should run _after_ Task A, but no data is exchanged). In fact, this is possible using the special `upstream_tasks` keyword argument to the task's call method. Here is an example:

    ```python
    from prefect import task, Flow

    @task(name="A")
    def task_A():
        # does something interesting and stateful
        return None


    @task(name="B")
    def task_B():
        # also does something interesting and stateful
        return None

    with Flow("functional-example") as flow:
        result = task_B(upstream_tasks=[task_A])
```



## Mapping

[Mapping](https://docs.prefect.io/core/concepts/mapping.html) is a unique feature of Prefect, which allows users to _dynamically_ spawn multiple copies of a given Task in response to an upstream Task's output. When a task is mapped, Prefect automatically creates a copy of the task for each element of its input data. The copy -- referred to as a "child" task -- is applied only to that element. This means that mapped tasks actually represent the computations of many individual children tasks.

If a "normal" (non-mapped) task depends on a mapped task, Prefect automatically applies a reduce operation to gather the mapped results and pass them to the downstream task.

However, if a mapped task relies on another mapped task, Prefect does not reduce the upstream result. Instead, it connects the nth upstream child to the nth downstream child, creating independent parallel pipelines.

Let's have a look at a simple example:

```python
import prefect
from prefect import task, Flow

@task
def add_one(x):
    """Operates one number at a time"""
    return x + 1

@task(name="sum")
def sum_numbers(y):
    """Operates on an iterable of numbers"""
    result = sum(y)
    logger = prefect.context["logger"]
    logger.info("The sum is {}".format(result))
    return result


## Imperative API
flow = Flow("Map Reduce")
flow.set_dependencies(add_one, keyword_tasks={"x": [1, 2, 3, 4]}, mapped=True)
flow.set_dependencies(sum_numbers, keyword_tasks={"y": add_one})

## Functional API
with Flow("Map Reduce") as flow:
    mapped_result = add_one.map(x=[1, 2, 3, 4])
    summed_result = sum_numbers(mapped_result)
```

Whenever this Flow is run, we will see the following log:

```
[2019-07-20 21:35:00,968] - INFO - prefect.Task | The sum is 14
```

Note that each "child" task is a _first class Prefect Task_. This means that they can do anything a "normal" task can do, including succeed, fail, retry, pause, or skip.

#### Not Everything must be mapped over

Suppose we have a Task that accepts many keyword arguments and we want to only map over a _subset_ of those arguments. In this case, we can use Prefect's `unmapped` container for specifying those inputs which should _not_ be mapped over:

```python
from prefect import task, Flow
from prefect import unmapped

@task
def add_one(x, y):
    """Operates one number at a time"""
    return x + y

with Flow("unmapped example") as flow:
    result = add_one.map(x=[1, 2, 3], y=unmapped(5))
```

When this Flow runs, only the `x` keyword will be mapped over; the `y` will remain fixed with the constant value of 5.

#### Mapped Tasks don't have to exchange data

Prefect's API is designed for maximum flexibility - it is actually possible to spawn multiple mapped copies of a Task in response to an upstream output without exchanging data. For example:

```python
from prefect import task, Flow

@task
def return_list():
    return [1, 2, 3, 4]

@task
def print_hello():
    print("=" * 30)
    print("HELLO")
    print("=" * 30)

with Flow("print-example") as flow:
    result = print_hello.map(upstream_tasks=[return_list])
```

When this flow runs, we will see _four_ print statements, one corresponding to each value of the `return_list` output. This pattern (combined with the `unmapped` container) is sometimes useful when you have multiple mapping layers and complicated dependency structures. Additionally, it is worth noting that if `return_list` returned an empty list, no child tasks would be created and the `print_hello` task would succeed gracefully.

!!! warning Order Matters
    Note that order matters in Prefect mapping. Internally, Prefect tracks your mapped child tasks via a "map index" which describes its position in the mapping. For this reason we don't recommend mapping over dictionaries, sets, or anything else without a natural of ordering.


## Best Practices in Writing Tasks

We can distill most of the above information into a few pieces of advice for designing your own Prefect Tasks.

#### Be careful with Task attributes

In exactly the same way that [Task Inputs and Outputs](#task-inputs-and-outputs) eventually need to be serialized, _so will Task attributes_. In fact, if you deploy your Flow to Prefect Cloud, your Task attributes will need to pass through `cloudpickle` _regardless_ of whether you submit your Flow to a Dask Cluster.

For example, the following Task design would be bad and could not be deployed to Cloud nor could it run using a Dask-based executor:

```python
import google.bigquery

class BigQuery(Task):
    def __init__(self, *args, **kwargs):
        self.client = bigquery.Client() # <-- not serializable
        super().__init__(*args, **kwargs)

    def run(self, query: str):
        self.client.query(query)
```

In this case, instantiating the Client outside of the `run` method will prevent this Task from being serializable by `cloudpickle` (instead you should instantiate the client _within_ the `run` method).

#### Avoid Statefulness

In addition to avoiding attributes which cannot be serialized, you should also avoid on relying on statefulness in your Tasks. For example, in designing a Task class, relying on an attribute which stores state would not behave as expected:

```python
class Bad(Task):
    def __init__(self, *args, **kwargs):
        self.run_count = 0
        super().__init__(*args, **kwargs)

    def run(self):
        self.run_count += 1
        return self.run_count
```

Similarly, relying on some global state will ultimately result in headache:

```python
global_state = {"info": []}

@task
def task_one():
    global_state["info"].append(1)

@task
def task_two():
    global_state["info"].append(2)
```

#### Use a Task class for "templating" Tasks

Using the [subclass approach](subclassing-the-task-class) to designing Tasks can be beneficial whenever you want to provide a configurable task "template", whose default values can be both set at initialization time and optionally overwritten at runtime. For example, let's alter the `add_task` we created above to provide a default value for `y`:

```python
class AddTask(Task):
    def __init__(self, *args, y=None, **kwargs):
        self.y = y
        super().__init__(*args, **kwargs)

    def run(self, x, y=None):
        if y is None:
            y = self.y

        return x + y


add_task = AddTask(y=0)

with Flow("add-with-default") as f:
    result_one = add_task(x=1)
    result_two = add_task(x=0, y=10)
```

We've found this pattern of setting defaults which are optionally overwritten at runtime to be so common, we created a [utility function to minimize boilerplate](https://docs.prefect.io/api/latest/utilities/tasks.html#prefect-utilities-tasks-defaults-from-attrs). In addition, subclassing allows you to write custom class methods that are organized in one place.

!!! warning Always call the parent Task initialization method
    Anytime you subclass `Task`, _make sure to call the parent initialization method_! This ensures Prefect will recognize your custom Task as an actual Task. In addition, we highly recommend always allowing for arbitrary keyword arguments (i.e., `**kwargs`) which are passed to the Task `__init__` method. This ensures that you can still set things such as Task tags, custom names, results, etc.


## State Handlers

State handlers are a useful way of creating custom "hooks" for your Tasks, and responding to each and every state change the Task undergoes. Common use cases of state handlers include:

- sending notifications on failure / success
- intercepting results and manipulating them
- calling out to an external system to make sure your Task is ready to run (if you have an implicit non-Prefect dependency)

A state handler is a function with a particular call signature that is attached to your Task. For example:

```python
from prefect import task
import requests


def send_notification(obj, old_state, new_state):
    """Sends a POST request with the error message if task fails"""
    if new_state.is_failed():
        requests.post("http://example.com", json={"error_msg": str(new_state.result)})
    return new_state


@task(state_handlers=[send_notification])
def do_nothing():
    pass
```

Whenever this Task runs, it will undergo many state changes. For example, from `Pending` to `Running`. If at any step in the pipeline it transitions to a state which is considered "Failed", a POST request will be sent containing the error message from the failed state. (Note that the `on_failure` keyword argument to Tasks is a convenient interface to a state handler which is only called on failed states). Additionally, you can attach as many state handlers to a task as you wish and they will be called in the order that you provide them in.

!!! warning State Handler failure results in Task failure
    Because state handlers are considered a part of your custom Task logic in Prefect, if your state handler raises an error for any reason your Task will be placed in a Failed state. For this reason we highly recommend being thoughtful with how you implement your state handlers / callbacks.

