# Prefect 0.15.0: Improve flow run creation and inspection

We’re excited to announce the release of Prefect 0.15.0! This release is the result of months of work to improve the interface for creating and inspecting flow runs. 0.15.0 contains a new command line interface for creating flow runs as well a suite of objects for inspecting flow runs without writing GraphQL queries.

For the full list of enhancements and features, check out the [release changelog](...).


. . .


The core of Prefect is orchestrating the execution of your workflows. When using Prefect Cloud or Server, you indicates a workflow should be run by creating a "flow run". A flow run can be created from the UI, via a GraphQL call, from a task in another flow run, or using the CLI. Continuous improvements have been made to launching flow runs from the the web UI; log levels can be easily adjusted, configuration can be modified per run, and JSON flow parameters have syntax highlighting. Whilst the `prefect run flow` CLI has seen a myriad of improvements, it hasn't been given a fresh look in a year. With the introduction of the new `prefect register` and `prefect build` commands in 0.14.13, it made sense to revisit the flow run command to create a coherent design.

## A new CLI

We created a new CLI for running flows: `prefect run`. The old command, `prefect run flow` will stick around for compatbility. Creating a new command let us change behavior and arguments without worrying about backwards compatibility. This naming matches the `prefect register` command (which replaced `prefect register flow`).

A minor pain point is that, when developing, you need to define your flow then call `flow.run()` at the bottom. To test the flow, you run `python my_flow_file.py`. Then, when the flow is ready to be pushed to Cloud, you change your `flow.run()` call to `flow.register("project")` and go to the UI to start a flow run. We want the transition from developing a flow locally to running flows in production to be seamless, so we've aimed at alleviating this friction. We want you to be able to limit the flow file to contain just the code for your workflow.

`prefect run` will take an import or file path to run a flow locally; this replaces the `flow.run()` and `python my_flow_file.py` pattern. For example, the following will run the file, extract the flow object, and call `flow.run()` for you:

```
$ prefect run -p my_flow_file.py
```

To transition this flow from local to Cloud, we can register it with an interface that feels the same:

```
$ prefect register -p my_flow_file.py --project example
```

Before we continue, let's switch to a real flow. We've added a "Hello World" flow to Prefect to make getting started really easy. 

First, try running the flow locally:
```
$ prefect run -m prefect.hello_world
```
```
Retrieving local flow... Done
Running flow locally...
└── 11:21:52 | INFO    | Beginning Flow run for 'hello-world'
└── 11:21:52 | INFO    | Task 'name': Starting task run...
└── 11:21:52 | INFO    | Task 'name': Finished task run for task with final state: 'Success'
└── 11:21:52 | INFO    | Task 'capitalize': Starting task run...
└── 11:21:52 | INFO    | Task 'capitalize': Finished task run for task with final state: 'Success'
└── 11:21:52 | INFO    | Task 'say_hello': Starting task run...
└── 11:21:52 | INFO    | Hello World
└── 11:21:52 | INFO    | Task 'say_hello': Finished task run for task with final state: 'Success'
└── 11:21:52 | INFO    | Flow run SUCCESS: all reference tasks succeeded
Flow run succeeded!
```

Then, register the flow:
```
# You may need to create a project first with `prefect create project 'example'`
$ prefect register -m prefect.hello_world --project example
```
```
Collecting flows...
Processing 'prefect.hello_world':
  Building `Module` storage...
  Registering 'hello-world'... Done
  └── ID: 8a896c14-07ac-4538-bed1-162e188d780f
  └── Version: 1
======================== 1 registered ========================
```

Now, a flow run can be created using the `prefect run` CLI:
```
$ prefect run --name "hello-world" --watch
```
```
Looking up flow metadata... Done
Creating run for flow 'hello-world'... Done
└── Name: electric-mandrill
└── UUID: 55955649-f2e7-4d43-938a-f5b08974bab9
└── Labels: []
└── Parameters: {}
└── Context: {}
└── URL: https://cloud.prefect.io/prefect-engineering/flow-run/55955649-f2e7-4d43-938a-f5b08974bab9
Watching flow run execution...
└── 11:22:38 | INFO    | Entered state <Scheduled>: Flow run scheduled.
└── 11:22:45 | INFO    | Entered state <Submitted>: Submitted for execution
└── 11:22:45 | INFO    | Submitted for execution: Job prefect-job-9d1c807c
└── 11:22:47 | INFO    | Beginning Flow run for 'hello-world'
└── 11:22:47 | INFO    | Entered state <Running>: Running flow.
└── 11:22:47 | INFO    | Task 'name': Starting task run...
└── 11:22:47 | INFO    | Task 'name': Finished task run for task with final state: 'Success'
└── 11:22:48 | INFO    | Task 'capitalize': Starting task run...
└── 11:22:48 | INFO    | Task 'capitalize': Finished task run for task with final state: 'Success'
└── 11:22:48 | INFO    | Task 'say_hello': Starting task run...
└── 11:22:48 | INFO    | Hello World
└── 11:22:48 | INFO    | Task 'say_hello': Finished task run for task with final state: 'Success'
└── 11:22:48 | INFO    | Flow run SUCCESS: all reference tasks succeeded
└── 11:22:48 | INFO    | Entered state <Success>: All reference tasks succeeded.
Flow run succeeded!
```

When used with a backend, `prefect run` will typically exit immediately after creating a flow run since the execution of the flow run is managed by an agent. Above, we opted to `--watch` the flow run which will stream logs and state changes from the flow run to you's machine.

### Agent warnings

A common user question is: Why is my flow run stuck in a 'Scheduled' state? Why hasn't my flow run started?

When the `--watch` flag is used, we can help answer this question. If the flow run does not enter a 'Running' state after 15 seconds, we will investigate. Flow runs are matched with agents by "labels". The labels on an agent must include all of the labels on the flow run for the agent to pick up the flow run. We pull all of the agents from Cloud and compare your labels to the flow run's labels to determine if there are any matching agents. If not, we'll tell you to start an agent with the required set of labels. If there are matching agent labels, we'll check the last time the agent contacted Cloud to see if it's healthy and warn you if it is not.

### Agentless execution

Agents add a layer to Prefect in which we help you manage the infrastructure your flow is going to be deployed on. However, when debugging or in some deployment stories, you may want to own that part of your flow's execution. Currently, the only recourse is to use local flow runs; but with local runs you lose some features that are only supported when backed by the API and you can't inspect your runs in the UI.

In 0.15.0, we've introduced a new concept of "agentless flow run execution". Here, you take full ownership of the infrastructure your flow runs on. If you want the flow to run in a container, you must set up the container yourself then call this command. This also prevents Prefect from managing the scheduling of the flow run since we cannot spin up the infrastructure on demand with an agent. However, this does allow you to do local runs of flows while still interacting with the full backend API feature set. 

Using our `hello-world` flow from above, pass the `--execute` flag to `prefect run` to execute the flow run without an agent.
```
$ prefect run --name "hello-world" --execute
```

- Creates a flow run for you in the backend with an extra unique label so an agent does not pick up the flow run
- Creates a subprocess including environment variables from your `RunConfig` (other infrastructure settings are ignored)
- The subprocess pulls the flow from storage
- The flow is executed with reporting to the backend

**Note**: Since your flow run isn't being deployed by an agent, you can put breakpoints in your tasks and debug your flow run! The context will have all of the information that it would in a real production flow run.

## Inspection of flow runs

The UI provides a wonderful view into your flow runs with minimal effort, but if you want to inspect a flow run programatically, you'll have to write some GraphQL queries yourself. GraphQL is a powerful view into the Prefect backend, allowing you to retrieve _exactly_ the data you want from nested objects. Sometimes, though, you just want a Python object.

0.15.0 creates a `prefect.backend` module with Python objects that provide views of the backend without requiring you to write any GraphQL. At the center of these objects is the `FlowRunView`, so we'll talk about that first.


The `FlowRunView` lets you pull the most recent information about a flow run from the backend. For example:

```python
from prefect.backend import FlowRunView

# Create a new instance using an ID from the UI or from the output of the `prefect run` command
flow_run = FlowRunView.from_flow_run_id("4c0101af-c6bb-4b96-8661-63a5bbfb5596")

# You now have access to information about the flow run
flow_run.state       # <Success: "All reference tasks succeeded.">
flow_run.labels      # {"foo"}
flow_run.parameters  # {"name": "Marvin"}
flow_run.run_config  # LocalRun(...)
flow_run.states      # [Scheduled(), Submitted(), Running(), Success()]

# You can also retrieve information about the flow
flow = flow_run.get_flow_metadata()  # FlowView(...)

# Or about a task run
task_run = flow_run.get_task_run(task_slug='say_hello-1')  # TaskRunView(...)
```

Notice that the `FlowRunView` provides methods to access two related structures: `FlowView` and `TaskRunView`. `FlowView` exposes the metadata that we store about a flow when it is registered. `TaskRunView` exposes metadata for a single run of a task in your flow.

A `FlowView` can also be directly instantiated with various lookup methods:

```python
from prefect.backend import FlowView

flow_view = FlowView.from_flow_name(flow_name="hello-world")

# If a name is not unique, a project will need to be provided
flow_view = FlowView.from_flow_name(flow_name="hello-world", project_name="example")

# Or a lookup can be performed by id
flow_view = FlowView.from_flow_id(flow_id="8a896c14-07ac-4538-bed1-162e188d780f")

# The view provides information about the flow
flow_view.run_config  # LocalRun(...)
flow_view.storage     # Module(...)
flow.core_version     # 0.15.0
flow.project_name     # "example"
```

A `TaskRunView` can also be instantiated directly, but it requires a flow run id so we recommend using `FlowRunView().get_task_run(...)`:

```python
from prefect import task
from prefect.backend import TaskRunView

# Presume we have a flow with the following task
@task
def foo():
  return "foobar!"

# Instantiate a task run directly
task_run = TaskRunView.from_task_slug("foo-1", flow_run_id="<id>")

# As with the other views, we can inspect the task run
task_run.state      # Success(...)
task_run.map_index  # -1  (not mapped)

# We can also retrieve results
task_run.get_result()  # "foobar!"
```

The most powerful feature of the `TaskRunView` is its ability to pull results from their location on your infrastructure. This object does the heavy lifting of looking up the location of the result and pulling the data from it. It also handles mapped tasks which require the result to be pulled from _many_ locations.

## Sub-flow result passing

The backend objects discussed above provided a stepping stone to a much requested feature: the ability to pass task results between flows. Since most of the work of retrieving results is abstracted into the view objects, it was straightforward to define some new built-in tasks that retrieve results from a task run in another flow run.

The existing task to create sub-flows, `StartFlowRun`, provides a `wait` flag. This flag changes its return value, which made it hard to rely on it providing a flow run id. A much simpler `create_flow_run` task was introduced to create a child flow run. This task always returns a flow run id immediately after creation. We then added a `get_task_run_result(flow_run_id: str, task_slug: str)` task which will retrieve the result from the task in the given flow run.

For example, we can pull a result from a child flow into a parent flow then act on that data:

```python
from typing import List

from prefect import Flow, Parameter, task
from prefect.engine.results import LocalResult
from prefect.tasks.prefect.flow_run import create_flow_run, get_task_run_result


@task(result=LocalResult())
def create_some_data(length: int):
    return list(range(length))


with Flow("child") as child_flow:
    data_size = Parameter("data_size", default=5)
    data = create_some_data(data_size)


@task(log_stdout=True)
def transform_and_show(data: List[int]) -> List[int]:
    print(f"Got: {data!r}")
    new_data = [x + 1 for x in data]
    print(f"Created: {new_data!r}")
    return new_data


with Flow("parent") as parent_flow:
    child_run_id = create_flow_run(
        flow_name=child_flow.name, parameters=dict(data_size=10)
    )
    child_data = get_task_run_result(child_run_id, "create_some_data-1")
    transform_and_show(child_data)
```

To run this example, save it to a file `parent-child-flow.py`. Then we can register and run the parent

```
$ prefect register -p parent-child-flow.py --project example
$ prefect run --name "parent" --execute
```
```
❯ prefect run --name 'parent' --execute
Looking up flow metadata... Done
Creating run for flow 'parent'... Done
└── Name: quixotic-orangutan
└── UUID: 8b17ffed-c70e-4a20-a3b4-efb2eebba9e9
└── Labels: ['agentless-run-2e92a4fd']
└── Parameters: {}
└── Context: {}
└── URL: https://cloud.prefect.io/prefect-engineering/flow-run/8b17ffed-c70e-4a20-a3b4-efb2eebba9e9
Executing flow run...
└── 13:19:07 | INFO    | Creating subprocess to execute flow run...
└── 13:19:08 | INFO    | Beginning Flow run for 'parent'
└── 13:19:09 | INFO    | Task 'create_flow_run': Starting task run...
└── 13:19:10 | INFO    | Creating flow run 'quixotic-orangutan-child' for flow 'child'...
└── 13:19:10 | INFO    | Created flow run 'quixotic-orangutan-child': https://cloud.prefect.io/prefect-engineering/flow-run/5eed1147-9247-48da-86e0-c7cee995cea9
└── 13:19:11 | INFO    | Task 'create_flow_run': Finished task run for task with final state: 'Success'
└── 13:19:11 | INFO    | Task 'get_task_run_result': Starting task run...
└── 13:19:22 | INFO    | Task 'get_task_run_result': Finished task run for task with final state: 'Success'
└── 13:19:23 | INFO    | Task 'transform_and_show': Starting task run...
└── 13:19:24 | INFO    | Got: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
└── 13:19:24 | INFO    | Created: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
└── 13:19:24 | INFO    | Task 'transform_and_show': Finished task run for task with final state: 'Success'
└── 13:19:25 | INFO    | Flow run SUCCESS: all reference tasks succeeded
Flow run succeeded!
```

## In conclusion

We've rehauled the API for running and inspecting flow runs and exposed some powerful new patterns. In the process, we rewrote most of the flow run documentation. Check out [the new documentation](https://docs.prefect.io/orchestration/flow-runs/overview.html#overview) for more details on everything covered in this post.

We're excited to see what you can do with these new features and we're always looking for more feedback so we can continue to make the best orchestration tool around!

...

Please continue reaching out to us with your questions and feedback — we appreciate the opportunity to work with all of you!

    join our Slack community for ad-hoc questions
    follow us on Twitter for updates
    attend our meetup events for contributors, focused on the internals of Prefect
    visit us on GitHub to open issues and pull requests

Happy Engineering!


— The Prefect Team



