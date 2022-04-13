# Orion Release Notes

## 2.0b3

Includes some minor improvements:

- Flow runs can be queries more flexibly and performantly.
- Improved results persistence handling.

Fixes some bugs:

- The Scheduler no longer crashes on misconfigured schedules.
- The MarkLateRuns service no longer marks runs as `Late` several seconds too early.
- Dashboard filters including flow/task run states can now be saved.
- Flow runs can no longer transition from terminal states. The engine will no longer try to set the final state of a flow run twice.
- Scheduled flow runs are now deleted when their corresponding deployment is deleted.

## 2.0b2

Includes some minor improvements:

- Docker flow runners can connect to local API applications on Linux without binding to `0.0.0.0`.
- Adds `with_options` method to flows allowing override of settings e.g. the task runner.

Fixes some bugs:

- The CLI no longer displays tracebacks on sucessful exit.
- Returning pandas objects from tasks does not error.
- Flows are listed correctly in the UI dashboard.

## 2.0b1

We are excited to introduce this branch as [Prefect 2.0](https://www.prefect.io/blog/introducing-prefect-2-0/), powered by [Orion, our second-generation orchestration engine](https://www.prefect.io/blog/announcing-prefect-orion/)! We will continue to develop Prefect 2.0 on this branch. Both the Orion engine and Prefect 2.0 as a whole will remain under active development in beta for the next several months, with a number of major features yet to come.

This is the first release that's compatible with Prefect Cloud 2.0's beta API - more exciting news to come on that soon!

### Expanded UI 
Through our technical preview phase, our focus has been on establishing the right [concepts](https://orion-docs.prefect.io/concepts/overview/) and making them accessible through the CLI and API. Now that some of those concepts have matured, we've made them more accessible and tangible through UI representations. This release adds some very important concepts to the UI:

**Flows and deployments**

If you've ever created a deployment without a schedule, you know it can be difficult to find that deployment in the UI. This release gives flows and their deployments a dedicated home on the growing left sidebar navigation. The dashboard continues to be the primary interface for exploring flow runs and their task runs.

**Work queues**

With the [2.0a13 release](https://github.com/PrefectHQ/prefect/blob/orion/RELEASE-NOTES.md#work-queues), we introduced [work queues](https://orion-docs.prefect.io/concepts/work-queues/), which could only be created through the CLI. Now, you can create and edit work queues directly from the UI, then copy, paste, and run a command that starts an agent that pulls work from that queue.

### Collections
Prefect Collections are groupings of pre-built tasks and flows used to quickly build data flows with Prefect.

Collections are grouped around the services with which they interact. For example, to download data from an S3 bucket, you could use the `s3_download` task from the [prefect-aws collection](https://github.com/PrefectHQ/prefect-aws), or if you want to send a Slack message as part of your flow you could use the `send_message` task from the [prefect-slack collection](https://github.com/PrefectHQ/prefect-slack).

By using Prefect Collections, you can reduce the amount of boilerplate code that you need to write for interacting with common services, and focus on the outcome you're seeking to achieve. Learn more about them in [the docs](https://orion-docs.prefect.io/collections/overview.md).

### Profile switching

We've added the `prefect profile use <name>` command to allow you to easily switch your active profile.

The format for the profiles file has changed to support this. Existing profiles will not work unless their keys are updated.

For example, the profile "foo" must be changed to "profiles.foo" in the file `profiles.toml`:

```toml
[foo]
SETTING = "VALUE"
```

to

```toml
[profiles.foo]
SETTING = "VALUE"
```

### Other enhancements
- It's now much easier to explore Prefect 2.0's major entities, including flows, deployments, flow runs, etc. through the CLI with the `ls` command, which produces consistent, beautifully stylized tables for each entity.
- Improved error handling for issues that the client commonly encounters, such as network errors, slow API requests, etc.
- The UI has been polished throughout to be sleeker, faster, and even more intuitive.
- We've made it even easier to access file storage through [fsspec](https://filesystem-spec.readthedocs.io/en/latest/index.html), which includes [many useful built in implementations](https://filesystem-spec.readthedocs.io/en/latest/api.html#built-in-implementations).

## 2.0a13

We've got some exciting changes to cover in our biggest release yet!

### Work queues

Work queues aggregate work to be done and agents poll a specific work queue for new work. Previously, agents would poll for any scheduled flow run. Now, scheduled flow runs are added to work queues that can filter flow runs by tags, deployment, and flow runner type.

Work queues enable some exiting new features:

- Filtering: Each work queue can target a specific subset of work. This filtering can be adjusted without restarting your agent.
- Concurrency limits: Each work queue can limit the number of flows that run at the same time.
- Pausing: Each work queue can be paused independently. This prevents agents from submitting additional work.

Check out the [work queue documentation](https://orion-docs.prefect.io/concepts/work-queues/) for more details.

Note, `prefect agent start` now requires you to pass a work queue identifier and `prefect orion start` no longer starts an agent by default.

### Remote storage

Prior to this release, the Orion server would store your flow code and results in its local file system. Now, we've introduced storage with external providers including AWS S3, Google Cloud Storage, and Azure Blob Storage.

There's an interactive command, `prefect storage create`, which walks you through the options required to configure storage. Your settings are encrypted and stored in the Orion database.

Note that you will no longer be able to use the Kubernetes or Docker flow runners without configuring storage. While automatically storing flow code in the API was convenient for early development, we're focused on enabling the [hybrid model](https://www.prefect.io/why-prefect/hybrid-model/) as a core feature of Orion.

### Running tasks on Ray

We're excited to announce a new task runner with support for [Ray](https://www.ray.io/). You can run your tasks on an existing Ray cluster, or dynamically create one with each flow run. Ray has powerful support for customizing runtime environments, parallelizing tasks to make use of your full compute power, and dynamically creating distributed task infrastructure.

An [overview of using Ray](https://orion-docs.prefect.io/concepts/task-runners/#running-tasks-on-ray) can be found in our documentation.

### Profiles

Prefect now supports profiles for configuration. You can store settings in profiles and switch between them. For example, this allows you to quickly switch between using a local and hosted API.

View all of the available commands with `prefect config --help` and check out our [settings documentation](https://orion-docs.prefect.io/concepts/settings/) for a full description of how to use profiles.

We've also rehauled our [settings reference](https://orion-docs.prefect.io/api-ref/prefect/settings/#prefect.settings.Settings) to make it easier to see all the available settings. You can override any setting with an environment variable or `prefect config set`.

## 2.0a12

### Filters
Orion captures valuable metadata about your flows, deployments, and their runs. We want it to be just as simple to retrieve this information as it is to record it. This release exposes a powerful set of filter operations to cut through this body of information with ease and precision. Want to see all of the runs of your Daily ETL flow? Now it's as easy as typing `flow:"Daily ETL"` into the filter bar. This update also includes a query builder UI, so you can utilize and learn these operators quickly and easily.

## 2.0a11

### Run Orion on Kubernetes
You can now can run the Orion API, UI, and agent on Kubernetes. We've included a new Prefect CLI command, `prefect orion kubernetes-manifest`, that you can use to automatically generate a manifest that runs Orion as a Kubernetes deployment.

### Run flows on Kubernetes
With the Kubernetes [flow runner](https://orion-docs.prefect.io/concepts/flow-runners/), you can now run flows as Kubernetes Jobs. You may specify the Kubernetes flow runner when creating a deployment. If you're running Orion in Kubernetes, you don't need to configure any networking. When the agent runs your deployment, it will create a job, which will start a pod, which creates a container, which runs your flow. You can use standard Kubernetes tooling to display flow run jobs, e.g. `kubectl get jobs -l app=orion`.

Learn more about running Orion and flows on Kubernetes in the [Running flows in Kubernetes](https://orion-docs.prefect.io/tutorials/kubernetes-flow-runner/) tutorial. 

## 2.0a10

### Concurrent task runner

Speed up your flow runs with the new Concurrent Task Runner. Whether your code is synchronous or asynchronous, this [task runner](https://orion-docs.prefect.io/concepts/task-runners/) will enable tasks that are blocked on input/output to yield to other tasks. To enable this behavior, this task runner always runs synchronous tasks in a worker thread, whereas previously they would run in the main thread.

### Task run concurrency limits

When running a flow using a task runner that enables concurrent execution, or running many flows across multiple execution environments, you may want to limit the number of certain tasks that can run at the same time. 

Concurrency limits are set and enforced with task run tags. For example, perhaps you want to ensure that, across all of your flows, there are no more than three open connections to your production database at once. You can do so by creating a “prod-db” tag and applying it to all of the tasks that open a connection to that database. Then, you can create a concurrency limit with `prefect concurrency-limit create prod-db 3`. Now, Orion will ensure that no more than 3 task runs with the “prod-db” tag will run at the same time. Check out [the documentation](https://orion-docs.prefect.io/concepts/tasks/) for more information about task run concurrency limits and other task level concepts.

This feature was previously only available in a paid tier of Prefect Cloud, our hosted commercial offering. We’re very happy to move it to the open source domain, furthering our goal of making Orion the most capable workflow orchestration tool ever.

### Flow parameters

Previously, when calling a flow, we required passed arguments to be serializable data types. Now, flows will accept arbitrary types, allowing ad hoc flow runs and subflow runs to consume unserializable data types. This change is motivated by two important use-cases:

- The flow decorator can be added to a wider range of existing Python functions
- Results from tasks can be passed directly into subflows without worrying about types

Setting flow parameters via the API still requires serializable data so we can store your new value for the parameter. However, we support automatic deserialization of those parameters via type hints. See the [parameters documentation](https://orion-docs.prefect.io/concepts/flows/#parameters) for more details.

### Database migrations

The run metadata that Orion stores in its database is a valuable record of what happened and why. With new database migrations for both SQLite and PostgreSQL, you can retain your data when upgrading. The CLI interface has been updated to include new commands and revise an existing command to leverage these migrations:

- `prefect orion reset-db` is now `prefect orion database reset`
- `prefect orion database upgrade` runs upgrade migrations
- `prefect orion database downgrade` runs downgrade migrations

**Breaking Change**
Because these migrations were not in place initially, if you have installed any previous version of Orion, you must first delete or stamp the existing database with `rm ~/.prefect/orion.db` or `prefect orion database stamp`, respectively. Learn more about database migrations in [the documentation](https://orion-docs.prefect.io/tutorials/orion/#the-database).

### CLI refinements

The CLI has gotten some love with miscellaneous additions and refinements:

- Added `prefect --version` and `prefect -v` to expose version info
- Updated `prefect` to display `prefect --help`
- Enhanced `prefect dev` commands:
    - Added `prefect dev container` to start a container with local code mounted
    - Added `prefect dev build-image` to build a development image
    - Updated `prefect dev start` to hot-reload on API and agent code changes
    - Added `prefect dev api` and `prefect dev agent` to launch hot-reloading services individually

### Other enhancements

- Feel the thrill when you start Orion or an agent with our new banners
- Added a new logging setting for the Orion server log level, defaulting to "WARNING", separate from the client logging setting
- Added a method, `with_options`, to the `Task` class. With this method, you can easily create a new task with modified settings based on an existing task. This will be especially useful in creating tasks from a prebuilt collection, such as Prefect’s task library.
- The logs tab is now the default tab on flow run page, and has been refined with usability and aesthetic improvements.
- As Orion becomes more capable of distributed deployments, the risk of client/server incompatibility issues increases. We’ve added a guard against these issues with API version checking for every request. If the version is missing from the request header, the server will attempt to handle it. If the version is incompatible with the Orion server version, the server will reject it.

## 2.0a9

### Logs

This release marks another major milestone on Orion's continued evolution into a production ready tool. Logs are fundamental output of any orchestrator. Orion's logs are designed to work exactly the way that you'd expect them to work. Our logger is built entirely on Python's [standard library logging configuration hooks](https://docs.python.org/3/library/logging.config.html), so you can easily output to JSON, write to files, set levels, and more - without Orion getting in the way. All logs are associated with a flow run ID. Where relevant, they are also associated with a task run ID.

Once you've run your flow, you can find the logs in a dedicated tab on the flow run page, where you can copy them all or one line at a time. You can even watch them come in as your flow run executes. Future releases will enable further filter options and log downloads.
Learn more about logging in [the docs](https://orion-docs.prefect.io/concepts/logs/).

### Other Enhancements

In addition to logs, we also included the scheduler in the set of services started with `prefect orion start`. Previously, this required a dedicated flag or an additional command. Now, the scheduler is always available while Orion is running.

## 2.0a8

The 2.0a7 release required users to pull Docker images (e.g. `docker pull prefecthq/prefect:2.0a7-python3.8`) before the agent could run flows in Docker.

This release adds pull policies to the `DockerFlowRunner` allowing full control over when your images should be pulled from a registry. We infer reasonable defaults from the tag of your image, following the behavior of [Kubernetes image pull policies](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy).

## 2.0a7

### Flow Runners

On the heels of the recent rename of Onion's `Executor` to `TaskRunner`, this release introduces `FlowRunner`, an analogous concept that specifies the infrastructure that a flow runs on. Just as a task runner can be specified for a flow, which encapsulates tasks, a flow runner can be specified for a deployment, which encapsulates a flow. This release includes two flow runners, which we expect to be the most commonly used:
- **SubprocessFlowRunner** - The subprocess flow runner is the default flow runner. It allows for specification of a runtime Python environment with `virtualenv` and `conda` support.
- **DockerFlowRunner** - Executes the flow run in a Docker container. The image, volumes, labels, and networks can be customized. From this release on, Docker images for use with this flow runner will be published with each release.

Future releases will introduce runners for executing flows on Kubernetes and major cloud platform's container compute services (e.g. AWS ECS, Google Cloud Run).

### Other enhancements
In addition to flow runners, we added several other enhancements and resolved a few issues, including:
- Corrected git installation command in docs
- Refined UI through color, spacing, and alignment updates
- Resolved memory leak issues associated with the cache of session factories
- Improved agent locking of double submitted flow runs and handling for failed flow run submission

## 2.0a6

### Subflows and Radar follow up
With the 2.0a5 release, we introduced the ability to navigate seamlessly between subflows and parent flows via Radar. In this release, we further enabled that ability by:
- Enabling the dedicated subflow runs tab on the Flow Run page
- Tracking of upstream inputs to subflow runs
- Adding a flow and task run count to all subflow run cards in the Radar view
- Adding a mini Radar view on the Flow run page

### Task Runners
Previous versions of Prefect could only trigger execution of code defined within tasks. Orion can trigger execution of significant code that can be run _outside of tasks_. In order to make the role previously played by Prefect's `Executor` more explicit, we have renamed `Executor` to `TaskRunner`.

A related `FlowRunner` component is forthcoming.

### Other enhancements
In addition to task runners and subflow UI enhancements, we added several other enhancements and resolved a few issues, including:
- Introduced dependency injection pathways so that Orion's database access can be modified after import time
- Enabled the ability to copy the run ID from the flow run page
- Added additional metadata to the flow run page details panel
- Enabled and refined dashboard filters to improve usability, reactivity, and aesthetics
- Added a button to remove filters that prevent deployments without runs from displaying in the dashboard
- Implemented response scoped dependency handling to ensure that a session is always committed before a response is returned to the user

## 2.0a5

### Radar: A new way of visualizing workflows
Orion can orchestrate dynamic, DAG-free workflows. Task execution paths may not be known to Orion prior to a run—the graph “unfolds” as execution proceeds. Radar embraces this dynamism, giving users the clearest possible view of their workflows.

Orion’s Radar is based on a structured, radial canvas upon which tasks are rendered as they are orchestrated. The algorithm optimizes readability through consistent node placement and minimal edge crossings. Users can zoom and pan across the canvas to discover and inspect tasks of interest. The mini-map, edge tracing, and node selection tools make workflow inspection a breeze. Radar also supports direct click-through to a subflow from its parent, enabling users to move seamlessly between task execution graphs.

### Other enhancements
While our focus was on Radar, we also made several other material improvements to Orion, including:
- Added popovers to dashboard charts, so you can see the specific data that comprises each visualization
- Refactored the `OrionAgent` as a fully client side construct
- Enabled custom policies through dependency injection at runtime into Orion via context managers

## 2.0a4

We're excited to announce the fourth alpha release of Prefect's second-generation workflow engine.

In this release, the highlight is executors. Executors are used to run tasks in Prefect workflows.
In Orion, you can write a flow that contains no tasks.
It can call many functions and execute arbitrary Python, but it will all happen sequentially and on a single machine.
Tasks allow you to track and orchestrate discrete chunks of your workflow while enabling powerful execution patterns.

[Executors](https://orion-docs.prefect.io/concepts/executors/) are the key building blocks that enable you to execute code in parallel, on other machines, or with other engines.

### Dask integration

Those of you already familiar with Prefect have likely used our Dask executor.
The first release of Orion came with a Dask executor that could run simple local clusters.
This allowed tasks to run in parallel, but did not expose the full power of Dask.
In this release of Orion, we've reached feature parity with the existing Dask executor.
You can [create customizable temporary clusters](https://orion-docs.prefect.io/tutorials/dask-task-runner/#using-a-temporary-cluster) and [connect to existing Dask clusters](https://orion-docs.prefect.io/tutorials/dask-task-runner/#connecting-to-an-existing-cluster).
Additionally, because flows are not statically registered, we're able to easily expose Dask annotations, which allow you to [specify fine-grained controls over the scheduling of your tasks](https://orion-docs.prefect.io/tutorials/dask-task-runner/#annotations) within Dask.


### Subflow executors

[Subflow runs](https://orion-docs.prefect.io/concepts/flows/#subflows) are a first-class concept in Orion and this enables new execution patterns.
For example, consider a flow where most of the tasks can run locally, but for some subset of computationally intensive tasks you need more resources.
You can move your computationally intensive tasks into their own flow, which uses a `DaskExecutor` to spin up a temporary Dask cluster in the cloud provider of your choice.
Next, you simply call the flow that uses a `DaskExecutor` from your other, parent flow.
This pattern can be nested or reused multiple times, enabling groups of tasks to use the executor that makes sense for their workload.

Check out our [multiple executor documentation](https://orion-docs.prefect.io/concepts/executors/#using-multiple-task-runners) for an example.


### Other enhancements

While we're excited to talk about these new features, we're always hard at work fixing bugs and improving performance. This release also includes:

- Updates to database engine disposal to support large, ephemeral server flow runs
- Improvements and additions to the `flow-run` and `deployment` command-line interfaces
    - `prefect deployment ls`
    - `prefect deployment inspect <name>`
    - `prefect flow-run inspect <id>`
    - `prefect flow-run ls`
- Clarification of existing documentation and additional new documentation
- Fixes for database creation and startup issues
