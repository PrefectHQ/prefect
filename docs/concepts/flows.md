---
description: Prefect flows are the foundational containers for workflow logic.
tags:
    - flows
    - subflows
    - workflows
    - scripts
    - parameters
    - states
search:
  boost: 2
---

# Prefect flows

This page explains Prefect flows and how to build and manage them.

## Overview

Flows are the core building blocks for defining and managing workflows as code within Prefect. They serve as containers for your workflow logic and provide features for configuration and tracking.

Flows are Python functions decorated with the `@flow` decorator.

### Flow components

Flow components can include:

* **Flow functions:** Python functions that define the core logic of your workflows.
* [**Parameters**](#parameters): Inputs you pass to the flow function during execution.
* **Tasks:** Smaller units of work within a flow. For more information, see [tasks](/concepts/tasks/).
* [**Subflows**](#create-modular-workflows-using-subflows): Flows that you call from within another flow. Can contain multiple tasks.
* [**Flow run**](#flow-runs): A single execution of a flow.

### Flow benefits

Using Prefect flows offer several advantages:

* **Code as workflows:** Define your workflows as Python code, allowing for clear, reusable, and maintainable logic.
* **Automatic tracking:** The Prefect API tracks and reports every flow that you execute, providing observability into your workflows.
* **Automatic type checking:** Type check input arguments using Pydantic, ensuring data integrity.
* **Error handling:** Configure flows with retries and timeouts to handle potential failures.
* **Modular workflows:** Break down complex workflows into smaller, reusable flows and tasks.

## Build flows

To build flows:

* Designate a flow using the [`@flow`][prefect.flows.flow] decorator:

    ```python hl_lines="3"
    from prefect import flow
    
    @flow
    def my_flow():
        return
    ```
    
    There are no rigid rules for what code you include within a flow definition - all valid Python is acceptable.

* Uniquely identify your flow by providing a `name` parameter value for the flow.

    ```python hl_lines="1"
    @flow(name="My Flow")
    def my_flow():
        return
    ```
    If you don't provide a name, Prefect uses the flow function name.

* Track more granular units of work within a flow by calling tasks:

    ```python
    from prefect import flow, task
    
    @task
    def print_hello(name):
        print(f"Hello {name}!")
    
    @flow(name="Hello Flow")
    def hello_world(name="world"):
        print_hello(name)
    ```
    For more information, see [tasks](/concepts/tasks/).

## Configure flow settings

Set up your flow's behavior using keyword arguments to the `@flow` decorator:

| Argument                                           | Description                                                                                                                                                                                                          |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description`                                      | Optional string description for the flow. Defaults to the docstring of the decorated function.|
| `name`                                             | Optional name for the flow. Defaults to the function name.|
| `retries`                                          | Optional number of times to retry on flow run failure.|
| <span class="no-wrap">`retry_delay_seconds`</span> | Optional delay (in seconds) between retries after a flow run failure. Applicable only if `retries` is set.|
| `flow_run_name`                                    | Optional template string to define the name for flow runs. Can reference flow parameters or use a function. For example, you can use the `{name}-on-{date:%A}` value for dynamic flow run naming|
| `task_runner`                                      | Optional task runner to use for task execution within the flow. Defaults to `ConcurrentTaskRunner`.|
| `timeout_seconds`                                  | Optional maximum runtime (in seconds) for the flow. If exceeded, the flow is marked as failed.|
| `validate_parameters`                              | Boolean indicating whether to validate flow parameters using Pydantic (`default: True`). Where possible, Prefect forces values into the correct type. For example, if you define a parameter as `x: int` and "5" is passed, it resolves to `5`.|
| `version`                                          | Optional version string for the flow. Defaults to a hash of the file containing the wrapped function. If the file cannot be found, the `version` value is `null`. |

### Examples
The following examples show how to customize certain flow behaviors.

To specify a custom name and task runner:

```python
from prefect import flow
from prefect.task_runners import SequentialTaskRunner

@flow(name="My Flow",
      description="My flow using SequentialTaskRunner",
      task_runner=SequentialTaskRunner())
def my_flow():
    return
```

To provide the description as the docstring on the flow function:

```python
@flow(name="My Flow",
      task_runner=SequentialTaskRunner())
def my_flow():
    """My flow using SequentialTaskRunner"""
    return
```

Distinguish runs of this flow by providing a `flow_run_name` and using Python's standard string formatting syntax:

```python
import datetime
from prefect import flow

@flow(flow_run_name="{name}-on-{date:%A}")
def my_flow(name: str, date: datetime.datetime):
    pass

# creates a flow run called 'marvin-on-Thursday'
my_flow(name="marvin", date=datetime.datetime.now(datetime.timezone.utc))
```

Accept a function that returns a string for the `flow_run_name`:

```python
import datetime
from prefect import flow

def generate_flow_run_name():
    date = datetime.datetime.now(datetime.timezone.utc)

    return f"{date:%A}-is-a-nice-day"

@flow(flow_run_name=generate_flow_run_name)
def my_flow(name: str):
    pass

# creates a flow run called 'Thursday-is-a-nice-day'
if __name__ == "__main__":
    my_flow(name="marvin")
```

Access information about the flow using the `prefect.runtime` module:

```python
from prefect import flow
from prefect.runtime import flow_run

def generate_flow_run_name():
    flow_name = flow_run.flow_name

    parameters = flow_run.parameters
    name = parameters["name"]
    limit = parameters["limit"]

    return f"{flow_name}-with-{name}-and-{limit}"

@flow(flow_run_name=generate_flow_run_name)
def my_flow(name: str, limit: int = 100):
    pass

# creates a flow run called 'my-flow-with-marvin-and-100'
if __name__ == "__main__":
    my_flow(name="marvin")
```

## Flow runs
A flow run represents a single execution of a flow. 

![Prefect UI](/img/ui/timeline-flows.png)

### Triggering flow runs

You can trigger a flow run in several ways:

* **Manually:** Calling the flow function directly in a script or interactive session.
* **Scheduler:** Using external schedulers like `cron` to invoke the flow function periodically.
* **Prefect Cloud/Server:** Creating [deployments](/concepts/deployments/) on Prefect Cloud or a locally run Prefect server. You can then schedule flow runs through the UI, API, or deployments.

### Managing flow runs

Prefect provides functionalities for managing flow runs:

* **Monitoring:** The Prefect UI or API allows you to view the status, logs, and results of past and ongoing flow runs.
* **Retries:** You can set up flows to automatically retry a certain number of times on failure.
* **Cancelling:** You can manually cancel a running flow run if necessary.
* **Retention:** Prefect Cloud offers flow run retention policies to control how long to store flow runs after completion.

By effectively managing flow runs, you can ensure the smooth execution and maintainability of your workflows.

### Flow run states

Prefect tracks the state of each flow run, allowing you to monitor its progress and identify any issues. Here are the typical flow run states:

* **Scheduled:** The flow run is waiting for execution based on a schedule.
* **Running:** The flow and its tasks are actively executing.
* **Failed:** The flow run encountered an error and did not complete successfully.
* **Cancelled:** The flow run was manually stopped before completion.
* **Succeeded:** The flow run finished execution without errors.

## Create modular workflows using subflows

Subflows allow you to create modular units of work within your Prefect workflows. These subflows can contain multiple tasks, offering several advantages over using individual [tasks](/concepts/tasks/):

* **Enhanced observability**: Subflows have first-class observability within Prefect, providing clear visibility into their status within the UI and Prefect Cloud.  You can easily monitor subflow progress in the Flow Runs dashboard, eliminating the need to delve into individual tasks within a specific flow run. See [states](/concepts/states/) for examples utilizing task state within flows.

* **Conditional execution**: Subflows enable you to group tasks that only run under specific conditions. This simplifies conditional logic by allowing you to conditionally run the entire subflow instead of managing individual tasks.

* **Parametrization**: Prefect's parameterization capabilities extend to subflows. This allows you to reuse the same group of tasks for different purposes by simply passing different parameters when invoking the subflow.

* **Task runner flexibility**: Subflows provide control over the task runner used within them.  For example, you can group tasks optimized for parallel execution with Dask into a subflow that utilizes the Dask task runner.  Different subflows can leverage different task runners for optimal performance.

### Subflow execution

Initiate a subflow run when you call a flow function inside another flow. The calling flow acts as the "parent" flow, while the created flow becomes the "child" or "subflow." The Prefect backend maintains a full visual representation of the subflow run, as if it were called directly.

Upon starting, a subflow creates a dedicated [task runner](/concepts/task-runners/) to manage its internal tasks. This runner is shut down once the subflow completes execution.

By default, subflow execution blocks the parent flow until it finishes. However, for asynchronous execution, you can leverage either [AnyIO task groups](https://anyio.readthedocs.io/en/stable/tasks.html) or [asyncio.gather](https://docs.python.org/3/library/asyncio-task.html#id6).

### Data exchange between flows

Subflows differ from regular flows in their handling of passed task futures. Subflows resolve any passed task futures into data, enabling seamless data exchange between the parent and child flows.

You can track the relationship between parent and child flows through a special task run created within the parent. This task run mirrors the state of the corresponding child flow run.

A task representing a subflow has a `child_flow_run_id` field within its `state_details`, indicating its subflow nature. You can also identify a subflow by the presence of a `parent_task_run_id` in its `state_details`.

### Define and run subflows

You can define multiple flows within a single file. However, regardless of execution location (local or via a [deployment](/concepts/deployments/), you must specify the entrypoint flow for a flow run.

### Cancel subflows

You can't cancel inline subflow runs, specifically those without `run_deployment`, independently.

To achieve independent cancellation, deploy the subflow separately and initiate it using the [`run_deployment` function](/api-ref/prefect/deployments/deployments/#prefect.deployments.deployments.run_deployment).

### Examples

See the following example subflow:

```python
from prefect import flow, task

@task(name="Print Hello")
def print_hello(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@flow(name="Subflow")
def my_subflow(msg):
    print(f"Subflow says: {msg}")

@flow(name="Hello Flow")
def hello_world(name="world"):
    message = print_hello(name)
    my_subflow(message)

if __name__ == "__main__":
    hello_world("Marvin")
```

You can also define flows or tasks in separate modules and import them for usage. For example, here's a simple subflow module:

```python
from prefect import flow, task

@flow(name="Subflow")
def my_subflow(msg):
    print(f"Subflow says: {msg}")
```

Here's a parent flow that imports and uses `my_subflow()` as a subflow:

```python
from prefect import flow, task
from subflow import my_subflow

@task(name="Print Hello")
def print_hello(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@flow(name="Hello Flow")
def hello_world(name="world"):
    message = print_hello(name)
    my_subflow(message)

hello_world("Marvin")
```

Running the `hello_world()` flow (in this example from the file `hello.py`) creates a flow run like this:

<div class="terminal">
```bash
$ python hello.py
15:19:21.651 | INFO    | prefect.engine - Created flow run 'daft-cougar' for flow 'Hello Flow'
15:19:21.651 | INFO    | Flow run 'daft-cougar' - Using task runner 'ConcurrentTaskRunner'
15:19:21.945 | INFO    | Flow run 'daft-cougar' - Created task run 'Print Hello-84f0fe0e-0' for task 'Print Hello'
Hello Marvin!
15:19:22.055 | INFO    | Task run 'Print Hello-84f0fe0e-0' - Finished in state Completed()
15:19:22.107 | INFO    | Flow run 'daft-cougar' - Created subflow run 'ninja-duck' for flow 'Subflow'
Subflow says: Hello Marvin!
15:19:22.794 | INFO    | Flow run 'ninja-duck' - Finished in state Completed()
15:19:23.215 | INFO    | Flow run 'daft-cougar' - Finished in state Completed('All states completed.')
```
</div>

## Parameters

Prefect flows accept arguments in two forms: positional and keyword arguments. These arguments are dynamically converted into a dictionary named `parameters` at runtime that maps parameter names to their corresponding values.

The Prefect orchestration engine stores these parameters within the associated flow run object, making them accessible throughout the flow's execution.

Flow run parameters cannot exceed `512kb` in size

### API-specific parameter requirements

When creating flow runs through the Prefect API, specifying parameter names is mandatory when overriding default values. Unlike positional arguments, Prefect doesn't support unnamed arguments.

### Validate parameters

Prefect validates parameters before running a flow. This ensures parameter integrity and helps prevent errors:

* If a flow call receives invalid parameters, the created flow run enters a `Failed` state.
* For deployed flows, encountering invalid parameters during a flow run causes the state to transition from `Pending` to `Failed` without ever entering the `Running` state.

[Pydantic models](https://pydantic-docs.helpmanual.io/) offer a convenient way to enforce type annotations on your flow parameters. Prefect automatically coerces any Pydantic model used as a type hint within a flow into the appropriate object type.

Here's an example demonstrating this functionality:

```python
from prefect import flow
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@flow
def model_validator(model: Model):
    print(model)
```

### Handle parameters

Prefect flows accept parameters during API-initiated flow runs. Prefect automatically serializes these parameters for transmission and can leverage type hints within your flow functions for automatic conversion from JSON to their appropriate Python types. This simplifies parameter handling and ensures type safety.

For example, to automatically convert something to a datetime:

```python
from prefect import flow
from datetime import datetime

@flow
def what_day_is_it(date: datetime = None):
    if date is None:
        date = datetime.now(timezone.utc)
    print(f"It was {date.strftime('%A')} on {date.isoformat()}")

if __name__ == "__main__":
    what_day_is_it("2021-01-01T02:00:19.180906")
```

When you run this flow, you'll see the following output:

<div class="terminal">
```bash
It was Friday on 2021-01-01T02:00:19.180906
```
</div>

## Monitor flows

To monitor flows, see [states](/concepts/states).

## Visualize flows

Calling `.visualize()` on your flow attempts to generate a visual representation (often a schematic diagram) of your flow and its tasks, without actually executing the flow code. This provides a quick and clear understanding of your flow structure and how tasks interact with each other.

### Important considerations

* Visualization without execution: Remember that `.visualize()` doesn't execute your flow's code. It solely focuses on structure visualization.
* Isolating code for visualization: Be cautious! Functions or code outside of flows or tasks are run when using `.visualize()`. This might cause unintended consequences. To prevent this, ensure your code resides within tasks.

### Prerequisites

[Install Graphviz](http://www.graphviz.org/download/) and make it accessible on your system path. Installing the `graphviz` python package using pip is not sufficient.

### Simple flow visualization

This following code visualizes the below diagram:

```python
from prefect import flow, task

@task(name="Print Hello")
def print_hello(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@task(name="Print Hello Again")
def print_hello_again(name):
    msg = f"Hello {name}!"
    print(msg)
    return msg

@flow(name="Hello Flow")
def hello_world(name="world"):
    message = print_hello(name)
    message2 = print_hello_again(message)

if __name__ == "__main__":
    hello_world.visualize()
```
Visualized diagram:
![A simple flow visualized with the .visualize() method](/img/orchestration/hello-flow-viz.png)

### Dynamic flow visualization

Prefect cannot automatically generate schematics for dynamic workflows involving loops or conditional statements. However, you can provide mock return values for tasks within the `.visualize()` call to address this.

```python
from prefect import flow, task
@task(viz_return_value=[4])
def get_list():
    return [1, 2, 3]

@task
def append_one(n):
    return n.append(6)

@flow
def viz_return_value_tracked():
    l = get_list()
    for num in range(3):
        l.append(5)
        append_one(l)

if __name__ == "__main__":
    viz_return_value_tracked.visualize()
```

Visualized diagram:
![A flow with return values visualized with the .visualize() method](/img/orchestration/viz-return-value-tracked.png)


## Deploy flows for continuous execution

Serving a flow deploys your flow as a long-running process that actively monitors for work. When work is available, the flow executes in a separate subprocess, promoting stability and isolation.

The following sample shows how to serve a flow and set up deployment without complex infrastructure setup by using the [`serve` method](/api-ref/prefect/flows/#prefect.flows.Flow.serve):

```python title="hello_world.py"
from prefect import flow


@flow(log_prints=True)
def hello_world(name: str = "world", goodbye: bool = False):
    print(f"Hello {name} from Prefect! 🤗")

    if goodbye:
        print(f"Goodbye {name}!")


if __name__ == "__main__":
    # creates a deployment and stays running to monitor for work instructions generated on the server

    hello_world.serve(name="my-first-deployment",
                      tags=["onboarding"],
                      parameters={"goodbye": True},
                      interval=60)
```

### Deployment configuration

The `serve` method provides options for customizing deployments:

* Schedules: Define times or intervals for automatic flow execution.
* Event Triggers: Initiate flow runs based on external events.
* Metadata: Add descriptive tags and a clear flow description.
* Default Parameters: Set default values for flow parameters.

### Prevent deployment shutdowns

By default, stopping the serving process pauses the deployment's schedule (if it exists). To prevent this in environments with frequent restarts, use the `pause_on_shutdown=False` flag:

```python hl_lines="5"
if __name__ == "__main__":
    hello_world.serve(name="my-first-deployment",
                        tags=["onboarding"],
                        parameters={"goodbye": True},
                        pause_on_shutdown=False,
                        interval=60)
```

### Deploy multiple flows

Serve multiple flows at the same time using the `serve` utility and the flow's `to_deployment` method to efficiently manage various workflows within a single process:

```python
import time
from prefect import flow, serve


@flow
def slow_flow(sleep: int = 60):
    "Sleepy flow - sleeps the provided amount of time (in seconds)."
    time.sleep(sleep)


@flow
def fast_flow():
    "Fastest flow this side of the Mississippi."
    return


if __name__ == "__main__":
    slow_deploy = slow_flow.to_deployment(name="sleeper", interval=45)
    fast_deploy = fast_flow.to_deployment(name="fast")
    serve(slow_deploy, fast_deploy)
```

The behavior and configuration for serving multiple flows are identical to the single flow case.

### Retrieve flows from remote storage

You can retrieve flows from remote storage using the [`flow.from_source`](/api-ref/prefect/flows/#prefect.flows.Flow.from_source) method.

This method accepts a git repository URL and an entrypoint specifying the flow to load:

```python title="load_from_url.py"
from prefect import flow

my_flow = flow.from_source(
    source="https://github.com/PrefectHQ/prefect.git",
    entrypoint="flows/hello_world.py:hello"
)

if __name__ == "__main__":
    my_flow()
```

<div class="terminal">

```bash
16:40:33.818 | INFO    | prefect.engine - Created flow run 'muscular-perch' for flow 'hello'
16:40:34.048 | INFO    | Flow run 'muscular-perch' - Hello world!
16:40:34.706 | INFO    | Flow run 'muscular-perch' - Finished in state Completed()
```

</div>
The flow entrypoint is the path to the flow file followed by a colon (`:`) and the flow function name.

For private repositories, provide a [`GitRepository`](/api-ref/prefect/flows/#prefect.runner.storage.GitRepository) object instead of a URL directly:

```python title="load_from_storage.py"
from prefect import flow
from prefect.runner.storage import GitRepository
from prefect.blocks.system import Secret

my_flow = flow.from_source(
    source=GitRepository(
        url="https://github.com/org/private-repo.git",
        branch="dev",
        credentials={
            "access_token": Secret.load("github-access-token").get()
        }
    ),
    entrypoint="flows.py:my_flow"
)

if __name__ == "__main__":
    my_flow()
```

### Deploy flows from remote storage

You can serve flows that you load from remote storage using the same [`serve`](#serving-a-flow) method as local flows:

```python title="serve_loaded_flow.py"
from prefect import flow

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/org/repo.git",
        entrypoint="flows.py:my_flow"
    ).serve(name="my-deployment")
```

This enables updating your flow code without restarting the serving process, as the process periodically checks for updates in your remote storage.

## Stop flow runs

You can pause, suspend, or cancel flow runs.

### Pause flow runs

Pause an ongoing flow run until manual approval using the [`pause_flow_run`](/api-ref/prefect/engine/#prefect.engine.pause_flow_run) and [`resume_flow_run`](/api-ref/prefect/engine/#prefect.engine.resume_flow_run) functions.

Paused flow runs automatically timeout after one hour by default. If the timeout occurs, the flow run fails with a message indicating it was paused but never resumed. You can specify a different timeout period in seconds using the `timeout` parameter.

Call `pause_flow_run` inside a flow:

```python
from prefect import task, flow, pause_flow_run, resume_flow_run

@task
async def marvin_setup():
    return "a raft of ducks walk into a bar..."


@task
async def marvin_punchline():
    return "it's a wonder none of them ducked!"


@flow
async def inspiring_joke():
    await marvin_setup()
    await pause_flow_run(timeout=600)  # pauses for 10 minutes
    await marvin_punchline()
```

Calling this flow pauses code execution after the first task, waiting for resumption before delivering the workflow.

```python
from prefect import task, flow, pause_flow_run

@task
def task_one():
    for i in range(3):
        sleep(1)
        print(i)

@flow(log_prints=True)
def my_flow():
    terminal_state = task_one.submit(return_state=True)
    if terminal_state.type == StateType.COMPLETED:
        print("Task one succeeded! Pausing flow run..")
        pause_flow_run(timeout=2) 
    else:
        print("Task one failed. Skipping pause flow run..")
```

You can resume paused flow runs by clicking **Resume** in the Prefect UI or by calling the resume_flow_run function programmatically:

```python
resume_flow_run(FLOW_RUN_ID)
```

### Suspend flow runs

Suspend flow runs to save costs instead of paying for long-running infrastructure using the [`suspend_flow_run`](/api-ref/prefect/engine/#prefect.engine.suspend_flow_run) and [`resume_flow_run`](/api-ref/prefect/engine/#prefect.engine.resume_flow_run) functions, as well as the Prefect UI.

When the flow run resumes, the flow code executes again from the beginning of the flow, so you should use [tasks](/concepts/tasks/) and [task caching](/concepts/tasks/#caching) to avoid recomputing expensive operations.

By default, suspended flow runs time out after one hour. For more information, see [Prevent long-running flows](#prevent-long-running-flows).

Here is an example of a flow that does not block flow execution while paused:

```python
from prefect import flow, pause_flow_run, task

@task(persist_result=True)
def foo():
    return 42

@flow(persist_result=True)
def noblock_pausing():
    x = foo.submit()
    pause_flow_run(timeout=30, reschedule=True)
    y = foo.submit()
    z = foo(wait_for=[x])
    alpha = foo(wait_for=[y])
    omega = foo(wait_for=[x, y])
```
This flow exits after one task, and reschedules upon resuming. Instead of rerunning the task, the function retrieves the stored result of the first task.

You can suspect flow runs out-of-process by calling `suspend_flow_run(flow_run_id=<ID>)` or selecting the **Suspend** button in the Prefect UI or Prefect Cloud.

Resume suspended flow runs by clicking the **Resume** button in the Prefect UI or calling the `resume_flow_run` utility via client code.

```python
resume_flow_run(FLOW_RUN_ID)
```

### Suspend subflows

Subflow runs cannot be suspended independently from their parent flow run.

This behavior applies when using `run_deployment` within a flow to schedule another flow run. By default, the scheduled run becomes a linked subflow of the calling flow. This linkage prevents independent suspension of the scheduled subflow.

To enable independent suspension of the scheduled flow run, call `run_deployment` with the `as_subflow=False` argument. This disables the linking behavior.

### Wait for input when pausing or suspending flow runs (experimental)

The `wait_for_input` argument for `pause_flow_run` and `suspend_flow_run` is experimental and might change without warning in future releases.

You can pause or suspend a flow run until further input from a user using the `wait_for_input` argument, a subclass of `prefect.input.RunInput` (Pydantic model).

Upon successful validation, the flow run resumes, and the return value of the `pause_flow_run` or `suspend_flow_run` is an instance of the model containing the provided data.

Here is an example of a flow that pauses and waits for input from a user:

```python
from prefect import flow, pause_flow_run
from prefect.input import RunInput


class UserNameInput(RunInput):
    name: str


@flow(log_prints=True)
async def greet_user():
    user_input = await pause_flow_run(
        wait_for_input=UserNameInput
    )

    print(f"Hello, {user_input.name}!")
```

Running this flow creates a flow run. The flow run advances until code execution reaches `pause_flow_run`, at which point it moves into a `Paused` state.
Execution blocks and waits for resumption.

When resuming the flow run, users must provide a value for the `name` field of the `UserNameInput` model.
Upon successful validation, the flow run resumes, and the return value of the `pause_flow_run` is an instance of the `UserNameInput` model containing the provided data.

For more information on receiving input from users when pausing and suspending flow runs, see [Creating interactive workflows](/guides/creating-interactive-workflows/).

### Cancel flow runs

Cancel a scheduled or in-progress flow run from the CLI, UI, REST API, or Python client to transition flow runs to a `Cancelling` state.

How it works:

* Workers monitor flow run states and trigger cancellation requests.
* Flow run infrastructure forcefully terminated if not stopped within the grace period (default 30 seconds).
* Requires a [deployment with the flow run](#deploy-flows-for-continuous-execution).
* Needs a monitoring process for enforcing cancellation.

### Worker restarts

Cancellations use the `infrastructure_pid` flow run metadata:

* Scope: Identifies where infrastructure is running (prevents killing wrong infrastructure).
* ID: Unique identifier for the infrastructure within the scope.


Example identifiers for infrastructure types:

- Processes: The machine hostname and the PID.
- Docker Containers: The Docker API URL and container ID.
- Kubernetes Jobs: The Kubernetes cluster name and the job name.

### Possible cancellation issues

* Altered/removed infrastructure block might prevent cancellation.
* Infrastructure block might not support cancellation.
* Mismatched identifier scope during cancellation attempt.
* Missing `infrastructure_pid`: Flow run marked cancelled, but enforcement fails.
* Unexpected worker error: Flow run cancellation might succeed or fail (worker retries).

### Improved cancellation (experimental)

Improve cancellation reliability by enabling the `PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION` setting on your worker or agents:

<div class="terminal">
```bash
prefect config set PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION=True
```
</div>

If you encounter any issues, let us know in [Slack](https://www.prefect.io/slack/) or with a [Github](https://github.com/PrefectHQ/prefect) issue.

### Cancel via the CLI

From the command line in your execution environment, you can cancel a flow run by using the `prefect flow-run cancel` CLI command, passing the ID of the flow run.

<div class="terminal">
```bash
prefect flow-run cancel 'a55a4804-9e3c-4042-8b59-b3b6b7618736'
```
</div>

### Cancel via the UI

From the UI you can cancel a flow run by navigating to the flow run's detail page and clicking `Cancel` in the upper right corner.

![Prefect UI](/img/ui/flow-run-cancellation-ui.png)

## Prevent long-running flows 

Flow timeouts prevent unintentionally long-running flows.

How it works:

* If a flow's execution time surpasses the set timeout, the system throws a timeout exception and updates the flow's state to 'Failed'.
* The UI visually identifies these flows with a "TimedOut" label.

Use `timeout_seconds` to specify timeout durations:

```python hl_lines="4"
from prefect import flow
import time

@flow(timeout_seconds=1, log_prints=True)
def show_timeouts():
    print("I will execute")
    time.sleep(5)
    print("I will not execute")
```

You can specify a different timeout period in seconds using the `timeout` parameter or pass `timeout=None` for no timeout.