# Prefect Release Notes

## Release 2.10.4

This release further refines Prefect 2.10 with enhancements for [project deployments](https://docs.prefect.io/latest/concepts/projects/#the-deployment-yaml-file) and
[workers](https://docs.prefect.io/latest/concepts/work-pools/#worker-overview), fixes for flow run cancellation and the worker CLI, and more.

### More flexible project deployments
Prior to this release, removing keys from a project's `deployment.yaml` caused an error. Thanks to the changes in [#9190](https://github.com/PrefectHQ/prefect/pull/9190), Prefect now uses default values for any required keys missing from your project's configuration.

### Enhancements
- Allow partial `deployment.yaml` files for projects by using defaults for missing values — [#9190](https://github.com/PrefectHQ/prefect/pull/9190)
- Add flow run cancellation support for workers - [#9198](https://github.com/PrefectHQ/prefect/pull/9198)

### Fixes
- Prevent scheduled flow runs from getting stuck in `CANCELLING` state  — [#8414](https://github.com/PrefectHQ/prefect/pull/8414)
- Fix `work_queues` and `worker_type` arguments for the `prefect worker start` CLI command — [#9154](https://github.com/PrefectHQ/prefect/pull/9154)
- Fix overflow in flow run logger UI [`#1342`](https://github.com/PrefectHQ/prefect-ui-library/pull/1342)
- Fix schema form handling of reference objects [`#1332`](https://github.com/PrefectHQ/prefect-ui-library/pull/1332)
- Improve flow graph UX by suppressing shortcuts when a metakey is active [`#1333`](https://github.com/PrefectHQ/prefect-ui-library/pull/1333)

### Experimental
- Emit an event when a worker submits a flow run for execution — [#9203](https://github.com/PrefectHQ/prefect/pull/9203)

### Documentation
- Fix a broken link by removing an obsolete redirect — [#9189](https://github.com/PrefectHQ/prefect/pull/9189)
- Add polling interval information to worker and agent documentation — [#9209](https://github.com/PrefectHQ/prefect/pull/9209)
- Update documentation badge styling to improve docs usability — [#9207](https://github.com/PrefectHQ/prefect/pull/9207)


## Release 2.10.3

This release builds on 2.10 to further improve the experience of setting up and deploying from [a prefect project](https://docs.prefect.io/latest/tutorials/projects/).  In particular, initializing with a recipe now initializes an interactive CLI experience that guides you to a correct setup.  This experience can be avoided for programmatic initialization by providing all required fields for the recipe via CLI.  For more information, see [the project documentation](https://docs.prefect.io/latest/concepts/projects/).  We will continue to enhance the deployment experience as we receive feedback, so please keep it coming!

This release also includes [a critical fix](https://github.com/PrefectHQ/prefect/pull/9180) for Prefect logs that were sometimes delayed in being sent to the API.


### Enhancements
- Rename `__root_path__` to `__development_base_path__` — https://github.com/PrefectHQ/prefect/pull/9136
- Include flow run and flow as related resources when emitting events via the events worker — https://github.com/PrefectHQ/prefect/pull/9129
- Cloud storage recipe improvements — https://github.com/PrefectHQ/prefect/pull/9145
- Use new sessions and transactions for each query during `CancellationCleanup` — https://github.com/PrefectHQ/prefect/pull/9124
- Stream `git` output during `git_clone_project` — https://github.com/PrefectHQ/prefect/pull/9149
- Update deployment defaults with project init — https://github.com/PrefectHQ/prefect/pull/9146
- Mock runtime via environment variable — https://github.com/PrefectHQ/prefect/pull/9156
- Wire up scheduling kwargs to deploy CLI — https://github.com/PrefectHQ/prefect/pull/9176
- Add deployment and flow filters to `/artifacts/filter` and `/artifacts/latest/filter` routes — https://github.com/PrefectHQ/prefect/pull/9089
- Add `/artifacts/latest/count` route — https://github.com/PrefectHQ/prefect/pull/9090
- add flow run to task run logging — https://github.com/PrefectHQ/prefect/pull/9170
- Add pragma statements automatically if sqlite — https://github.com/PrefectHQ/prefect/pull/9169
- Improved recipe initialization UX — https://github.com/PrefectHQ/prefect/pull/9158

### Fixes
- Update `prefect deploy` to pull `flow_name` and `entrypoint` from deployment.yaml if specified — https://github.com/PrefectHQ/prefect/pull/9157
- Fix bug where non-zero status codes would be reported when deployed flow runs paused or failed — https://github.com/PrefectHQ/prefect/pull/9175
- Hide command when access token is provided and `git_clone_project` fails — https://github.com/PrefectHQ/prefect/pull/9150
- Fix bug where log worker only sent logs to API on flush rather than on an interval — https://github.com/PrefectHQ/prefect/pull/9180
- Fix apply artifact collection filter — https://github.com/PrefectHQ/prefect/pull/9153

### Documentation
- Adds artifacts to api-ref — https://github.com/PrefectHQ/prefect/pull/9143
- Expands upon project step documentation — https://github.com/PrefectHQ/prefect/pull/9151
- small project doc fixes — https://github.com/PrefectHQ/prefect/pull/9161

### Collections
- add prefect-spark-on-k8s-operator to integrations catalog list. — https://github.com/PrefectHQ/prefect/pull/9029

### Contributors
* @tardunge made their first contribution in https://github.com/PrefectHQ/prefect/pull/9029

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.10.2...2.10.3

## Release 2.10.2

Fixes a bug where deployments were not downloaded from remote storage blocks during flow runs — https://github.com/PrefectHQ/prefect/pull/9138

### Enhancements
- Add httpx.ConnectTimeout to the list of retry exceptions in base client — https://github.com/PrefectHQ/prefect/pull/9125

### Contributors
* @sorendaugaard made their first contribution in https://github.com/PrefectHQ/prefect/pull/9125


**All changes**: https://github.com/PrefectHQ/prefect/compare/2.10.1...2.10.2

## Release 2.10.1

Fixes a bug with accessing project recipes through the CLI. See the [pull request](https://github.com/PrefectHQ/prefect/pull/9132) for implementation details.

## Release 2.10.0

Prefect deployments often have critical, implicit dependencies on files and build artifacts, such as containers, that are created and stored outside of Prefect. Each of these dependencies is a potential stumbling block when deploying a flow - you need to ensure that they're satisfied for your flow to run successfully. In this release, we're introducing two new beta features, workers and projects, to help you better manage your flow deployment process. Additionally, we're releasing variables for centralized management of management and expanding events and automations to include blocks. There are a lot of highlighted features this week — but we've also made some significant performance improvements alongside a slew of bug fixes and enhancements!

### Workers [Beta]

Workers are next-generation agents, designed from the ground up to interact with [work pools](https://docs.prefect.io/concepts/work-pools/). Each worker manages flow run infrastructure of a specific type and must pull from a work pool with a matching type. Existing work pools are all "agent" typed for backwards compatibility with our agents — but new work pools can be assigned a specific infrastructure type. Specifying a type for a work pool simplifies choosing what kind of infrastructure will be used when creating a flow run. 

Work pools expose rich configuration of their infrastructure. Every work pool type has a base configuration with sensible defaults such that you can begin executing work with just a single command. The infrastructure configuration is fully customizable from the Prefect UI. For example, you can now customize the entire payload used to run flows on Kubernetes — you are not limited to the fields Prefect exposes in its SDK. We provide templating to inject runtime information and common settings into infrastructure creation payloads. Advanced users can add _custom_ template variables which are then exposed the same as Prefect's default options in an easy to use UI.

If the work pool’s configuration is updated, all workers automatically begin using the new settings — you no longer need to redeploy your agents to change infrastructure settings. For advanced use cases, you can override settings on a per-deployment basis.

This release includes Process, Kubernetes, and Docker worker types. Additional worker types will be included in subsequent releases.

Creating a Kubernetes work pool:

<img width="1601" alt="Creating a new Kubernetes work pool" src="https://user-images.githubusercontent.com/2586601/230471683-63875a04-f331-4cf1-8b1b-69c2cd0e4e05.png">
<img width="1601" alt="Advanced configuration of the work pool infrastructure" src="https://user-images.githubusercontent.com/2586601/230471686-7146e930-34fc-43ae-a946-9e3795c4a27a.png">

Adding a new variable to the advanced work pool configuration will expose it in the basic config:

<img width="1551" alt="Adding a variable to the advanced config" src="https://user-images.githubusercontent.com/2586601/230475075-b535b158-62a8-4b88-9439-0054f58e8f77.png">
<img width="1601" alt="New variables can be adjusted in the basic config" src="https://user-images.githubusercontent.com/2586601/230473701-b8db1973-eb03-4682-86cc-64b698356048.png">

See the updated [work pool, workers, & agents concepts documentation](https://docs.prefect.io/latest/concepts/work-pools/) for more information.

### Projects [Beta]

A project is a directory of files that define one or more flows, deployments, Python packages, or any other dependencies that your flow code needs to run. If you’ve been using Prefect, or working on any non-trivial Python project, you probably have an organized structure like this already. Prefect projects are minimally opinionated, so they can work with the structure you already have in place and with the containerization, version control, and build automation tools that you know and love. With projects as directories, you can make relative references between files while retaining portability. We expect most projects to map directly to a git repository. In fact, projects offer a first-class way to clone a git repository so they can be easily shared and synced.

Projects also include a lightweight build system that you can use to define the process for deploying flows in that project. That procedure is specified in a new `prefect.yaml` file, in which you can specify steps to build the necessary artifacts for a project's deployments, push those artifacts, and retrieve them at runtime.

Projects are a contract between you and a worker, specifying what you do when you create a deployment, and what the worker will do before it kicks off that deployment. Together, projects and workers bridge your development environment, where your flow code is written, and your execution environment, where your flow code runs. Create your first Prefect project by following [this tutorial](https://docs.prefect.io/latest/tutorials/projects/).

See the new [project concept doc](https://docs.prefect.io/latest/concepts/projects/) for more information or the following pull requests for implementation details:

- https://github.com/PrefectHQ/prefect/pull/8930
- https://github.com/PrefectHQ/prefect/pull/9103
- https://github.com/PrefectHQ/prefect/pull/9105
- https://github.com/PrefectHQ/prefect/pull/9112
- https://github.com/PrefectHQ/prefect/pull/9093
- https://github.com/PrefectHQ/prefect/pull/9083
- https://github.com/PrefectHQ/prefect/pull/9041

### Variables

Variables enable you to store and reuse non-sensitive bits of data, such as configuration information. Variables are named, mutable string values, much like environment variables. They are scoped to a Prefect Server instance or a single workspace in Prefect Cloud. Variables can be created or modified at any time. While variable values are most commonly loaded during flow runtime, they can be loaded in other contexts, at any time, such that they can be used to pass configuration information to Prefect configuration files, such as project steps. You can access any variable via the Python SDK via the `.get()` method. 

```python
from prefect import variables

# from a synchronous context
answer = variables.get('the_answer')
print(answer)
# 42

# from an asynchronous context
answer = await variables.get('the_answer')
print(answer)
# 42

# without a default value
answer = variables.get('not_the_answer')
print(answer)
# None

# with a default value
answer = variables.get('not_the_answer', default='42')
print(answer)
# 42
```

See the new [variables concept doc](https://docs.prefect.io/latest/concepts/variables/) for more information or the [pull request](https://github.com/PrefectHQ/prefect/pull/9088) for implementation details.

### Events

Continuing the rollout of events[https://docs.prefect.io/concepts/events-and-resources/] as the primary unit of observability in Prefect Cloud, Prefect will now emit events for all block method calls by default. These events can be viewed in the Event feed, allowing you to analyze the interactions your flows and tasks have with external systems such as storage locations, notification services, and infrastructure. Additionally, you can trigger automations based on these events. For example, you can create an automation that is triggered when a file is uploaded to a storage location.

![image](https://user-images.githubusercontent.com/26799928/230421783-997e4fda-a02f-4bf4-88e1-f51a2f890cf5.png)

### Versioned documentation

We're releasing a lot of new features every week and we know not everyone is on the latest version of Prefect. We've added versioning to our documentation website to make it easier to find the docs for the version of Prefect that you're using.

Now, when you visit the Prefect documentation site, you'll see a version selector at the top of the page. 

![versioned docs](https://user-images.githubusercontent.com/228762/230432235-26fc9406-1390-4c63-9956-b8cdabdfba6f.png)


### Breaking Changes
- Unused options for sorting logs have been removed from the API — https://github.com/PrefectHQ/prefect/pull/7873

### Enhancements
- Add artifacts view to flow run page — https://github.com/PrefectHQ/prefect/pull/9109
- Improve performance of the background event worker — https://github.com/PrefectHQ/prefect/pull/9019
- Update deployment flow run creation to default to a SCHEDULED state instead of PENDING — https://github.com/PrefectHQ/prefect/pull/9049
- Add `PREFECT_CLIENT_RETRY_EXTRA_CODES` to allow retry on additional HTTP status codes — https://github.com/PrefectHQ/prefect/pull/9056
- Improve performance of the background log worker — https://github.com/PrefectHQ/prefect/pull/9048
- Update agent cancellation check interval to double the scheduled check interval — https://github.com/PrefectHQ/prefect/pull/9084
- Update default agent query interval from 10s to 15s — https://github.com/PrefectHQ/prefect/pull/9085
- Add a 10 minute cache to API healthchecks — https://github.com/PrefectHQ/prefect/pull/9069
- Improve performance of concurrent task runner — https://github.com/PrefectHQ/prefect/pull/9073
- Improve performance of waiting for task submission — https://github.com/PrefectHQ/prefect/pull/9072
- Add retry on 502 BAD GATEWAY to client — https://github.com/PrefectHQ/prefect/pull/9102
- Update local and remote file systems to return path on write — https://github.com/PrefectHQ/prefect/pull/8965
- Add artifacts `/count` route — https://github.com/PrefectHQ/prefect/pull/9022
- Improve performance of automatic block registration — https://github.com/PrefectHQ/prefect/pull/8838
- Improve performance of log retrieval queries — https://github.com/PrefectHQ/prefect/pull/9035
- Improve performance of artifact retrieval — https://github.com/PrefectHQ/prefect/pull/9061 / https://github.com/PrefectHQ/prefect/pull/9064
- Add `--type` option to create work-pool CLI — https://github.com/PrefectHQ/prefect/pull/8993
- Improve flow run timeline performance - https://github.com/PrefectHQ/prefect-ui-library/pull/1315
- Add flow names to sub flows on the flow run timeline graph - https://github.com/PrefectHQ/prefect-ui-library/pull/1304

### Fixes
- Fix bug where iterable defaults were treated as mapped parameters — https://github.com/PrefectHQ/prefect/pull/9021
- Fix sequential execution with mapped tasks using the SequentialTaskRunner — https://github.com/PrefectHQ/prefect/pull/8473
- Fix race condition where futures did not wait for submission to complete — https://github.com/PrefectHQ/prefect/pull/9070
- Fix detection of iterables within `quote` annotations while mapping — https://github.com/PrefectHQ/prefect/pull/9095
- Fix Dockerfile copy of UI package files on latest Docker version — https://github.com/PrefectHQ/prefect/pull/9077

### Documentation
- Add copy to clipboard button in documentation code blocks — https://github.com/PrefectHQ/prefect/pull/9026
- Fixed styling of deployments mermaid diagram — https://github.com/PrefectHQ/prefect/pull/9017
- Add documentation for database migrations — https://github.com/PrefectHQ/prefect/pull/9044
- Adds documentation for BitBucket to flow code storage types — https://github.com/PrefectHQ/prefect/pull/9080
- Update rate limit documentation for Cloud — https://github.com/PrefectHQ/prefect/pull/9100

### Contributors
- @mianos made their first contribution in https://github.com/PrefectHQ/prefect/pull/9077
- @dominictarro made their first contribution in https://github.com/PrefectHQ/prefect/pull/8965
- @joelluijmes
- @john-jam

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.9.0...2.10.0

## Release 2.9.0

### Track and manage artifacts

Most workflows produce or update an artifact of some kind, whether it's a table, a file, or a model. With Prefect Artifacts, you can track changes to these outputs and richly display them in the UI as tables, markdown, and links. Artifacts may be associated with a particular task run, flow run, or even exist outside a flow run context, enabling you to not only observe your flows, but the objects that they interact with as well. 

![Artifacts top-level view](https://user-images.githubusercontent.com/27291717/228905742-0bad7874-6b6b-4000-9111-1c4d0e0bd6e1.png)

A variety of artifact types are available. To create an artifact that produces a table, for example, you can use the `create_table_artifact()` function.

```python
from prefect import task, flow
from prefect.artifacts import create_table_artifact

@task
def my_table_task():
    table_data = [
        {"id": 0, "name": "Dublin", "lat": 53.3498, "lon": -6.2603,},
        {"id": 1, "name": "London", "lat": 51.5074, "lon": -0.1278,},
        {"id": 2, "name": "New York", "lat": 40.7128, "lon": -74.0060,},
        {"id": 3, "name": "Oslo", "lat": 59.9139, "lon": 10.7522,},
        {"id": 4, "name": "Paris", "lat": 48.8566, "lon": 2.3522,},
        {"id": 5, "name": "Rome", "lat": 41.9028, "lon": 12.4964,},
        {"id": 6, "name": "Tokyo", "lat": 35.6895, "lon": 139.6917,},
        {"id": 7, "name": "Vancouver", "lat": 49.2827, "lon": -123.1207,}
    ]

    return create_table_artifact(
        key="cities-table",
        table=table_data,
        description="A table of cities and their coordinates",
    )

@flow
def my_flow():
    table = my_table_task()
    return table

if __name__ == "__main__":
    my_flow()

```

You can view your artifacts in the Artifacts page of the Prefect UI, easily search the data in your new table artifact, and toggle between a rendered and raw version of your data.

![Table artifact in a timeline view](https://user-images.githubusercontent.com/27291717/228905740-bd297de9-6381-45ec-aba3-8b72def70a08.png)

See [the documentation](https://docs.prefect.io/concepts/artifacts) for more information, as well as the following pull requests for implementation details:
- https://github.com/PrefectHQ/prefect/pull/9003
- https://github.com/PrefectHQ/prefect/pull/8832
- https://github.com/PrefectHQ/prefect/pull/8932
- https://github.com/PrefectHQ/prefect/pull/8875
- https://github.com/PrefectHQ/prefect/pull/8874
- https://github.com/PrefectHQ/prefect/pull/8985

### Configure result storage keys

When persisting results, Prefect stores data at a unique, randomly-generated path. While this is convenient for ensuring the result is never overwritten, it limits organization of result files. In this release, we've added configuration of result storage keys, which gives you control over the result file path. Result storage keys can be dynamically formatted with access to all of the modules in `prefect.runtime` and the run's `parameters`. 

For example, you can name each result to correspond to the flow run that produced it and a parameter it received:

```python
from prefect import flow, task

@flow()
def my_flow():
    hello_world()
    hello_world(name="foo")
    hello_world(name="bar")

@task(
    persist_result=True,
    result_storage_key="hello__{flow_run.name}__{parameters[name]}.json",
)
def hello_world(name: str = "world"):
    return f"hello {name}"

my_flow()
```

Which will persist three result files in the storage directory:
```
$ ls ~/.prefect/storage | grep "hello__" 
hello__rousing-mushroom__bar.json
hello__rousing-mushroom__foo.json
hello__rousing-mushroom__world.json
```

See [the documentation](https://docs.prefect.io/concepts/results/#result-storage-key) for more information. 

### Expanded `prefect.runtime`

The `prefect.runtime` module is now the preferred way to access information about the current run. In this release, we've added the following attributes:

- `prefect.runtime.task_run.id`
- `prefect.runtime.task_run.name`
- `prefect.runtime.task_run.task_name`
- `prefect.runtime.task_run.tags`
- `prefect.runtime.task_run.parameters`
- `prefect.runtime.flow_run.name`
- `prefect.runtime.flow_run.flow_name`
- `prefect.runtime.flow_run.parameters`

See [the documentation](https://docs.prefect.io/concepts/runtime-context/) for more information.

See the following pull requests for implementation details:
- https://github.com/PrefectHQ/prefect/pull/8947
- https://github.com/PrefectHQ/prefect/pull/8948
- https://github.com/PrefectHQ/prefect/pull/8949
- https://github.com/PrefectHQ/prefect/pull/8951
- https://github.com/PrefectHQ/prefect/pull/8954
- https://github.com/PrefectHQ/prefect/pull/8956

### Enhancements
- Add unique integers to worker thread names for inspection - https://github.com/PrefectHQ/prefect/pull/8908
- Add support to `JSONSerializer` for serialization of exceptions so they are persisted even on failure - https://github.com/PrefectHQ/prefect/pull/8922
- Add Gzip middleware to the UI and API FastAPI apps for compressing responses - https://github.com/PrefectHQ/prefect/pull/8931
- Update the runtime to detect flow run information from task run contexts — https://github.com/PrefectHQ/prefect/pull/8951

### Fixes
- Fix imports in copytree backport for Python 3.7 - https://github.com/PrefectHQ/prefect/pull/8925
- Retry on sqlite operational errors - https://github.com/PrefectHQ/prefect/pull/8950
- Add 30 second timeout to shutdown of the log worker thread — https://github.com/PrefectHQ/prefect/pull/8983

### Documentation
- Disambiguate reference to "Blocks" - https://github.com/PrefectHQ/prefect/pull/8921
- Fix broken concepts link - https://github.com/PrefectHQ/prefect/pull/8923
- Add note about fine-grained PAT format - https://github.com/PrefectHQ/prefect/pull/8929
- Add `UnpersistedResult` type - https://github.com/PrefectHQ/prefect/pull/8953
- Update docs CSS and config for versioning compatibility - https://github.com/PrefectHQ/prefect/pull/8957
- Clarify Filesystem package dependencies - https://github.com/PrefectHQ/prefect/pull/8989
- Update flow runs documentation - https://github.com/PrefectHQ/prefect/pull/8919
- Fix missing backticks on Work Pools concept page - https://github.com/PrefectHQ/prefect/pull/8942
- Update links to the release notes in the installation guide - https://github.com/PrefectHQ/prefect/pull/8974
- Fix `EXTRA_PIP_PACKAGES` info in Docker guide — https://github.com/PrefectHQ/prefect/pull/8995
- Fix `KubernetesJob.job_watch_timeout_seconds` docstring — https://github.com/PrefectHQ/prefect/pull/8977
- Add task run runtime to API reference — https://github.com/PrefectHQ/prefect/pull/8998
- Add documentation for runtime context — https://github.com/PrefectHQ/prefect/pull/8999

### Contributors
- @andreadistefano made their first contribution in https://github.com/PrefectHQ/prefect/pull/8942
- @knl made their first contribution in https://github.com/PrefectHQ/prefect/pull/8974
- @thomas-te made their first contribution in https://github.com/PrefectHQ/prefect/pull/8959
## Release 2.8.7

If you have been watching the experimental section of our release notes, you may have noticed a lot of work around concurrency tooling, flow run graph enhancements, and result artifacts. With this release, these experiments have culminated into exciting features!

### Engine reliability

Supporting mixed asynchronous and synchronous code is complicated, but important. When designing Prefect 2, we wanted to account for the future growth of asynchronous Python and the many user requests for asynchronous task support. Most of this complexity is buried in the Prefect engine, which manages execution of your flows and tasks. With this release, we've made some dramatic improvements to the engine, closing some long-standing bugs and ensuring that it isn't a point of failure when running your flows.

The behavioral changes include:

- All orchestration of flows and tasks happens in a dedicated worker thread
- Synchronous flows are run on the main thread instead of worker threads
    - Solves problems where flow code must be in the main thread e.g. https://github.com/PrefectHQ/prefect/issues/5991
- Asynchronous flows no longer share an event loop with the Prefect engine
- Flow timeouts are now enforced with signals
    - Allows interrupt of long-running system calls like `sleep` for more effective timeout enforcement
- Asynchronous flows can be called from sync flows
- Asynchronous tasks can be used as upstream dependencies for sync tasks in async flows
- Synchronous tasks can be submitted from asynchronous flows
- Waiting for many tasks that sleep no longer causes deadlocks
- Flows with thousands of synchronous tasks are less likely to crash
- Debug mode now enables verbose logging from Prefect concurrency internals
- The API limits itself to 100 concurrent requests when using SQLite as a backend
    - Avoids database file contention when using high levels of concurrency
- Resolving task inputs no longer uses worker threads
    - Resolves issues where large numbers of upstream task inputs would cause deadlocks
    - Instead of using worker threads, we wait for upstream tasks on the event loop to support high levels of concurrency

See the following pull requests for implementation details:

- https://github.com/PrefectHQ/prefect/pull/8702
- https://github.com/PrefectHQ/prefect/pull/8887
- https://github.com/PrefectHQ/prefect/pull/8903
- https://github.com/PrefectHQ/prefect/pull/8830

### Results tab on flow run pages

The Prefect UI now renders information about your flow run and task run results! 

This view provides a visual representation of the output of your tasks and flows and, when possible, provides links to results persisted using any of our storage blocks. To see this in your UI, run any flow and navigate to the run page; from there you'll see a new tab, "Results":

![Results list view](https://user-images.githubusercontent.com/27291717/227274576-1379c67c-6624-4a79-9bf7-83ae70e1fb4d.png)
![Results grid view](https://user-images.githubusercontent.com/27291717/227274578-35673508-09e2-4b83-bc22-11538f813eea.png)

See the following pull requests for implementation details:
- https://github.com/PrefectHQ/prefect-ui-library/pull/1207
- https://github.com/PrefectHQ/prefect-ui-library/pull/1213
- https://github.com/PrefectHQ/prefect-ui-library/pull/1223
- https://github.com/PrefectHQ/prefect/pull/8904
- https://github.com/PrefectHQ/prefect/pull/8759

### Flow run graph

We heard that people loved the simplicity and sleekness of the timeline on the flow run page, but valued the radar graph's ability to traverse between flow runs and subflows runs. This release introduces the ability to expand and collapse subflow runs within the timeline. With these enhancements, the flow run timeline has now evolved into a general purpose flow run graph, with the ability to render thousands of nodes and edges performantly. The radar graph has been retired. You can now observe and explore your flow runs even more quickly and easily in a single flow run graph!

<img width="1497" alt="Flow run timeline" src="https://user-images.githubusercontent.com/2586601/227337664-8d856634-7093-4002-ab55-57986eeaa2ed.png">
<img width="1496" alt="Subflow run expansion" src="https://user-images.githubusercontent.com/2586601/227337673-5cc574c9-76a6-442b-b579-e8fd2a184fd3.png">

### Enhancements
- Add `--reverse` option to the flow run logs CLI to view logs in descending order — https://github.com/PrefectHQ/prefect/pull/8625
- Show all flow runs for deployments rather than just the last 7 days — https://github.com/PrefectHQ/prefect/pull/8837
- Add jitter to Prefect client request retries — https://github.com/PrefectHQ/prefect/pull/8839
- Add `deployment.name` and `deployment.version` to `prefect.runtime` — https://github.com/PrefectHQ/prefect/pull/8864
- Add `flow_run.scheduled_start_time` to `prefect.runtime` — https://github.com/PrefectHQ/prefect/pull/8864
- Adjust SQLite sync mode for improved performance — https://github.com/PrefectHQ/prefect/pull/8071
- Add debug level log of active profile on module import — https://github.com/PrefectHQ/prefect/pull/8856
- Update server to use new FastAPI lifespan context manager — https://github.com/PrefectHQ/prefect/pull/8842
- Add support for variadic keyword arguments to `Task.map` — https://github.com/PrefectHQ/prefect/pull/8188
- Show the full run history in the UI — https://github.com/PrefectHQ/prefect/pull/8885

### Fixes
- Fix `prefect dev start` failure — https://github.com/PrefectHQ/prefect/pull/8850
- Fix bug where `propose_state` could exceed recursion limits during extended waits — https://github.com/PrefectHQ/prefect/pull/8827
- Fix configuration of flow run infrastructure when using agent default — https://github.com/PrefectHQ/prefect/pull/8872
- Fix saving block document secrets that have not been modified — https://github.com/PrefectHQ/prefect/pull/8848
- Disable SLSA provenance setting in Docker buildx to resolve image pull errors with certain Cloud providers — https://github.com/PrefectHQ/prefect/pull/8889
- Fix race condition in worker thread start — https://github.com/PrefectHQ/prefect/pull/8886
- The state message has been returned to the flow run metadata panel on the right side of the flow run page - https://github.com/PrefectHQ/prefect/pull/8885

### Experimental
- Update to worker base job template logic for nested placeholders — https://github.com/PrefectHQ/prefect/pull/8795
- Require lowercase artifact `key` field — https://github.com/PrefectHQ/prefect/pull/8860
- Create `emit_event` helper that takes args for an `Event` and emits it via a worker — https://github.com/PrefectHQ/prefect/pull/8867
- Allow multiple artifacts to have the same key — https://github.com/PrefectHQ/prefect/pull/8855
- Add common values to job configuration prior to flow run submission — https://github.com/PrefectHQ/prefect/pull/8826

### Deprecations
- Creating data documents will now throw deprecation warnings — https://github.com/PrefectHQ/prefect/pull/8760

### Documentation
- Add documentation for events and resources — https://github.com/PrefectHQ/prefect/pull/8858

### Contributors
* @lounis89 made their first contribution in https://github.com/PrefectHQ/prefect/pull/8625
* @mesejo made their first contribution in https://github.com/PrefectHQ/prefect/pull/8842

## Release 2.8.6

### `prefect.runtime` for context access

Many users of Prefect run their flows in highly dynamic environments; because of this it can be incredibly useful to access information about the current flow run or deployment run outside of a flow function for configuration purposes. For example, if we are running a Prefect deployment within a larger Dask cluster, we might want to use each flow run id as the Dask client name for easier searching of the scheduler logs. Prefect now offers a user-friendly way of accessing this information through the `prefect.runtime` namespace:

```python
from prefect.runtime import flow_run
from prefect import flow
from prefect_dask.task_runners import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(client_kwargs = {"name": flow_run.id}))
def my_flow():
    ...
```

This will create a Dask client whose name mirrors the flow run ID. Similarly, you can use `prefect.runtime` to access parameters that were passed to this deployment run via `prefect.runtime.deployment.parameters`. Note that all of these attributes will be empty if they are not available.

See https://github.com/PrefectHQ/prefect/pull/8790 for details.

### Enhancements
- Add deployment id support to `run_deployment` — https://github.com/PrefectHQ/prefect/pull/7958
- Disable Postgres JIT for performance improvements — https://github.com/PrefectHQ/prefect/pull/8804

### Fixes
- Fix blocking file read in async method `Deployment.load_from_yaml` — https://github.com/PrefectHQ/prefect/pull/8798
- Allow tasks and flows to make redundant transitions such as `RUNNING` -> `RUNNING` — https://github.com/PrefectHQ/prefect/pull/8802

### Experimental
- Enable setting environment variables for worker submitted flow runs — https://github.com/PrefectHQ/prefect/pull/8706
- Add `--work-queue` option to worker CLI — https://github.com/PrefectHQ/prefect/pull/8771
- Add artifact description column — https://github.com/PrefectHQ/prefect/pull/8805
- Format types in result descriptions as code — https://github.com/PrefectHQ/prefect/pull/8808
- Add artifacts for unpersisted results — https://github.com/PrefectHQ/prefect/pull/8759
- Update default result descriptions — https://github.com/PrefectHQ/prefect/pull/8772

### Documentation
- Update workspace roles table to emphasize differences between roles — https://github.com/PrefectHQ/prefect/pull/8787
- Add webhook block docs — https://github.com/PrefectHQ/prefect/pull/8773
- Update info on Ray's support for hardware and software — https://github.com/PrefectHQ/prefect/pull/8811

### Helm chart
- Helm charts are now automatically published on each Prefect release — https://github.com/PrefectHQ/prefect/pull/8776

### Contributors
- @devanshdoshi9

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.8.5...2.8.6

## Release 2.8.5

### Enhancements
- Add an endpoint to retrieve data from the collection registry — https://github.com/PrefectHQ/prefect/pull/8685
- Remove deployment flow run foreign key to speed up deployment deletion — https://github.com/PrefectHQ/prefect/pull/8684

### Fixes
- Fix `prefect cloud login` detection of "ENTER" on some machines — https://github.com/PrefectHQ/prefect/pull/8705
- Fix Kubernetes job watch timeout request error by rounding floats — https://github.com/PrefectHQ/prefect/pull/8733
- Fix flow load errors by excluding fsspec `2023.3.0` during requirements installation — https://github.com/PrefectHQ/prefect/pull/8757
- Fix Deployment and Concurrency Limit pages tabs — https://github.com/PrefectHQ/prefect/pull/8716
- Add tests for base exceptions and calls — https://github.com/PrefectHQ/prefect/pull/8734

### Experimental
- Refactor supervisor API to allow configuration — https://github.com/PrefectHQ/prefect/pull/8695
- Consolidate `WorkItem` and `Call` classes — https://github.com/PrefectHQ/prefect/pull/8697
- Use `PREFECT_API_URL` when initializing the events client — https://github.com/PrefectHQ/prefect/pull/8704
- Refactor supervisors to interact directly with "Worker" threads — https://github.com/PrefectHQ/prefect/pull/8714
- Add chaining to cancel contexts — https://github.com/PrefectHQ/prefect/pull/8719
- Add portal abstract base for worker threads and supervisors — https://github.com/PrefectHQ/prefect/pull/8717
- Fix bugs in supervisors implementation — https://github.com/PrefectHQ/prefect/pull/8718
- Refactor concurrency module and add documentation — https://github.com/PrefectHQ/prefect/pull/8724
- Update block event resource IDs to use block-document id instead of name. — https://github.com/PrefectHQ/prefect/pull/8730
- Add cancellation reporting to calls and waiters — https://github.com/PrefectHQ/prefect/pull/8731
- Add worker command output when applying deployments with a work pool — https://github.com/PrefectHQ/prefect/pull/8725
- Add support for float timeouts using alarms — https://github.com/PrefectHQ/prefect/pull/8737
- Add the ability to discover type from work pool when starting a worker — https://github.com/PrefectHQ/prefect/pull/8711
- Add basic event instrumentation to blocks — https://github.com/PrefectHQ/prefect/pull/8686

### Documentation
- Corrected typo in Storage.md — https://github.com/PrefectHQ/prefect/pull/8692
- Fix `prefect flow-run cancel` help — https://github.com/PrefectHQ/prefect/pull/8755

### Contributors
* @Zesky665 made their first contribution in https://github.com/PrefectHQ/prefect/pull/8692
* @predatorprasad made their first contribution in https://github.com/PrefectHQ/prefect/pull/8755


## Release 2.8.4

### Enhancements
- Enable `DefaultAzureCredential` authentication for Azure filesystem block — https://github.com/PrefectHQ/prefect/pull/7513
- Add support for yaml config strings to `KubernetesClusterConfig` — https://github.com/PrefectHQ/prefect/pull/8643
- Add `--description` flag to `prefect deployment build` CLI command — https://github.com/PrefectHQ/prefect/pull/8603
- Handle SIGTERM received by server gracefully — https://github.com/PrefectHQ/prefect/pull/7948
- Optimize database query performance by changing SQLAlchemy lazy loads from `joined` to `selectin` — https://github.com/PrefectHQ/prefect/pull/8659
- Add clarifying modal to the task run page in the UI — https://github.com/PrefectHQ/prefect/pull/8295

### Fixes
- Ensure flow parameters default values are present during deployment runs — https://github.com/PrefectHQ/prefect/pull/8666
- Use a monotonic clock for Kubernetes job watch timeout deadline calculation — https://github.com/PrefectHQ/prefect/pull/8680
- Fix version misaligned on the settings page in the UI — https://github.com/PrefectHQ/prefect/pull/8676

### Experimental
- Refactor supervisors to manage submission — https://github.com/PrefectHQ/prefect/pull/8631
- Improve supervisor repr for debugging — https://github.com/PrefectHQ/prefect/pull/8633
- Add timeout support to supervisors — https://github.com/PrefectHQ/prefect/pull/8649
- Track flow run id when generating task run results — https://github.com/PrefectHQ/prefect/pull/8674
- Create `EventsWorker` to manage client lifecycle and abstract async nature — https://github.com/PrefectHQ/prefect/pull/8673

### Documentation
- Add tutorial for running an agent on Azure Container Instances — https://github.com/PrefectHQ/prefect/pull/8620
- Add security headers for docs — https://github.com/PrefectHQ/prefect/pull/8655
- Add markdown link fix in orchestration docs — https://github.com/PrefectHQ/prefect/pull/8660

## New Contributors
* @samdyzon made their first contribution in https://github.com/PrefectHQ/prefect/pull/7513
* @mjschock made their first contribution in https://github.com/PrefectHQ/prefect/pull/8660
* @jcorrado76 made their first contribution in https://github.com/PrefectHQ/prefect/pull/8603
* @scharlottej13 made their first contribution in https://github.com/PrefectHQ/prefect/pull/8669

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.8.3...2.8.4

## Release 2.8.3

### `on_completion` and `on_failure` hooks for flows and tasks
With this release you can now add client-side hooks that will be called when your flow or task enters a `Completed` or `Failed` state. This is great for any case where you want to execute code without involvement of the Prefect API. 

Both flows and tasks include `on_completion` and `on_failure` options where a list of callable hooks can be provided. The callable will receive three arguments:
- `flow`, `flow_run`, and `state` in the case of a flow hook
- `task`, `task_run`, and `state` in the case of a task hook

For example, here we add completion hooks to a flow and a task:

```python
from prefect import task, flow

def my_completion_task_hook_1(task, task_run, state):
    print("This is the first hook - Task completed!!!")
    
def my_completion_task_hook_2(task, task_run, state):
  print("This is the second hook - Task completed!!!")
    
def my_completion_flow_hook(flow, flow_run, state):
    print("Flow completed!!!")
    
@task(on_completion=[my_completion_task_hook_1, my_completion_task_hook_2])
def my_task():
    print("This is the task!")

@flow(on_completion=[my_completion_flow_hook])
def my_flow():
    my_task()

if __name__ == "__main__":
    my_flow()
```

Next, we'll include a failure hook as well. It's worth noting that you can supply both `on_completion` and `on_failure` hooks to a flow or task. Only the hooks that are relevant to the final state of the flow or task will be called.

```python
from prefect import task, flow

def my_task_completion_hook(task, task_run, state):
    print("Our task completed successfully!")

def my_task_failure_hook(task, task_run, state):
    print("Our task failed :(")

@task(on_completion=[my_task_completion_hook], on_failure=[my_task_failure_hook])
def my_task():
    raise Exception("Oh no!")

@flow
def my_flow():
    my_task.submit()

if __name__ == "__main__":
    my_flow()
```

### Enhancements
- Update `quote` handling in input resolution to skip descending into the quoted expression — https://github.com/PrefectHQ/prefect/pull/8576
- Add light and dark mode color and contrast enhancements to UI — https://github.com/PrefectHQ/prefect/pull/8629

### Fixes
- Fix `Task.map` type hint for type-checker compatibility with async tasks — https://github.com/PrefectHQ/prefect/pull/8607
- Update Docker container name sanitization to handle "ce" and "ee" when checking Docker version — https://github.com/PrefectHQ/prefect/pull/8588
- Fix Kubernetes Job watch timeout behavior when streaming logs — https://github.com/PrefectHQ/prefect/pull/8618
- Fix date range filter selection on the flow runs UI page — https://github.com/PrefectHQ/prefect/pull/8616
- Fix Kubernetes not streaming logs when using multiple containers in Job — https://github.com/PrefectHQ/prefect/pull/8430

### Experimental
- Update worker variable typing for clearer display in the UI — https://github.com/PrefectHQ/prefect/pull/8613
- Update `BaseWorker` to ignore flow runs with associated storage block — https://github.com/PrefectHQ/prefect/pull/8619
- Add experimental API for artifacts — https://github.com/PrefectHQ/prefect/pull/8404

### Documentation
- Add documentation for resuming a flow run via the UI — https://github.com/PrefectHQ/prefect/pull/8621
- Add [`prefect-sifflet`](https://siffletapp.github.io/prefect-sifflet/) to Collections catalog — https://github.com/PrefectHQ/prefect/pull/8599


### Contributors
- @jefflaporte made their first contribution in https://github.com/PrefectHQ/prefect/pull/8430
- @AzemaBaptiste made their first contribution in https://github.com/PrefectHQ/prefect/pull/8599
- @darrida

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.8.2...2.8.3

## Release 2.8.2

### Fixes
- Reenable plugin loading in `prefect` module init — https://github.com/PrefectHQ/prefect/pull/8569

### Documentation
- Fix logging format override example — https://github.com/PrefectHQ/prefect/pull/8565


### Experimental
- Add events client to `PrefectClient` — https://github.com/PrefectHQ/prefect/pull/8546


**All changes**: https://github.com/PrefectHQ/prefect/compare/2.8.1...2.8.2

## Release 2.8.1

### New names, same behavior

We knew we were onto something big when we [first announced Prefect Orion](https://www.prefect.io/guide/blog/announcing-prefect-orion/), our second-generation orchestration engine, but we didn't know just how big. Orion's foundational design principles of dynamism, developer experience, and observability have shaped the Prefect 2 codebase to such an extent that it's difficult to tell where Orion ends and other components begin. For example, it's been challenging to communicate clearly about the “Orion API” (the orchestration API), an “Orion Server” (a hosted instance of the API and UI), and individual components of that server. 

With this release, **we've removed references to "Orion" and replaced them with more explicit, conventional nomenclature throughout the codebase**. All changes are **fully backwards compatible** and will follow our standard deprecation cycle of six months. These changes clarify the function of various components, commands, variables, and more.

See the [deprecated section](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md#deprecated) for a full rundown of changes.

Note: Many settings have been renamed but your old settings will be respected. To automatically convert all of the settings in your current profile to the new names, run the `prefect config validate` command.


### Enhancements
- Add `MattermostWebhook` notification block — https://github.com/PrefectHQ/prefect/pull/8341
- Add ability to pass in RRule string to `--rrule` option in `prefect set-schedule` command - https://github.com/PrefectHQ/prefect/pull/8543

### Fixes
- Fix default deployment parameters not populating in the UI — https://github.com/PrefectHQ/prefect/pull/8518
- Fix ability to use anchor date when setting an interval schedule with the `prefect set-schedule` command — https://github.com/PrefectHQ/prefect/pull/8524

### Documentation
- Add table listing available blocks — https://github.com/PrefectHQ/prefect/pull/8443
- Fix work pools documentation links — https://github.com/PrefectHQ/prefect/pull/8477
- Add examples for custom automation triggers — https://github.com/PrefectHQ/prefect/pull/8476
- Add webhooks to Automations  docs — https://github.com/PrefectHQ/prefect/pull/8514
- Document Prefect Cloud API rate limits — https://github.com/PrefectHQ/prefect/pull/8529

### Experimental
- Add metadata fields to `BaseWorker` — https://github.com/PrefectHQ/prefect/pull/8527
- Add default artifact metadata to `LiteralResults` and `PersistedResults` — https://github.com/PrefectHQ/prefect/pull/8501

### Deprecated
- Default SQLite database name changed from `orion.db` to `prefect.db`
- Logger `prefect.orion` renamed to `prefect.server`
- Constant `ORION_API_VERSION` renamed to `SERVER_API_VERSION`
- Kubernetes deployment template application name changed from `prefect-orion` to `prefect-server`
- Command `prefect kubernetes manifest orion` renamed to `prefect kubernetes manifest server`
- Log config handler `orion` renamed to `api`
- Class `OrionLogWorker` renamed to `APILogWorker`
- Class `OrionHandler` renamed to `APILogHandler`
- Directory `orion-ui` renamed to `ui`
- Class `OrionRouter` renamed to `PrefectRouter`
- Class `OrionAPIRoute` renamed to `PrefectAPIRoute`
- Class `OrionDBInterface` renamed to `PrefectDBInterface`
- Class `OrionClient` renamed to `PrefectClient`
- Module `prefect.client.orion` renamed to `prefect.client.orchestration`
- Command group `prefect orion` renamed to `prefect server`
- Module `prefect.orion` renamed to `prefect.server`
- The following settings have been renamed:
    - `PREFECT_LOGGING_ORION_ENABLED` → `PREFECT_LOGGING_TO_API_ENABLED`
    - `PREFECT_LOGGING_ORION_BATCH_INTERVAL` → `PREFECT_LOGGING_TO_API_BATCH_INTERVAL`
    - `PREFECT_LOGGING_ORION_BATCH_SIZE` → `PREFECT_LOGGING_TO_API_BATCH_SIZE`
    - `PREFECT_LOGGING_ORION_MAX_LOG_SIZE` → `PREFECT_LOGGING_TO_API_MAX_LOG_SIZE`
    - `PREFECT_LOGGING_ORION_WHEN_MISSING_FLOW` → `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW`
    - `PREFECT_ORION_BLOCKS_REGISTER_ON_START` → `PREFECT_API_BLOCKS_REGISTER_ON_START`
    - `PREFECT_ORION_DATABASE_CONNECTION_URL` → `PREFECT_API_DATABASE_CONNECTION_URL`
    - `PREFECT_ORION_DATABASE_MIGRATE_ON_START` → `PREFECT_API_DATABASE_MIGRATE_ON_START`
    - `PREFECT_ORION_DATABASE_TIMEOUT` → `PREFECT_API_DATABASE_TIMEOUT`
    - `PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT` → `PREFECT_API_DATABASE_CONNECTION_TIMEOUT`
    - `PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS` → `PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS`
    - `PREFECT_ORION_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE` → `PREFECT_API_SERVICES_SCHEDULER_DEPLOYMENT_BATCH_SIZE`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS` → `PREFECT_API_SERVICES_SCHEDULER_MAX_RUNS`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MIN_RUNS` → `PREFECT_API_SERVICES_SCHEDULER_MIN_RUNS`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME` → `PREFECT_API_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME`
    - `PREFECT_ORION_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME` → `PREFECT_API_SERVICES_SCHEDULER_MIN_SCHEDULED_TIME`
    - `PREFECT_ORION_SERVICES_SCHEDULER_INSERT_BATCH_SIZE` → `PREFECT_API_SERVICES_SCHEDULER_INSERT_BATCH_SIZE`
    - `PREFECT_ORION_SERVICES_LATE_RUNS_LOOP_SECONDS` → `PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS`
    - `PREFECT_ORION_SERVICES_LATE_RUNS_AFTER_SECONDS` → `PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS`
    - `PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS` → `PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS`
    - `PREFECT_ORION_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS` → `PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS`
    - `PREFECT_ORION_API_DEFAULT_LIMIT` → `PREFECT_API_DEFAULT_LIMIT`
    - `PREFECT_ORION_API_HOST` → `PREFECT_SERVER_API_HOST`
    - `PREFECT_ORION_API_PORT` → `PREFECT_SERVER_API_PORT`
    - `PREFECT_ORION_API_KEEPALIVE_TIMEOUT` → `PREFECT_SERVER_API_KEEPALIVE_TIMEOUT`
    - `PREFECT_ORION_UI_ENABLED` → `PREFECT_UI_ENABLED`
    - `PREFECT_ORION_UI_API_URL` → `PREFECT_UI_API_URL`
    - `PREFECT_ORION_ANALYTICS_ENABLED` → `PREFECT_SERVER_ANALYTICS_ENABLED`
    - `PREFECT_ORION_SERVICES_SCHEDULER_ENABLED` → `PREFECT_API_SERVICES_SCHEDULER_ENABLED`
    - `PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED` → `PREFECT_API_SERVICES_LATE_RUNS_ENABLED`
    - `PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED` → `PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED`
    - `PREFECT_ORION_SERVICES_PAUSE_EXPIRATIONS_ENABLED` → `PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED`
    - `PREFECT_ORION_TASK_CACHE_KEY_MAX_LENGTH` → `PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH`
    - `PREFECT_ORION_SERVICES_CANCELLATION_CLEANUP_ENABLED` → `PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED`


### Contributors
- @qheuristics made their first contribution in https://github.com/PrefectHQ/prefect/pull/8478
- @KernelErr made their first contribution in https://github.com/PrefectHQ/prefect/pull/8485

## Release 2.8.0

### Prioritize flow runs with work pools 🏊

![Work pools allow you to organize and prioritize work](https://user-images.githubusercontent.com/12350579/217914094-e8064420-294b-4033-b12e-c0f58da521d5.png)

With this release, flow runs can now be prioritized among work queues via work pools! Work pools allow you to organize and prioritize work by grouping related work queues together. Within work pools, you can assign a priority to each queue, and flow runs scheduled on higher priority work queues will be run before flow runs scheduled on lower priority work queues. This allows agents to prioritize work that is more important or time-sensitive even if there is a large backlog of flow runs on other work queues in a given work pool.

All existing work queues will be assigned to a default work pool named `default-agent-pool`. Creating a new work pool can be done via the Work Pools page in the UI or via the CLI.

To create a new work pool named "my-pool" via the CLI:

```bash
prefect work-pool create "my-pool"
```

Each work pool starts out with a default queue. New queues can be added to a work pool via the UI or the CLI.

To create a new work queue in a work pool via the CLI:

```bash
prefect work-queue create "high-priority" --pool "my-pool"
```

Deployments can now be assigned to a work queue in a specific work pool. Use the `--pool` flag to specify the work pool and the `--queue` flag to specify the work queue when building a deployment.

```bash
prefect deployment build \
    --pool my-pool \
    --queue high-priority \   
    --name high-priority \
    high_priority_flow.py:high_priority_flow
```

Once a deployment has been created and is scheduling flow runs on a work queue, you can start an agent to pick up those flow runs by starting an agent with the `--pool` flag.

```bash
prefect agent start --pool my-pool
```

Starting an agent with the `--pool` command allows the agent to pick up flow runs for the entire pool even as new queues are added to the pool. If you want to start an agent that only picks up flow runs for a specific queue, you can use the `--queue` flag.

```bash
prefect agent start --pool my-pool --queue high-priority
```

To learn more about work pools, check out the [docs](https://docs.prefect.io/concepts/work-pools/) or see the relevant pull requests:

### Enhancements
- Add ability to filter on work pool and queue when querying flow runs — https://github.com/PrefectHQ/prefect/pull/8459
- Ensure agent respects work queue priority — https://github.com/PrefectHQ/prefect/pull/8458
- Add ability to create a flow run from the UI with parameters from a previous run — https://github.com/PrefectHQ/prefect/pull/8405
- Add generic `Webhook` block — https://github.com/PrefectHQ/prefect/pull/8401
- Add override customizations functionality to deployments via CLI — https://github.com/PrefectHQ/prefect/pull/8349
- Add ability to reset concurrency limits in CLI to purge existing runs from taking concurrency slots — https://github.com/PrefectHQ/prefect/pull/8408
- Ensure matching flow run state information in UI — https://github.com/PrefectHQ/prefect/pull/8441
- Customize CLI block registration experience based on `PREFECT_UI_URL` — https://github.com/PrefectHQ/prefect/pull/8438

### Fixes
- Fix `prefect dev start` command — https://github.com/PrefectHQ/prefect/pull/8176
- Fix display of long log messages when in the UI — https://github.com/PrefectHQ/prefect/pull/8449
- Update `get_run_logger` to accomodate returning `logging.LoggerAdapter` — https://github.com/PrefectHQ/prefect/pull/8422
- Restore Prefect wrapper around HTTP errors for nicer error messages — https://github.com/PrefectHQ/prefect/pull/8391
- Fix display of work pool flow run filter in the UI — https://github.com/PrefectHQ/prefect/pull/8453

### Documentation
- Update Infrastructure concept documentation with `extra-pip-package` example and updated `deployment.yaml` — https://github.com/PrefectHQ/prefect/pull/8465
- Add work pools documentation - https://github.com/PrefectHQ/prefect/pull/8377

### Contributors
- @carderne

## Release 2.7.12

### Custom flow and task run names 🎉

Both tasks and flows now expose a mechanism for customizing the names of runs! This new keyword argument (`flow_run_name` for flows, `task_run_name` for tasks) accepts a string that will be used to create a run name for each run of the function. The most basic usage is as follows:

```python
from datetime import datetime
from prefect import flow, task

@task(task_run_name="custom-static-name")
def my_task(name):
  print(f"hi {name}")

@flow(flow_run_name="custom-but-fixed-name")
def my_flow(name: str, date: datetime):
  return my_task(name)

my_flow()
```

This is great, but doesn’t help distinguish between multiple runs of the same task or flow. In order to make these names dynamic, you can template them using the parameter names of the task or flow function, using all of the basic rules of Python string formatting as follows:

```python
from datetime import datetime
from prefect import flow, task

@task(task_run_name="{name}")
def my_task(name):
  print(f"hi {name}")

@flow(flow_run_name="{name}-on-{date:%A}")
def my_flow(name: str, date: datetime):
  return my_task(name)

my_flow()
```

See [the docs](https://docs.prefect.io/tutorials/flow-task-config/#basic-flow-configuration) or https://github.com/PrefectHQ/prefect/pull/8378 for more details.

### Enhancements
- Update the deployment page to show the runs tab before the description — https://github.com/PrefectHQ/prefect/pull/8398

### Fixes
- Fix artifact migration to only include states that have non-null data — https://github.com/PrefectHQ/prefect/pull/8420
- Fix error when using `prefect work-queue ls` without enabling work pools — https://github.com/PrefectHQ/prefect/pull/8427

### Experimental
- Add error when attempting to apply a deployment to a work pool that hasn't been created yet — https://github.com/PrefectHQ/prefect/pull/8413
- Create queues in the correct work pool when applying a deployment for a queue that hasn't been created yet — https://github.com/PrefectHQ/prefect/pull/8413

### Contributors
- @NodeJSmith

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.11...2.7.12



## Release 2.7.11

### Using loggers outside of flows

Prefect now defaults to displaying a warning instead of raising an error when you attempt to use Prefect loggers outside of flow or task runs. We've also added a setting `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW` to allow configuration of this behavior to silence the warning or raise an error as before. This means that you can attach Prefect's logging handler to existing loggers without breaking your workflows.

```python
from prefect import flow
import logging

my_logger = logging.getLogger("my-logger")
my_logger.info("outside the flow")

@flow
def foo():
    my_logger.info("inside the flow")

if __name__ == "__main__":
    foo()
```

We want to see messages from `my-logger` in the UI. We can do this with `PREFECT_LOGGING_EXTRA_LOGGERS`.

```
$ PREFECT_LOGGING_EXTRA_LOGGERS="my-logger" python example.py
example.py:6: UserWarning: Logger 'my-logger' attempted to send logs to Orion without a flow run id. The Orion log handler can only send logs within flow run contexts unless the flow run id is manually provided.
  my_logger.info("outside the flow")
18:09:30.518 | INFO    | my-logger - outside the flow
18:09:31.028 | INFO    | prefect.engine - Created flow run 'elated-curassow' for flow 'foo'
18:09:31.104 | INFO    | my-logger - inside the flow
18:09:31.179 | INFO    | Flow run 'elated-curassow' - Finished in state Completed()
```

Notice, we got a warning. This helps avoid confusion when certain logs don't appear in the UI, but if you understand that you can turn it off:

```
$ prefect config set PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW=ignore
Set 'PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW' to 'ignore'.
Updated profile 'default'.
```

### Enhancements
- Update default task run name to exclude hash of task key — https://github.com/PrefectHQ/prefect/pull/8292
- Update Docker images to update preinstalled packages on build — https://github.com/PrefectHQ/prefect/pull/8288
- Add PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW to allow loggers to be used outside of flows — https://github.com/PrefectHQ/prefect/pull/8311
- Display Runs before Deployments on flow pages - https://github.com/PrefectHQ/prefect/pull/8386
- Clearify output CLI message when switching profiles - https://github.com/PrefectHQ/prefect/pull/8383

### Fixes
- Fix bug preventing agents from properly updating Cancelling runs to a Cancelled state — https://github.com/PrefectHQ/prefect/pull/8315
- Fix bug where Kubernetes job monitoring exited early when no timeout was given — https://github.com/PrefectHQ/prefect/pull/8350

### Experimental
- We're working on work pools, groups of work queues. Together, work pools & queues give you greater flexibility and control in organizing and prioritizing work.
     - Add updates to work queue `last_polled` time when polling work pools — https://github.com/PrefectHQ/prefect/pull/8338
     - Add CLI support for work pools — https://github.com/PrefectHQ/prefect/pull/8259
     - Add fields to `work_queue` table to accommodate work pools — https://github.com/PrefectHQ/prefect/pull/8264
     - Add work queue data migration — https://github.com/PrefectHQ/prefect/pull/8327
     - Fix default value for priority on `WorkQueue` core schema — https://github.com/PrefectHQ/prefect/pull/8373
- Add ability to exclude experimental fields in API calls — https://github.com/PrefectHQ/prefect/pull/8274, https://github.com/PrefectHQ/prefect/pull/8331
- Add Prefect Cloud Events schema and clients — https://github.com/PrefectHQ/prefect/pull/8357

### Documentation
- Add git commands to Prefect Recipes contribution page — https://github.com/PrefectHQ/prefect/pull/8283
- Add `retry_delay_seconds` and `exponential_backoff` examples to Tasks retries documentation — https://github.com/PrefectHQ/prefect/pull/8280
- Add role permissions regarding block secrets — https://github.com/PrefectHQ/prefect/pull/8309
- Add getting started tutorial video to Prefect Cloud Quickstart — https://github.com/PrefectHQ/prefect/pull/8336
- Add tips for re-registering blocks from Prefect Collections — https://github.com/PrefectHQ/prefect/pull/8333
- Improve examples for Kubernetes infrastructure overrides — https://github.com/PrefectHQ/prefect/pull/8312
- Add mention of reverse proxy for `PREFECT_API_URL` config — https://github.com/PrefectHQ/prefect/pull/8240
- Fix unused Cloud Getting Started page — https://github.com/PrefectHQ/prefect/pull/8291
- Fix Prefect Cloud typo in FAQ — https://github.com/PrefectHQ/prefect/pull/8317

### Collections
- Add `ShellOperation` implementing `JobBlock` in `v0.1.4` release of `prefect-shell` - https://github.com/PrefectHQ/prefect-shell/pull/55
- Add `CensusSync` implementing `JobBlock` in `v0.1.1` release of `prefect-census` - https://github.com/PrefectHQ/prefect-census/pull/15

### Contributors
- @chiaberry
- @hozn
- @manic-miner
- @space-age-pete

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.10...2.7.11

## Release 2.7.10

### Flow run cancellation enhancements

We're excited to announce an upgrade to our flow run cancellation feature, resolving common issues.

We added SIGTERM handling to the flow run engine. When cancellation is requested, the agent sends a termination signal to the flow run infrastructure. Previously, this signal resulted in the immediate exit of the flow run. Now, the flow run will detect the signal and attempt to shut down gracefully. This gives the run an opportunity to clean up any resources it is managing. If the flow run does not gracefully exit in a reasonable time (this differs per infrastructure type), it will be killed.

We improved our handling of runs that are in the process of cancelling. When a run is cancelled, it's first placed in a "cancelling" state then moved to a "cancelled" state when cancellation is complete. Previously, concurrency slots were released as soon as cancellation was requested. Now, the flow run will continue to occupy concurrency slots until a "cancelled" state is reached.

We added cleanup of tasks and subflows belonging to cancelled flow runs. Previously, these tasks and subflows could be left in a "running" state. This can cause problems with concurrency slot consumption and restarts, so we've added a service that updates the states of the children of recently cancelled flow runs. 

See https://github.com/PrefectHQ/prefect/pull/8126 for implementation details.


### Multiarchitecture Docker builds

In 2.7.8, we announced that we were publishing development Docker images, including multiarchitecture images. This was the first step in the incremental rollout of multiarchitecture Docker images. We're excited to announce we will be publishing multiarchitecture Docker images starting with this release.

You can try one of the new images by including the `--platform` specifier, e.g.:

```bash
$ docker run --platform linux/arm64 --pull always prefecthq/prefect:2-latest prefect version
```

We will be publishing images for the following architectures:

- linux/amd64
- linux/arm64

This should provide a significant speedup to anyone running containers on ARM64 machines (I'm looking at you, Apple M1 chips!) and reduce the complexity for our users that are deploying on different platforms. The workflow for building our images was rewritten from scratch, and it'll be easy for us to expand support to include other common platforms.

Shoutout to [@ddelange](https://github.com/ddelange) who led implementation of the feature.
See https://github.com/PrefectHQ/prefect/pull/7902 for details.

### Enhancements
- Add [`is_schedule_active` option](https://docs.prefect.io/api-ref/prefect/deployments/#prefect.deployments.Deployment) to `Deployment` class to allow control of automatic scheduling — https://github.com/PrefectHQ/prefect/pull/7430

- Add documentation links to blocks in UI — https://github.com/PrefectHQ/prefect/pull/8210
- Add Kubernetes kube-system permissions to Prefect agent template for retrieving UUID from kube-system namespace — https://github.com/PrefectHQ/prefect/pull/8205
- Add support for obscuring secrets in nested block fields in the UI — https://github.com/PrefectHQ/prefect/pull/8246
- Enable publish of multiarchitecture Docker builds on release — https://github.com/PrefectHQ/prefect/pull/7902
- Add `CANCELLING` state type — https://github.com/PrefectHQ/prefect/pull/7794
- Add graceful shutdown of engine on `SIGTERM` — https://github.com/PrefectHQ/prefect/pull/7887
- Add cancellation cleanup service — https://github.com/PrefectHQ/prefect/pull/8093
- Add `PREFECT_ORION_API_KEEPALIVE_TIMEOUT` setting to allow configuration of Uvicorn `timeout-keep-alive` setting - https://github.com/PrefectHQ/prefect/pull/8190

### Fixes
- Fix server compatibility with clients on 2.7.8 - https://github.com/PrefectHQ/prefect/pull/8272
- Fix tracking of long-running Kubernetes jobs and add handling for connection failures - https://github.com/PrefectHQ/prefect/pull/8189

### Experimental
- Add functionality to specify a work pool when starting an agent — https://github.com/PrefectHQ/prefect/pull/8222
- Disable `Work Queues` tab view when work pools are enabled — https://github.com/PrefectHQ/prefect/pull/8257
- Fix property for `WorkersTable` in UI — https://github.com/PrefectHQ/prefect/pull/8232

### Documentation
- [Add Prefect Cloud Quickstart tutorial](https://docs.prefect.io/ui/cloud-getting-started/) — https://github.com/PrefectHQ/prefect/pull/8227
- Add `project_urls` to `setup.py` — https://github.com/PrefectHQ/prefect/pull/8224
- Add configuration to `mkdocs.yml` to enable versioning at a future time - https://github.com/PrefectHQ/prefect/pull/8204
- Improve [contributing documentation](https://docs.prefect.io/contributing/overview/) with venv instructions — https://github.com/PrefectHQ/prefect/pull/8247
- Update documentation on [KubernetesJob options](https://docs.prefect.io/concepts/infrastructure/#kubernetesjob) — https://github.com/PrefectHQ/prefect/pull/8261
- Update documentation on [workspace-level roles](https://docs.prefect.io/ui/roles/#workspace-level-roles) — https://github.com/PrefectHQ/prefect/pull/8263

### Collections
- Add [prefect-openai](https://prefecthq.github.io/prefect-openai/) to [Collections catalog](https://docs.prefect.io/collections/catalog/) — https://github.com/PrefectHQ/prefect/pull/8236

### Contributors
- @ddelange
- @imsurat
- @Laerte

## Release 2.7.9

### Enhancements
- Add `--head` flag to `flow-run logs` CLI command to limit the number of logs returned — https://github.com/PrefectHQ/prefect/pull/8003
- Add `--num_logs` option to `flow-run logs` CLI command to specify the number of logs returned — https://github.com/PrefectHQ/prefect/pull/8003
- Add option to filter out `.git` files when reading files with the GitHub storage block — https://github.com/PrefectHQ/prefect/pull/8193

### Fixes
- Fix bug causing failures when spawning Windows subprocesses - https://github.com/PrefectHQ/prefect/pull/8184
- Fix possible recursive loop when blocks label themselves as both their own parent and reference — https://github.com/PrefectHQ/prefect/pull/8197

### Documentation
- Add [recipe contribution page](https://docs.prefect.io/recipes/recipes/#contributing-recipes) and [AWS Chalice](https://docs.prefect.io/recipes/recipes/#recipe-catalog) recipe — https://github.com/PrefectHQ/prefect/pull/8183
- Add new `discourse` and `blog` admonition types — https://github.com/PrefectHQ/prefect/pull/8202
- Update Automations and Notifications documentation — https://github.com/PrefectHQ/prefect/pull/8140
- Fix minor API docstring formatting issues — https://github.com/PrefectHQ/prefect/pull/8196

### Collections
- [`prefect-openai` 0.1.0](https://github.com/PrefectHQ/prefect-openai) newly released with support for authentication and completions

### Experimental
- Add ability for deployment create and deployment update to create work pool queues — https://github.com/PrefectHQ/prefect/pull/8129

## New Contributors
* @mj0nez made their first contribution in https://github.com/PrefectHQ/prefect/pull/8201

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.8...2.7.9

## Release 2.7.8

### Flow run timeline view

We're excited to announce that a new timeline graph has been added to the flow run page. 
This view helps visualize how execution of your flow run takes place in time, an alternative to the radar view that focuses on the structure of dependencies between task runs.

This feature is currently in beta and we have lots of improvements planned in the near future! We're looking forward to your feedback.

![The timeline view visualizes execution of your flow run over time](https://user-images.githubusercontent.com/6200442/212138540-78586356-89bc-4401-a700-b80b15a17020.png)

### Enhancements
- Add [task option `refresh_cache`](https://docs.prefect.io/concepts/tasks/#refreshing-the-cache) to update the cached data for a task run — https://github.com/PrefectHQ/prefect/pull/7856
- Add logs when a task run receives an abort signal and is in a non-final state — https://github.com/PrefectHQ/prefect/pull/8097
- Add [publishing of multiarchitecture Docker images](https://hub.docker.com/r/prefecthq/prefect-dev) for development builds  — https://github.com/PrefectHQ/prefect/pull/7900
- Add `httpx.WriteError` to client retryable exceptions — https://github.com/PrefectHQ/prefect/pull/8145
- Add support for memory limits and privileged containers to `DockerContainer` — https://github.com/PrefectHQ/prefect/pull/8033

### Fixes
- Add support for `allow_failure` to mapped task arguments — https://github.com/PrefectHQ/prefect/pull/8135
- Update conda requirement regex to support channel and build hashes — https://github.com/PrefectHQ/prefect/pull/8137
- Add numpy array support to orjson serialization — https://github.com/PrefectHQ/prefect/pull/7912

### Experimental
- Rename "Worker pools" to "Work pools" — https://github.com/PrefectHQ/prefect/pull/8107
- Rename default work pool queue — https://github.com/PrefectHQ/prefect/pull/8117
- Add worker configuration — https://github.com/PrefectHQ/prefect/pull/8100
- Add `BaseWorker` and `ProcessWorker` — https://github.com/PrefectHQ/prefect/pull/7996

### Documentation
- Add YouTube video to welcome page - https://github.com/PrefectHQ/prefect/pull/8090
- Add social links - https://github.com/PrefectHQ/prefect/pull/8088
- Increase visibility of Prefect Cloud and Orion REST API documentation - https://github.com/PrefectHQ/prefect/pull/8134

## New Contributors
* @muddi900 made their first contribution in https://github.com/PrefectHQ/prefect/pull/8101
* @ddelange made their first contribution in https://github.com/PrefectHQ/prefect/pull/7900
* @toro-berlin made their first contribution in https://github.com/PrefectHQ/prefect/pull/7856
* @Ewande made their first contribution in https://github.com/PrefectHQ/prefect/pull/7912
* @brandonreid made their first contribution in https://github.com/PrefectHQ/prefect/pull/8153

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.7...2.7.8

## Release 2.7.7

### Improved reference documentation

The API reference documentation has been completely rehauled with improved navigation and samples.

The best place to view the REST API documentation is on [Prefect Cloud](https://app.prefect.cloud/api/docs).

<img width="1659" alt="Cloud API Reference Documentation" src="https://user-images.githubusercontent.com/2586601/211107172-cbded5a4-e50c-452f-8525-e36b5988f82e.png">

Note: you can also view the REST API documentation [embedded in our open source documentation](https://docs.prefect.io/api-ref/rest-api-reference/).

We've also improved the parsing and rendering of reference documentation for our Python API. See the [@flow decorator reference](https://docs.prefect.io/api-ref/prefect/flows/#prefect.flows.flow) for example.

### Enhancements
- Add link to blocks catalog after registering blocks in CLI — https://github.com/PrefectHQ/prefect/pull/8017
- Add schema migration of block documents during `Block.save` — https://github.com/PrefectHQ/prefect/pull/8056
- Update result factory creation to avoid creating an extra client instance — https://github.com/PrefectHQ/prefect/pull/8072
- Add logs for deployment flow code loading — https://github.com/PrefectHQ/prefect/pull/8075
- Update `visit_collection` to support annotations e.g. `allow_failure` — https://github.com/PrefectHQ/prefect/pull/7263
- Update annotations to inherit from `namedtuple` for serialization support in Dask — https://github.com/PrefectHQ/prefect/pull/8037
- Add `PREFECT_API_TLS_INSECURE_SKIP_VERIFY` setting to disable client SSL verification — https://github.com/PrefectHQ/prefect/pull/7850
- Update OpenAPI schema for flow parameters to include positions for display — https://github.com/PrefectHQ/prefect/pull/8013
- Add parsing of flow docstrings to populate parameter descriptions in the OpenAPI schema — https://github.com/PrefectHQ/prefect/pull/8004
- Add `validate` to `Block.load` allowing validation to be disabled — https://github.com/PrefectHQ/prefect/pull/7862
- Improve error message when saving a block with an invalid name — https://github.com/PrefectHQ/prefect/pull/8038
- Add limit to task run cache key size — https://github.com/PrefectHQ/prefect/pull/7275
- Add limit to RRule length — https://github.com/PrefectHQ/prefect/pull/7762
- Add flow run history inside the date range picker - https://github.com/PrefectHQ/orion-design/issues/994

### Fixes
- Fix bug where flow timeouts started before waiting for upstreams — https://github.com/PrefectHQ/prefect/pull/7993
- Fix captured Kubernetes error type in `get_job` — https://github.com/PrefectHQ/prefect/pull/8018
- Fix `prefect cloud login` error when no workspaces exist — https://github.com/PrefectHQ/prefect/pull/8034
- Fix serialization of `SecretDict` when used in deployments — https://github.com/PrefectHQ/prefect/pull/8074
- Fix bug where `visit_collection` could fail when accessing extra Pydantic fields — https://github.com/PrefectHQ/prefect/pull/8083

### Experimental
- Add pages and routers for workers — https://github.com/PrefectHQ/prefect/pull/7973

### Documentation
- Update API reference documentation to use new parser and renderer — https://github.com/PrefectHQ/prefect/pull/7855
- Add new REST API reference using Redoc — https://github.com/PrefectHQ/prefect/pull/7503

### Collections
- [`prefect-aws` 0.2.2](https://github.com/PrefectHQ/prefect-aws/releases/tag/v0.2.2) released with many improvements to `S3Bucket`

### Contributors
* @j-tr made their first contribution in https://github.com/PrefectHQ/prefect/pull/8013
* @toby-coleman made their first contribution in https://github.com/PrefectHQ/prefect/pull/8083
* @riquelmev made their first contribution in https://github.com/PrefectHQ/prefect/pull/7768
* @joelluijmes


**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.5...2.7.7


## Release 2.7.6

This release fixes a critical bug in the SQLite database migrations in 2.7.4 and 2.7.5.

See https://github.com/PrefectHQ/prefect/issues/8058 for details.

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.5...2.7.6

## Release 2.7.5

### Schedule flow runs and read logs from the CLI

You can now specify either `--start-in` or `--start-at` when running deployments from the CLI.
```
❯ prefect deployment run foo/test --start-at "3pm tomorrow"
Creating flow run for deployment 'foo/test'...
Created flow run 'pompous-porpoise'.
└── UUID: 0ce7930e-8ec0-40cb-8a0e-65bccb7a9605
└── Parameters: {}
└── Scheduled start time: 2022-12-06 15:00:00
└── URL: <no dashboard available>
```

You can also get the logs for a flow run using `prefect flow-run logs <flow run UUID>`
```
❯ prefect flow-run logs 7aec7a60-a0ab-4f3e-9f2a-479cd85a2aaf 
2022-12-29 20:00:40.651 | INFO    | Flow run 'optimal-pegasus' - meow
2022-12-29 20:00:40.652 | INFO    | Flow run 'optimal-pegasus' - that food in my bowl is gross
2022-12-29 20:00:40.652 | WARNING | Flow run 'optimal-pegasus' - seriously, it needs to be replaced ASAP
2022-12-29 20:00:40.662 | INFO    | Flow run 'optimal-pegasus' - Finished in state Completed()
```

### Enhancements
- Add `--start-in` and `--start-at` to `prefect deployment run` — https://github.com/PrefectHQ/prefect/pull/7772
- Add `flow-run logs` to get logs using the CLI — https://github.com/PrefectHQ/prefect/pull/7982

### Documentation
- Fix task annotation in task runner docs — https://github.com/PrefectHQ/prefect/pull/7977
- Add instructions for building custom blocks — https://github.com/PrefectHQ/prefect/pull/7979

### Collections
- Added `BigQueryWarehouse` block in `prefect-gcp` v0.2.1
- Added `AirbyteConnection` block in `prefect-airbyte` v0.2.0
- Added dbt Cloud metadata API client to `DbtCloudCredentials` in `prefect-dbt` v0.2.7

### Experimental 
- Fix read worker pool queue endpoint — https://github.com/PrefectHQ/prefect/pull/7995
- Fix error in worker pool queue endpoint — https://github.com/PrefectHQ/prefect/pull/7997
- Add filtering to flow runs by worker pool and worker pool queue attributes — https://github.com/PrefectHQ/prefect/pull/8006

### Contributors
* @ohadch made their first contribution in https://github.com/PrefectHQ/prefect/pull/7982
* @mohitsaxenaknoldus made their first contribution in https://github.com/PrefectHQ/prefect/pull/7980

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.4...2.7.5


## Release 2.7.4

### Improvements to retry delays: multiple delays, exponential backoff, and jitter

When configuring task retries, you can now configure a delay for each retry! The `retry_delay_seconds` option accepts a list of delays for custom retry behavior. For example, the following task will wait for successively increasing intervals before the next attempt starts:

```python
from prefect import task, flow
import random

@task(retries=3, retry_delay_seconds=[1, 10, 100])
def flaky_function():
    if random.choice([True, False]):
        raise RuntimeError("not this time!")
    return 42
```

Additionally, you can pass a callable that accepts the number of retries as an argument and returns a list. Prefect includes an `exponential_backoff` utility that will automatically generate a list of retry delays that correspond to an exponential backoff retry strategy. The following flow will wait for 10, 20, then 40 seconds before each retry.

```python
from prefect import task, flow
from prefect.tasks import exponential_backoff
import random

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=10))
def flaky_function():
    if random.choice([True, False]):
        raise RuntimeError("not this time!")
    return 42
```

Many users that configure exponential backoff also wish to jitter the delay times to prevent "thundering herd" scenarios, where many tasks all retry at exactly the same time, causing cascading failures. The `retry_jitter_factor` option can be used to add variance to the base delay. For example, a retry delay of `10` seconds with a `retry_jitter_factor` of `0.5` will be allowed to delay up to `15` seconds. Large values of `retry_jitter_factor` provide more protection against "thundering herds", while keeping the average retry delay time constant. For example, the following task adds jitter to its exponential backoff so the retry delays will vary up to a maximum delay time of 20, 40, and 80 seconds respectively.

```python
from prefect import task, flow
from prefect.tasks import exponential_backoff
import random

@task(
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=10),
    retry_jitter_factor=1,
)
def flaky_function():
    if random.choice([True, False]):
        raise RuntimeError("not this time!")
    return 42
```

See https://github.com/PrefectHQ/prefect/pull/7961 for implementation details.

### Enhancements
- Add task run names to the `/graph`  API route — https://github.com/PrefectHQ/prefect/pull/7951
- Add vcs directories `.git` and `.hg` (mercurial) to default `.prefectignore` — https://github.com/PrefectHQ/prefect/pull/7919
- Increase the default thread limit from 40 to 250 — https://github.com/PrefectHQ/prefect/pull/7961

### Deprecations
- Add removal date to tag-based work queue deprecation messages — https://github.com/PrefectHQ/prefect/pull/7930

### Documentation
- Fix `prefect deployment` command listing — https://github.com/PrefectHQ/prefect/pull/7949
- Add workspace transfer documentation — https://github.com/PrefectHQ/prefect/pull/7941
- Fix docstring examples in `PrefectFuture` — https://github.com/PrefectHQ/prefect/pull/7877
- Update `setup.py` metadata to link to correct repo — https://github.com/PrefectHQ/prefect/pull/7933

### Experimental
- Add experimental workers API routes — https://github.com/PrefectHQ/prefect/pull/7896

### Collections
- New [`prefect-google-sheets` collection](https://stefanocascavilla.github.io/prefect-google-sheets/)

### Contributors
* @devanshdoshi9 made their first contribution in https://github.com/PrefectHQ/prefect/pull/7949
* @stefanocascavilla made their first contribution in https://github.com/PrefectHQ/prefect/pull/7960
* @quassy made their first contribution in https://github.com/PrefectHQ/prefect/pull/7919

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.3...2.7.4

## Release 2.7.3

### Fixes
- Fix bug where flows with names that do not match the function name could not be loaded — https://github.com/PrefectHQ/prefect/pull/7920
- Fix type annotation for `KubernetesJob.job_watch_timeout_seconds` — https://github.com/PrefectHQ/prefect/pull/7914
- Keep data from being lost when assigning a generator to `State.data` — https://github.com/PrefectHQ/prefect/pull/7714

## Release 2.7.2

### Rescheduling paused flow runs

When pausing a flow run, you can ask that Prefect reschedule the run for you instead of blocking until resume. This allows infrastructure to tear down, saving costs if the flow run is going to be pasued for significant amount of time.

You can request that a flow run be rescheduled by setting the `reschedule` option when calling `pause_flow_run`.

```python
from prefect import task, flow, pause_flow_run

@task(persist_result=True)
async def marvin_setup():
    return "a raft of ducks walk into a bar..."

@task(persist_result=True)
async def marvin_punchline():
    return "it's a wonder none of them ducked!"

@flow(persist_result=True)
async def inspiring_joke():
    await marvin_setup()
    await pause_flow_run(timeout=600, reschedule=True)  # pauses for 10 minutes
    await marvin_punchline()
```

If set up as a deployment, running this flow will set up a joke, then pause and leave execution until it is resumed. Once resumed either with the `resume_flow_run` utility or the Prefect UI, the flow will be rescheduled and deliver the punchline.

In order to use this feature pauses, the flow run must be associated with a deployment and results must be enabled.

Read the [pause documentation](https://docs.prefect.io/concepts/flows/#pause-a-flow-run) or see the [pull request](https://github.com/PrefectHQ/prefect/pull/7738) for details.

### Pausing flow runs from the outside

Flow runs from deployments can now be paused outside of the flow itself!

The UI features a **Pause** button for flow runs that will stop execution at the beginning of the _next_ task that runs. Any currently running tasks will be allowed to complete. Resuming this flow will schedule it to start again.

You can also pause a flow run from code: the `pause_flow_run` utility now accepts an optional `flow_run_id` argument. For example, you can pause a flow run from another flow run!

Read the [pause documentation](https://docs.prefect.io/concepts/flows/#pause-a-flow-run) or see the [pull request](https://github.com/PrefectHQ/prefect/pull/7863) for details.

### Pages for individual task run concurrency limits

When viewing task run concurrency in the UI, each limit has its own page. Included in the details for each limit is the tasks that are actively part of that limit.

<img width="1245" alt="image" src="https://user-images.githubusercontent.com/6200442/207954852-60e7a185-0f9d-4a3d-b9f7-2b393ef12726.png">


### Enhancements
- Improve Prefect import time by deferring imports — https://github.com/PrefectHQ/prefect/pull/7836
- Add Opsgenie notification block — https://github.com/PrefectHQ/prefect/pull/7778
- Add individual concurrency limit page with active runs list — https://github.com/PrefectHQ/prefect/pull/7848
- Add `PREFECT_KUBERNETES_CLUSTER_UID` to allow bypass of `kube-system` namespace read — https://github.com/PrefectHQ/prefect/pull/7864
- Refactor `pause_flow_run` for consistency with engine state handling — https://github.com/PrefectHQ/prefect/pull/7857
- API: Allow `reject_transition` to return current state — https://github.com/PrefectHQ/prefect/pull/7830
- Add `SecretDict` block field that obfuscates nested values in a dictionary — https://github.com/PrefectHQ/prefect/pull/7885

### Fixes
- Fix bug where agent concurrency slots may not be released — https://github.com/PrefectHQ/prefect/pull/7845
- Fix circular imports in the `orchestration` module — https://github.com/PrefectHQ/prefect/pull/7883
- Fix deployment builds with scripts that contain flow calls - https://github.com/PrefectHQ/prefect/pull/7817
- Fix path argument behavior in `LocalFileSystem` block - https://github.com/PrefectHQ/prefect/pull/7891
- Fix flow cancellation in `Process` block on Windows - https://github.com/PrefectHQ/prefect/pull/7799

### Documentation
- Add documentation for Automations UI — https://github.com/PrefectHQ/prefect/pull/7833
- Mention recipes and tutorials under Recipes and Collections pages — https://github.com/PrefectHQ/prefect/pull/7876
- Add documentation for Task Run Concurrency UI — https://github.com/PrefectHQ/prefect/pull/7840
- Add `with_options` example to collections usage docs — https://github.com/PrefectHQ/prefect/pull/7894
- Add a link to orion design and better title to UI readme — https://github.com/PrefectHQ/prefect/pull/7484

### Collections
- New [`prefect-kubernetes`](https://prefecthq.github.io/prefect-kubernetes/) collection for [Kubernetes](https://kubernetes.io/) — https://github.com/PrefectHQ/prefect/pull/7907
- New [`prefect-bitbucket`](https://prefecthq.github.io/prefect-bitbucket/) collection for [Bitbucket](https://bitbucket.org/product) — https://github.com/PrefectHQ/prefect/pull/7907

## Contributors
- @jlutran

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.7.1...2.7.2

## Release 2.7.1

### Task concurrency limits page
You can now add task concurrency limits in the ui!

![image](https://user-images.githubusercontent.com/6200442/206586749-3f9fff36-5359-41a9-8727-60523cf89071.png)

### Enhancements
- Add extra entrypoints setting for user module injection; allows registration of custom blocks — https://github.com/PrefectHQ/prefect/pull/7179
- Update orchestration rule to wait for scheduled time to only apply to transition to running — https://github.com/PrefectHQ/prefect/pull/7585
- Use cluster UID and namespace instead of cluster "name" for `KubernetesJob` identifiers — https://github.com/PrefectHQ/prefect/pull/7747
- Add a task run concurrency limits page — https://github.com/PrefectHQ/prefect/pull/7779
- Add setting to toggle interpreting square brackets as style — https://github.com/PrefectHQ/prefect/pull/7810
- Move `/health` API route to root router — https://github.com/PrefectHQ/prefect/pull/7765
- Add `PREFECT_API_ENABLE_HTTP2` setting to allow HTTP/2 to be disabled — https://github.com/PrefectHQ/prefect/pull/7802
- Monitor process after kill and return early when possible — https://github.com/PrefectHQ/prefect/pull/7746
- Update `KubernetesJob` to watch jobs without timeout by default — https://github.com/PrefectHQ/prefect/pull/7786
- Bulk deletion of flows, deployments, and work queues from the UI - https://github.com/PrefectHQ/prefect/pull/7824

### Fixes
- Add lock to ensure that alembic commands are not run concurrently — https://github.com/PrefectHQ/prefect/pull/7789
- Release task concurrency slots when transition is rejected as long as the task is not in a running state — https://github.com/PrefectHQ/prefect/pull/7798
- Fix issue with improperly parsed flow run notification URLs — https://github.com/PrefectHQ/prefect/pull/7173
- Fix radar not updating without refreshing the page - https://github.com/PrefectHQ/prefect/pull/7824
- UI: Fullscreen layouts on screens < `lg` should take up all the available space — https://github.com/PrefectHQ/prefect/pull/7792

### Documentation
- Add documentation for creating a flow run from deployments — https://github.com/PrefectHQ/prefect/pull/7696
- Move `wait_for` examples to the tasks documentation — https://github.com/PrefectHQ/prefect/pull/7788

## Contributors
* @t-yuki made their first contribution in https://github.com/PrefectHQ/prefect/pull/7741
* @padbk made their first contribution in https://github.com/PrefectHQ/prefect/pull/7173

## Release 2.7.0

### Flow run cancellation

We're excited to announce a new flow run cancellation feature!

Flow runs can be cancelled from the CLI, UI, REST API, or Python client. 

For example:

```
prefect flow-run cancel <flow-run-id>
```

When cancellation is requested, the flow run is moved to a "Cancelling" state. The agent monitors the state of flow runs and detects that cancellation has been requested. The agent then sends a signal to the flow run infrastructure, requesting termination of the run. If the run does not terminate after a grace period (default of 30 seconds), the infrastructure will be killed, ensuring the flow run exits.

Unlike the implementation of cancellation in Prefect 1 — which could fail if the flow run was stuck — this provides a strong guarantee of cancellation. 

Note: this process is robust to agent restarts, but does require that an agent is running to enforce cancellation.

Support for cancellation has been added to all core library infrastructure types:

- Docker Containers (https://github.com/PrefectHQ/prefect/pull/7684)
- Kubernetes Jobs (https://github.com/PrefectHQ/prefect/pull/7701)
- Processes (https://github.com/PrefectHQ/prefect/pull/7635)

Cancellation support is in progress for all collection infrastructure types:

- ECS Tasks (https://github.com/PrefectHQ/prefect-aws/pull/163)
- Google Cloud Run Jobs (https://github.com/PrefectHQ/prefect-gcp/pull/76)
- Azure Container Instances (https://github.com/PrefectHQ/prefect-azure/pull/58)

At this time, this feature requires the flow run to be submitted by an agent — flow runs without deployments cannot be cancelled yet, but that feature is [coming soon](https://github.com/PrefectHQ/prefect/pull/7150).

See https://github.com/PrefectHQ/prefect/pull/7637 for more details

### Flow run pause and resume

In addition to cancellations, flow runs can also be paused for manual approval!

```python
from prefect import flow, pause_flow_run


@flow
def my_flow():
    print("hi!")
    pause_flow_run()
    print("bye!")
```

A new `pause_flow_run` utility is provided — when called from within a flow, the flow run is moved to a "Paused" state and execution will block. Any tasks that have begun execution before pausing will finish. Infrastructure will keep running, polling to check whether the flow run has been resumed. Paused flow runs can be resumed with the `resume_flow_run` utility, or from the UI.

A timeout can be supplied to the `pause_flow_run` utility — if the flow run is not resumed within the specified timeout, the flow will fail.

This blocking style of pause that keeps infrastructure running is supported for all flow runs, including subflow runs.

See https://github.com/PrefectHQ/prefect/pull/7637 for more details.

### Logging of prints in flows and tasks

Flows or tasks can now opt-in to logging print statements. This is much like the `log_stdout` feature in Prefect 1, but we've improved the _scoping_ so you can enable or disable the feature at the flow or task level.

In the following example, the print statements will be redirected to the logger for the flow run and task run accordingly:

```python
from prefect import task, flow

@task
def my_task():
    print("world")

@flow(log_prints=True)
def my_flow():
    print("hello")
    my_task()
```

The output from these prints will appear in the UI!

This feature will also capture prints made in functions called by tasks or flows — as long as you're within the context of the run the prints will be logged.

If you have a sensitive task, it can opt-out even if the flow has enabled logging of prints:

```python
@task(log_prints=False)
def my_secret_task():
    print(":)")
```

This print statement will appear locally as normal, but won't be sent to the Prefect logger or API.

See [the logging documentation](https://docs.prefect.io/concepts/logs/#logging-print-statements) for more details.

See https://github.com/PrefectHQ/prefect/pull/7580 for implementation details.


### Agent flow run concurrency limits

Agents can now limit the number of concurrent flow runs they are managing.

For example, start an agent with:

```
prefect agent start -q default --limit 10
```

When the agent submits a flow run, it will track it in a local concurrency slot. If the agent is managing more than 10 flow runs, the agent will not accept any more work from its work queues. When the infrastructure for a flow run exits, the agent will release a concurrency slot and another flow run can be submitted.

This feature is especially useful for limiting resource consumption when running flows locally! It also provides a way to roughly balance load across multiple agents.

Thanks to @eudyptula for contributing!

See https://github.com/PrefectHQ/prefect/pull/7361 for more details.


### Enhancements
- Add agent reporting of crashed flow run infrastructure — https://github.com/PrefectHQ/prefect/pull/7670
- Add Twilio SMS notification block — https://github.com/PrefectHQ/prefect/pull/7685
- Add PagerDuty Webhook notification block — https://github.com/PrefectHQ/prefect/pull/7534
- Add jitter to the agent query loop — https://github.com/PrefectHQ/prefect/pull/7652
- Include final state logs in logs sent to API — https://github.com/PrefectHQ/prefect/pull/7647
- Add `tags` and `idempotency_key` to `run deployment` — https://github.com/PrefectHQ/prefect/pull/7641
- The final state of a flow is now `Cancelled` when any task finishes in a `Cancelled` state — https://github.com/PrefectHQ/prefect/pull/7694
- Update login to prompt for "API key" instead of "authentication key" — https://github.com/PrefectHQ/prefect/pull/7649
- Disable cache on result retrieval if disabled on creation — https://github.com/PrefectHQ/prefect/pull/7627
- Raise `CancelledRun` when retrieving a `Cancelled` state's result — https://github.com/PrefectHQ/prefect/pull/7699
- Use new database session to send each flow run notification — https://github.com/PrefectHQ/prefect/pull/7644
- Increase default agent query interval to 10s — https://github.com/PrefectHQ/prefect/pull/7703
- Add default messages to state exceptions — https://github.com/PrefectHQ/prefect/pull/7705
- Update `run_sync_in_interruptible_worker_thread` to use an event — https://github.com/PrefectHQ/prefect/pull/7704
- Increase default database query timeout to 10s — https://github.com/PrefectHQ/prefect/pull/7717

### Fixes
- Prompt workspace selection if API key is set, but API URL is not set — https://github.com/PrefectHQ/prefect/pull/7648
- Use `PREFECT_UI_URL` for flow run notifications — https://github.com/PrefectHQ/prefect/pull/7698
- Display all parameter values a flow run was triggered with in the UI (defaults and overrides) — https://github.com/PrefectHQ/prefect/pull/7697
- Fix bug where result event is missing when wait is called before submission completes — https://github.com/PrefectHQ/prefect/pull/7571
- Fix support for sync-compatible calls in `deployment build` — https://github.com/PrefectHQ/prefect/pull/7417
- Fix bug in `StateGroup` that caused `all_final` to be wrong — https://github.com/PrefectHQ/prefect/pull/7678
- Add retry on specified httpx network errors — https://github.com/PrefectHQ/prefect/pull/7593
- Fix state display bug when state message is empty — https://github.com/PrefectHQ/prefect/pull/7706

### Documentation
- Fix heading links in docs — https://github.com/PrefectHQ/prefect/pull/7665
- Update login and `PREFECT_API_URL` configuration notes — https://github.com/PrefectHQ/prefect/pull/7674
- Add documentation about AWS retries configuration — https://github.com/PrefectHQ/prefect/pull/7691
- Add GitLab storage block to deployment CLI docs — https://github.com/PrefectHQ/prefect/pull/7686
- Add links to Cloud Run and Container Instance infrastructure — https://github.com/PrefectHQ/prefect/pull/7690
- Update docs on final state determination to reflect `Cancelled` state changes — https://github.com/PrefectHQ/prefect/pull/7700
- Fix link in 'Agents and Work Queues' documentation — https://github.com/PrefectHQ/prefect/pull/7659

### Contributors
- @brian-pond made their first contribution in https://github.com/PrefectHQ/prefect/pull/7659
- @YtKC made their first contribution in https://github.com/PrefectHQ/prefect/pull/7641
- @eudyptula made their first contribution in https://github.com/PrefectHQ/prefect/pull/7361
- @hateyouinfinity
- @jmrobbins13

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.9...2.7.0

## Release 2.6.9

### Features

Logging into Prefect Cloud from the CLI has been given a serious upgrade!

<img width="748" alt="Login example" src="https://user-images.githubusercontent.com/2586601/199800241-c1b3691b-f18c-43ee-85e9-53cc3e5b1d48.png">

The `prefect cloud login` command now:

- Can be used non-interactively
- Can open the browser to generate a new API key for you
- Uses a new workspace selector
- Always uses your current profile
- Only prompts for workspace selection when you have more than one workspace

It also detects existing authentication:

- If logged in on the current profile, we will check that you want to reauthenticate
- If logged in on another profile, we will suggest a profile switch

There's also a new `prefect cloud logout` command (contributed by @hallenmaia) to remove credentials from the current profile.

### Enhancements
- Add automatic upper-casing of string log level settings — https://github.com/PrefectHQ/prefect/pull/7592
- Add `infrastructure_pid` to flow run — https://github.com/PrefectHQ/prefect/pull/7595
- Add `PrefectFormatter` to reduce logging configuration duplication — https://github.com/PrefectHQ/prefect/pull/7588
- Update `CloudClient.read_workspaces` to return a model — https://github.com/PrefectHQ/prefect/pull/7332
- Update hashing utilities to allow execution in FIPS 140-2 environments — https://github.com/PrefectHQ/prefect/pull/7620

### Fixes
- Update logging setup to support incremental configuration — https://github.com/PrefectHQ/prefect/pull/7569
- Update logging `JsonFormatter` to output valid JSON — https://github.com/PrefectHQ/prefect/pull/7567
- Remove `inter` CSS import, which blocked UI loads in air-gapped environments — https://github.com/PrefectHQ/prefect/pull/7586
- Return 404 when a flow run is missing during `set_task_run_state` — https://github.com/PrefectHQ/prefect/pull/7603
- Fix directory copy errors with `LocalFileSystem` deployments on Python 3.7 — https://github.com/PrefectHQ/prefect/pull/7441
- Add flush of task run logs when on remote workers — https://github.com/PrefectHQ/prefect/pull/7626

### Documentation
- Add docs about CPU and memory allocation on agent deploying ECS infrastructure blocks — https://github.com/PrefectHQ/prefect/pull/7597

### Contributors
- @hallenmaia 
- @szelenka

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.8...2.6.9

## Release 2.6.8

### Enhancements
- Add `--run-once` to `prefect agent start` CLI — https://github.com/PrefectHQ/prefect/pull/7505
- Expose `prefetch-seconds` in `prefect agent start` CLI — https://github.com/PrefectHQ/prefect/pull/7498
- Add start time sort for flow runs to the REST API — https://github.com/PrefectHQ/prefect/pull/7496
- Add `merge_existing_data` flag to `update_block_document` — https://github.com/PrefectHQ/prefect/pull/7470
- Add sanitization to enforce leading/trailing alphanumeric characters for Kubernetes job labels — https://github.com/PrefectHQ/prefect/pull/7528

### Fixes
- Fix type checking for flow name and version arguments — https://github.com/PrefectHQ/prefect/pull/7549
- Fix check for empty paths in `LocalFileSystem` — https://github.com/PrefectHQ/prefect/pull/7477
- Fix `PrefectConsoleHandler` bug where log tracebacks were excluded — https://github.com/PrefectHQ/prefect/pull/7558

### Documentation
- Add glow to Collection Catalog images in dark mode — https://github.com/PrefectHQ/prefect/pull/7535
- New [`prefect-vault`](https://github.com/pbchekin/prefect-vault) collection for integration with Hashicorp Vault

## Contributors
* @kielnino made their first contribution in https://github.com/PrefectHQ/prefect/pull/7517

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.7...2.6.8

## Release 2.6.7

### Enhancements
- Add timeout support to tasks — https://github.com/PrefectHQ/prefect/pull/7409
- Add colored log levels — https://github.com/PrefectHQ/prefect/pull/6101
- Update flow and task run page sidebar styling — https://github.com/PrefectHQ/prefect/pull/7426
- Add redirect to logs tab when navigating to parent or child flow runs — https://github.com/PrefectHQ/prefect/pull/7439
- Add `PREFECT_UI_URL` and `PREFECT_CLOUD_UI_URL` settings — https://github.com/PrefectHQ/prefect/pull/7411
- Improve scheduler performance — https://github.com/PrefectHQ/prefect/pull/7450 https://github.com/PrefectHQ/prefect/pull/7433
- Add link to parent flow from subflow details page — https://github.com/PrefectHQ/prefect/pull/7491
- Improve visibility of deployment tags in the deployments page — https://github.com/PrefectHQ/prefect/pull/7491
- Add deployment and flow metadata to infrastructure labels — https://github.com/PrefectHQ/prefect/pull/7479
- Add obfuscation of secret settings — https://github.com/PrefectHQ/prefect/pull/7465

### Fixes
- Fix missing import for `ObjectAlreadyExists` exception in deployments module — https://github.com/PrefectHQ/prefect/pull/7360
- Fix export of `State` and `allow_failure` for type-checkers  — https://github.com/PrefectHQ/prefect/pull/7447
- Fix `--skip-upload` flag in `prefect deployment build` — https://github.com/PrefectHQ/prefect/pull/7437
- Fix `visit_collection` handling of IO objects — https://github.com/PrefectHQ/prefect/pull/7482
- Ensure that queries are sorted correctly when limits are used — https://github.com/PrefectHQ/prefect/pull/7457

### Deprecations
- `PREFECT_CLOUD_URL` has been deprecated in favor of `PREFECT_CLOUD_API_URL` — https://github.com/PrefectHQ/prefect/pull/7411
- `prefect.orion.utilities.names` has been deprecated in favor of `prefect.utilities.names` — https://github.com/PrefectHQ/prefect/pull/7465

### Documentation
- Add support for dark mode — https://github.com/PrefectHQ/prefect/pull/7432 and https://github.com/PrefectHQ/prefect/pull/7462
- Add [audit log documentation](https://docs.prefect.io/ui/audit-log/) for Prefect Cloud — https://github.com/PrefectHQ/prefect/pull/7404
- Add [troubleshooting topics](https://docs.prefect.io/ui/troubleshooting/) for Prefect Cloud — https://github.com/PrefectHQ/prefect/pull/7446

### Collections
- Adds auto-registration of blocks from AWS, Azure, GCP, and Databricks collections — https://github.com/PrefectHQ/prefect/pull/7415
- Add new [`prefect-hightouch`](https://prefecthq.github.io/prefect-hightouch/) collection for [Hightouch](https://hightouch.com/) — https://github.com/PrefectHQ/prefect/pull/7443

### Contributors
- @tekumara
- @bcbernardo made their first contribution in https://github.com/PrefectHQ/prefect/pull/7360
- @br3ndonland made their first contribution in https://github.com/PrefectHQ/prefect/pull/7432

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.6...2.6.7


## Release 2.6.6

### Enhancements
- Add work queue status and health display to UI — [#733](https://github.com/PrefectHQ/orion-design/pull/733), [#743](https://github.com/PrefectHQ/orion-design/pull/743), [#750](https://github.com/PrefectHQ/orion-design/pull/750)
- Add `wait_for` to flows; subflows can wait for upstream tasks — https://github.com/PrefectHQ/prefect/pull/7343
- Add informative error if flow run is deleted while running — https://github.com/PrefectHQ/prefect/pull/7390
- Add name filtering support to the `work_queues/filter` API route — https://github.com/PrefectHQ/prefect/pull/7394
- Improve the stability of the scheduler service — https://github.com/PrefectHQ/prefect/pull/7412

### Fixes
- Fix GitHub storage error for Windows — https://github.com/PrefectHQ/prefect/pull/7372
- Fix links to flow runs in notifications — https://github.com/PrefectHQ/prefect/pull/7249
- Fix link to UI deployment page in CLI — https://github.com/PrefectHQ/prefect/pull/7376
- Fix UI URL routing to be consistent with CLI — https://github.com/PrefectHQ/prefect/pull/7391
- Assert that command is a list when passed to `open_process` — https://github.com/PrefectHQ/prefect/pull/7389
- Fix JSON error when serializing certain flow run parameters such as dataframes — https://github.com/PrefectHQ/prefect/pull/7385

### Documentation
- Add versioning documentation — https://github.com/PrefectHQ/prefect/pull/7353

### Collections
- New [`prefect-alert`](https://github.com/khuyentran1401/prefect-alert) collection for sending alerts on flow run fail
- New [Fivetran](https://fivetran.github.io/prefect-fivetran/) collection
- New [GitLab](https://prefecthq.github.io/prefect-gitlab/) collection

## Contributors
- @marwan116

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.5...2.6.6

## Release 2.6.5

### Enhancements
- Add support for manual flow run retries — https://github.com/PrefectHQ/prefect/pull/7152
- Improve server performance when retrying flow runs with many tasks — https://github.com/PrefectHQ/prefect/pull/7152
- Add status checks to work queues — https://github.com/PrefectHQ/prefect/pull/7262
- Add timezone parameter to `prefect deployment build` — https://github.com/PrefectHQ/prefect/pull/7282
- UI: Add redirect to original block form after creating a nested block — https://github.com/PrefectHQ/prefect/pull/7284
- Add support for multiple work queue prefixes — https://github.com/PrefectHQ/prefect/pull/7222
- Include "-" before random suffix of Kubernetes job names — https://github.com/PrefectHQ/prefect/pull/7329
- Allow a working directory to be specified for `Process` infrastructure — https://github.com/PrefectHQ/prefect/pull/7252
- Add support for Python 3.11 — https://github.com/PrefectHQ/prefect/pull/7304
- Add persistence of data when a state is returned from a task or flow — https://github.com/PrefectHQ/prefect/pull/7316
- Add `ignore_file` to `Deployment.build_from_flow()` — https://github.com/PrefectHQ/prefect/pull/7012

### Fixes
- Allow `with_options` to reset retries and retry delays — https://github.com/PrefectHQ/prefect/pull/7276
- Fix proxy-awareness in the `OrionClient` — https://github.com/PrefectHQ/prefect/pull/7328
- Fix block auto-registration when changing databases — https://github.com/PrefectHQ/prefect/pull/7350
- Include hidden files when uploading directories to `RemoteFileSystem` storage — https://github.com/PrefectHQ/prefect/pull/7336
- UI: added support for unsetting color-mode preference, `null` is now equivalent to "default" — https://github.com/PrefectHQ/prefect/pull/7321

### Documentation
- Add documentation for Prefect Cloud SSO — https://github.com/PrefectHQ/prefect/pull/7302

### Collections
- New [`prefect-docker`](https://prefecthq.github.io/prefect-docker/) collection for [Docker](https://www.docker.com/)
- New [`prefect-census`](https://prefecthq.github.io/prefect-census/) collection for [Census](https://docs.getcensus.com/)

## Contributors
- @BallisticPain made their first contribution in https://github.com/PrefectHQ/prefect/pull/7252
- @deepyaman
- @hateyouinfinity
- @jmg-duarte
- @taljaards

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.4...2.6.5

## Release 2.6.4

### Enhancements
- UI: Rename deployment "Overview" tab to "Description" — https://github.com/PrefectHQ/prefect/pull/7234
- Add `Deployment.build_from_flow` toggle to disable loading of existing values from the API — https://github.com/PrefectHQ/prefect/pull/7218
- Add `PREFECT_RESULTS_PERSIST_BY_DEFAULT` setting to globally toggle the result persistence default — https://github.com/PrefectHQ/prefect/pull/7228
- Add support for using callable objects as tasks — https://github.com/PrefectHQ/prefect/pull/7217
- Add authentication as service principal to the `Azure` storage block — https://github.com/PrefectHQ/prefect/pull/6844
- Update default database timeout from 1 to 5 seconds — https://github.com/PrefectHQ/prefect/pull/7246

### Fixes
- Allow image/namespace fields to be loaded from Kubernetes job manifest — https://github.com/PrefectHQ/prefect/pull/7244
- UI: Update settings API call to respect `ORION_UI_SERVE_BASE` environment variable — https://github.com/PrefectHQ/prefect/pull/7068
- Fix entrypoint path error when deployment is created on Windows then run on Unix — https://github.com/PrefectHQ/prefect/pull/7261

### Collections
- New [`prefect-kv`](https://github.com/madkinsz/prefect-kv) collection for persisting key-value data
- `prefect-aws`: Update [`S3Bucket`](https://prefecthq.github.io/prefect-aws/s3/#prefect_aws.s3.S3Bucket) storage block to enable use with deployments — https://github.com/PrefectHQ/prefect-aws/pull/82
- `prefect-aws`: Add support for arbitrary user customizations to [`ECSTask`](https://prefecthq.github.io/prefect-aws/ecs/) block — https://github.com/PrefectHQ/prefect-aws/pull/120
- `prefect-aws`: Removed the experimental designation from the [`ECSTask`](https://prefecthq.github.io/prefect-aws/ecs/) block
- `prefect-azure`: New [`AzureContainerInstanceJob`](https://prefecthq.github.io/prefect-azure/container_instance/) infrastructure block to run flows or commands as containers on Azure — https://github.com/PrefectHQ/prefect-azure/pull/45

### Contributors
- @Trymzet
- @jmg-duarte
- @mthanded made their first contribution in https://github.com/PrefectHQ/prefect/pull/7068

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.3...2.6.4

## Release 2.6.3

### Fixes
- Fix handling of `cache_result_in_memory` in `Task.with_options` — https://github.com/PrefectHQ/prefect/pull/7227

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.2...2.6.3

## Release 2.6.2

### Enhancements
- Add `CompressedSerializer` for compression of other result serializers — https://github.com/PrefectHQ/prefect/pull/7164
- Add option to drop task or flow return values from memory — https://github.com/PrefectHQ/prefect/pull/7174
- Add support for creating and reading notification policies from the client — https://github.com/PrefectHQ/prefect/pull/7154
- Add API support for sorting deployments — https://github.com/PrefectHQ/prefect/pull/7187
- Improve searching and sorting of flows and deployments in the UI —  https://github.com/PrefectHQ/prefect/pull/7160
- Improve recurrence rule schedule parsing with support for compound rules  — https://github.com/PrefectHQ/prefect/pull/7165
- Add support for private GitHub repositories — https://github.com/PrefectHQ/prefect/pull/7107

### Fixes
- Improve orchestration handling of `after_transition` when exception encountered — https://github.com/PrefectHQ/prefect/pull/7156
- Prevent block name from being reused on the block creation form in the UI — https://github.com/PrefectHQ/prefect/pull/7096
- Fix bug where `with_options` incorrectly updates result settings — https://github.com/PrefectHQ/prefect/pull/7186
- Add backwards compatibility for return of server-states from flows and tasks — https://github.com/PrefectHQ/prefect/pull/7189
- Fix naming of subflow runs tab on flow run page in the UI — https://github.com/PrefectHQ/prefect/pull/7192
- Fix `prefect orion start` error on Windows when module path contains spaces — https://github.com/PrefectHQ/prefect/pull/7224


### Collections
- New [prefect-monte-carlo](https://prefecthq.github.io/prefect-monte-carlo/) collection for interaction with [Monte Carlo](https://www.montecarlodata.com/)

### Contributors
- @jmg-duarte

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.1...2.6.2

## Release 2.6.1

### Fixes
- Fix bug where return values of `{}` or `[]` could be coerced to `None` — https://github.com/PrefectHQ/prefect/pull/7181

## Contributors
* @acookin made their first contribution in https://github.com/PrefectHQ/prefect/pull/7172

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.6.0...2.6.1

## Release 2.6.0

### First-class configuration of results 🎉

Previously, Prefect serialized the results of all flows and tasks with pickle, then wrote them to your local file system.
In this release, we're excited to announce this behavior is fully configurable and customizable.

Here are some highlights:

- Persistence of results is off by default.
    - We will turn on result persistence automatically if needed for a feature you're using, but you can always opt-out.
    - You can easily opt-in for any flow or task.
- You can choose the result serializer.
    - By default, we continue to use a pickle serializer, now with the ability to choose a custom implementation.
    - We now offer a JSON result serializer with support for all of the types supported by Pydantic.
    - You can also write your own serializer for full control.
    - Unless your results are being persisted, they will not be serialized.
- You can change the result storage.
    - By default, we will continue to use the local file system.
    - You can specify any of our storage blocks, such as AWS S3.
    - You can use any storage block you have defined.

All of the options can be customized per flow or task.

```python
from prefect import flow, task

# This flow defines a default result serializer for itself and all tasks in it
@flow(result_serializer="pickle")
def foo():
    one()
    two()
    three()

# This task's result will be persisted to the local file system
@task(persist_result=True)
def one():
    return "one!"

# This task will not persist its result
@task(persist_result=False)
def two():
    return "two!"

# This task will use a different serializer than the rest
@task(persist_result=True, result_serializer="json")
def three():
    return "three!"

# This task will persist its result to an S3 bucket
@task(persist_result=True, result_storage="s3/my-s3-block")
def four()
    return "four!
```

See the [documentation](https://docs.prefect.io/concepts/results/) for more details and examples.
See https://github.com/PrefectHQ/prefect/pull/6908 for implementation details.

### Waiting for tasks even if they fail

You can now specify that a downstream task should wait for an upstream task and run even if the upstream task has failed.

```python
from prefect import task, flow, allow_failure

@flow
def foo():
    upstream_future = fails_sometimes.submit()
    important_cleanup(wait_for=[allow_failure(upstream_future)])

@task
def fails_sometimes():
    raise RuntimeError("oh no!")

@task
def important_cleanup():
    ...
```

See https://github.com/PrefectHQ/prefect/pull/7120 for implementation details.

### Work queue match support for agents

Agents can now match multiple work queues by providing a `--match` string instead of specifying all of the work queues. The agent will poll every work queue with a name that starts with the given string. Your agent will detect new work queues that match the option without requiring a restart!

```
$ prefect agent start --match "foo-"
```

### Enhancements
- Add `--param` / `--params` support `prefect deployment run` — https://github.com/PrefectHQ/prefect/pull/7018
- Add 'Show Active Runs' button to work queue page — https://github.com/PrefectHQ/prefect/pull/7092
- Update block protection to only prevent deletion — https://github.com/PrefectHQ/prefect/pull/7042
- Improve stability by optimizing the HTTP client — https://github.com/PrefectHQ/prefect/pull/7090
- Optimize flow run history queries — https://github.com/PrefectHQ/prefect/pull/7138
- Optimize server handling by saving log batches in individual transactions — https://github.com/PrefectHQ/prefect/pull/7141
- Optimize deletion of auto-scheduled runs — https://github.com/PrefectHQ/prefect/pull/7102

### Fixes
- Fix `DockerContainer` log streaming crash due to "marked for removal" error — https://github.com/PrefectHQ/prefect/pull/6860
- Improve RRule schedule string parsing — https://github.com/PrefectHQ/prefect/pull/7133
- Improve handling of duplicate blocks, reducing errors in server logs — https://github.com/PrefectHQ/prefect/pull/7140
- Fix flow run URLs in notifications and `prefect deployment run` output — https://github.com/PrefectHQ/prefect/pull/7153

### Documentation
- Add documentation for support of proxies — https://github.com/PrefectHQ/prefect/pull/7087
- Fix rendering of Prefect settings in API reference — https://github.com/PrefectHQ/prefect/pull/7067

### Contributors
* @jmg-duarte
* @kevin868 made their first contribution in https://github.com/PrefectHQ/prefect/pull/7109
* @space-age-pete made their first contribution in https://github.com/PrefectHQ/prefect/pull/7122

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.5.0...2.6.0

## Release 2.5.0

### Exciting New Features 🎉

- Add `prefect.deployments.run_deployment` to create a flow run for a deployment with support for:
    - Configurable execution modes: returning immediately or waiting for completion of the run.
    - Scheduling runs in the future or now.
    - Custom flow run names.
    - Automatic linking of created flow run to the flow run it is created from.
    - Automatic tracking of upstream task results passed as parameters.
  <br />
  See https://github.com/PrefectHQ/prefect/pull/7047, https://github.com/PrefectHQ/prefect/pull/7081, and https://github.com/PrefectHQ/prefect/pull/7084

### Enhancements
- Add ability to delete multiple objects on flow run, flow, deployment and work queue pages — https://github.com/PrefectHQ/prefect/pull/7086
- Update `put_directory` to exclude directories from upload counts — https://github.com/PrefectHQ/prefect/pull/7054
- Always suppress griffe logs — https://github.com/PrefectHQ/prefect/pull/7059
- Add OOM warning to `Process` exit code log message — https://github.com/PrefectHQ/prefect/pull/7070
- Add idempotency key support to `OrionClient.create_flow_run_from_deployment` — https://github.com/PrefectHQ/prefect/pull/7074

### Fixes
- Fix default start date filter for deployments page in UI — https://github.com/PrefectHQ/prefect/pull/7025
- Fix `sync_compatible` handling of wrapped async functions and generators — https://github.com/PrefectHQ/prefect/pull/7009
- Fix bug where server could error due to an unexpected null in task caching logic — https://github.com/PrefectHQ/prefect/pull/7031
- Add exception handling to block auto-registration — https://github.com/PrefectHQ/prefect/pull/6997
- Remove the "sync caller" check from `sync_compatible` — https://github.com/PrefectHQ/prefect/pull/7073

### Documentation
- Add `ECSTask` block tutorial to recipes — https://github.com/PrefectHQ/prefect/pull/7066
- Update documentation for organizations for member management, roles, and permissions — https://github.com/PrefectHQ/prefect/pull/7058

## Collections
- New [prefect-soda-core](https://sodadata.github.io/prefect-soda-core/) collection for integration with [Soda](https://www.soda.io/).

### Contributors
- @taljaards

**All changes**: https://github.com/PrefectHQ/prefect/compare/2.4.5...2.5.0

## Release 2.4.5

This release disables block protection. With block protection enabled, as in 2.4.3 and 2.4.4, client and server versions cannot be mismatched unless you are on a version before 2.4.0. Disabling block protection restores the ability for a client and server to have different version.

Block protection was added in 2.4.1 to prevent users from deleting block types that are necessary for the system to function. With this change, you are able to delete block types that will cause your flow runs to fail. New safeguards that do not affect client/server compatibility will be added in the future.

## Release 2.4.3

**When running a server with this version, the client must be the same version. This does not apply to clients connecting to Prefect Cloud.**

### Enhancements
- Warn if user tries to login with API key from Cloud 1 — https://github.com/PrefectHQ/prefect/pull/6958
- Improve concurrent task runner performance — https://github.com/PrefectHQ/prefect/pull/6948
- Raise a `MissingContextError` when `get_run_logger` is called outside a run context — https://github.com/PrefectHQ/prefect/pull/6980
- Adding caching to API configuration lookups to improve performance — https://github.com/PrefectHQ/prefect/pull/6959
- Move `quote` to `prefect.utilities.annotations` — https://github.com/PrefectHQ/prefect/pull/6993
- Add state filters and sort-by to the work-queue, flow and deployment pages — https://github.com/PrefectHQ/prefect/pull/6985

### Fixes
- Fix login to private Docker registries — https://github.com/PrefectHQ/prefect/pull/6889
- Update `Flow.with_options` to actually pass retry settings to new object — https://github.com/PrefectHQ/prefect/pull/6963
- Fix compatibility for protected blocks when client/server versions are mismatched — https://github.com/PrefectHQ/prefect/pull/6986
- Ensure `python-slugify` is always used even if [unicode-slugify](https://github.com/mozilla/unicode-slugify) is installed — https://github.com/PrefectHQ/prefect/pull/6955

### Documentation
- Update documentation for specifying schedules from the CLI — https://github.com/PrefectHQ/prefect/pull/6968
- Add results concept to documentation — https://github.com/PrefectHQ/prefect/pull/6992

### Collections
- New [`prefect-hex` collection](https://prefecthq.github.io/prefect-hex/) — https://github.com/PrefectHQ/prefect/pull/6974
- New [`CloudRunJob` infrastructure block](https://prefecthq.github.io/prefect-gcp/cloud_run/) in `prefect-gcp` — https://github.com/PrefectHQ/prefect-gcp/pull/48

### Contributors
* @Hongbo-Miao made their first contribution in https://github.com/PrefectHQ/prefect/pull/6956
* @hateyouinfinity made their first contribution in https://github.com/PrefectHQ/prefect/pull/6955

## Release 2.4.2

### Fixes
- Remove types in blocks docstring attributes to avoid annotation parsing warnings — https://github.com/PrefectHQ/prefect/pull/6937
- Fixes `inject_client` in scenarios where the `client` kwarg is passed `None` — https://github.com/PrefectHQ/prefect/pull/6942

### Contributors
* @john-jam made their first contribution in https://github.com/PrefectHQ/prefect/pull/6937

## Release 2.4.1

### Enhancements
- Add TTL to `KubernetesJob` for automated cleanup of finished jobs — https://github.com/PrefectHQ/prefect/pull/6785
- Add `prefect kubernetes manifest agent` to generate an agent Kubernetes manifest — https://github.com/PrefectHQ/prefect/pull/6771
- Add `prefect block type delete` to delete block types — https://github.com/PrefectHQ/prefect/pull/6849
- Add dynamic titles to tabs in UI — https://github.com/PrefectHQ/prefect/pull/6914
- Hide secret tails by default — https://github.com/PrefectHQ/prefect/pull/6846
- Add runs tab to show flow runs on the flow, deployment, and work-queue pages in the UI — https://github.com/PrefectHQ/prefect/pull/6721
- Add toggle to disable block registration on application start — https://github.com/PrefectHQ/prefect/pull/6858
- Use injected client during block registration, save, and load — https://github.com/PrefectHQ/prefect/pull/6857
- Refactor of `prefect.client` into `prefect.client.orion` and `prefect.client.cloud` — https://github.com/PrefectHQ/prefect/pull/6847
- Improve breadcrumbs on radar page in UI — https://github.com/PrefectHQ/prefect/pull/6757
- Reject redundant state transitions to prevent duplicate runs — https://github.com/PrefectHQ/prefect/pull/6852
- Update block auto-registration to use a cache to improve performance — https://github.com/PrefectHQ/prefect/pull/6841
- Add ability to define blocks from collections to be registered by default — https://github.com/PrefectHQ/prefect/pull/6890
- Update file systems interfaces to be sync compatible — https://github.com/PrefectHQ/prefect/pull/6511
- Add flow run URLs to notifications — https://github.com/PrefectHQ/prefect/pull/6798
- Add client retries on 503 responses — https://github.com/PrefectHQ/prefect/pull/6927
- Update injected client retrieval to use the flow and task run context client for reduced overhead — https://github.com/PrefectHQ/prefect/pull/6859
- Add Microsoft Teams notification block — https://github.com/PrefectHQ/prefect/pull/6920

### Fixes
- Fix `LocalFileSystem.get_directory` when from and to paths match — https://github.com/PrefectHQ/prefect/pull/6824
- Fix registration of block schema versions — https://github.com/PrefectHQ/prefect/pull/6803
- Update agent to capture infrastructure errors and fail the flow run instead of crashing — https://github.com/PrefectHQ/prefect/pull/6903
- Fix bug where `OrionClient.read_logs` filter was ignored — https://github.com/PrefectHQ/prefect/pull/6885

### Documentation
- Add GitHub and Docker deployment recipe — https://github.com/PrefectHQ/prefect/pull/6825
- Add parameter configuration examples — https://github.com/PrefectHQ/prefect/pull/6886

### Collections
- Add `prefect-firebolt` to collections catalog — https://github.com/PrefectHQ/prefect/pull/6917

### Helm Charts
- Major overhaul in how helm charts in `prefect-helm` are structured and how we version and release them — [2022.09.21 release](https://github.com/PrefectHQ/prefect-helm/releases/tag/2022.09.21)

### Contributors
- @jmg-duarte
- @taljaards
- @yashlad681
- @hallenmaia made their first contributions(!) in https://github.com/PrefectHQ/prefect/pull/6903, https://github.com/PrefectHQ/prefect/pull/6785, and https://github.com/PrefectHQ/prefect/pull/6771
- @dobbersc made their first contribution in https://github.com/PrefectHQ/prefect/pull/6870
- @jnovinger made their first contribution in https://github.com/PrefectHQ/prefect/pull/6916
- @mathijscarlu made their first contribution in https://github.com/PrefectHQ/prefect/pull/6885


## Release 2.4.0

### Exciting New Features 🎉
- Add `ECSTask` infrastructure block to run commands and flows on AWS ECS<br />
    See [the documentation](https://prefecthq.github.io/prefect-aws/ecs/) in the [prefect-aws collection](https://prefecthq.github.io/prefect-aws/) and usage notes in the [infrastructure guide](https://docs.prefect.io/concepts/infrastructure/#ecstask)

### Enhancements
- Update the deployments CLI to better support CI/CD use cases — https://github.com/PrefectHQ/prefect/pull/6697
- Improve database query performance by removing unnecessary SQL transactions — https://github.com/PrefectHQ/prefect/pull/6714
- Update blocks to dispatch instance creation using slugs — https://github.com/PrefectHQ/prefect/pull/6622
- Add flow run start times to flow run metadata in UI — https://github.com/PrefectHQ/prefect/pull/6743
- Update default infrastructure command to be set at runtime — https://github.com/PrefectHQ/prefect/pull/6610
- Allow environment variables to be "unset" in infrastructure blocks — https://github.com/PrefectHQ/prefect/pull/6650
- Add favicon switching feature for flow and task run pages — https://github.com/PrefectHQ/prefect/pull/6794
- Update `Deployment.infrastructure` to accept types outside of the core library i.e. custom infrastructure or from collections — https://github.com/PrefectHQ/prefect/pull/6674
- Update `deployment build --rrule` input to allow start date and timezones — https://github.com/PrefectHQ/prefect/pull/6761

### Fixes
- Update crash detection to ignore abort signals — https://github.com/PrefectHQ/prefect/pull/6730
- Protect against race condition with deployment schedules — https://github.com/PrefectHQ/prefect/pull/6673
- Fix saving of block fields with aliases — https://github.com/PrefectHQ/prefect/pull/6758
- Preserve task dependencies to futures passed as parameters in `.map` — https://github.com/PrefectHQ/prefect/pull/6701
- Update task run orchestration to include latest metadata in context — https://github.com/PrefectHQ/prefect/pull/6791

### Documentation
- Task runner documentation fixes and clarifications — https://github.com/PrefectHQ/prefect/pull/6733
- Add notes for Windows and Linux installation — https://github.com/PrefectHQ/prefect/pull/6750
- Add a catalog of implementation recipes — https://github.com/PrefectHQ/prefect/pull/6408
- Improve storage and file systems documentation — https://github.com/PrefectHQ/prefect/pull/6756
- Add CSS for badges — https://github.com/PrefectHQ/prefect/pull/6655

### Contributors
* @robalar made their first contribution in https://github.com/PrefectHQ/prefect/pull/6701
* @shraddhafalane made their first contribution in https://github.com/PrefectHQ/prefect/pull/6784

## 2.3.2

### Enhancements
* UI displays an error message when backend is unreachable - https://github.com/PrefectHQ/prefect/pull/6670

### Fixes
* Fix issue where parameters weren't updated when a deployment was re-applied by @lennertvandevelde in https://github.com/PrefectHQ/prefect/pull/6668
* Fix issues with stopping Orion on Windows machines - https://github.com/PrefectHQ/prefect/pull/6672
* Fix issue with GitHub storage running in non-empty directories - https://github.com/PrefectHQ/prefect/pull/6693
* Fix issue where some user-supplied values were ignored when creating new deployments - https://github.com/PrefectHQ/prefect/pull/6695

### Collections
* Added [prefect-fugue](https://fugue-project.github.io/prefect-fugue/) 

### Contributors
* @lennertvandevelde made their first contribution! — [https://github.com/PrefectHQ/prefect/pull/6668](https://github.com/PrefectHQ/prefect/pull/6668)

## 2.3.1

### Enhancements
* Add sync compatibility to `run` for all infrastructure types — https://github.com/PrefectHQ/prefect/pull/6654
* Update Docker container name collision log to `INFO` level for clarity — https://github.com/PrefectHQ/prefect/pull/6657
* Refactor block documents queries for speed ⚡️ — https://github.com/PrefectHQ/prefect/pull/6645
* Update block CLI to match standard styling — https://github.com/PrefectHQ/prefect/pull/6679

### Fixes
* Add `git` to the Prefect image — https://github.com/PrefectHQ/prefect/pull/6653
* Update Docker container runs to be robust to container removal — https://github.com/PrefectHQ/prefect/pull/6656
* Fix parsing of `PREFECT_TEST_MODE` in `PrefectBaseModel` — https://github.com/PrefectHQ/prefect/pull/6647
* Fix handling of `.prefectignore` paths on Windows — https://github.com/PrefectHQ/prefect/pull/6680

### Collections
* [prefect-juptyer](https://prefecthq.github.io/prefect-jupyter/)

### Contributors
* @mars-f made their first contribution — https://github.com/PrefectHQ/prefect/pull/6639
* @pdashk made their first contribution — https://github.com/PrefectHQ/prefect/pull/6640

## 2.3.0

### Exciting New Features 🎉

- Add support for deploying flows stored in Docker images — [#6574](https://github.com/PrefectHQ/prefect/pull/6574)
- Add support for deploying flows stored on GitHub — [#6598](https://github.com/PrefectHQ/prefect/pull/6598)
- Add file system block for reading directories from GitHub — [#6517](https://github.com/PrefectHQ/prefect/pull/6517)
- Add a context manager to disable the flow and task run loggers for testing — [#6575](https://github.com/PrefectHQ/prefect/pull/6575)
- Add task run pages to the UI — [#6570](https://github.com/PrefectHQ/prefect/pull/6570)

### Enhancements

- Add "cloud" to `prefect version` server type display — [#6523](https://github.com/PrefectHQ/prefect/pull/6523)
- Use the parent flow run client for child flow runs if available — [#6526](https://github.com/PrefectHQ/prefect/pull/6526)
- Add display of Prefect version when starting agent — [#6545](https://github.com/PrefectHQ/prefect/pull/6545)
- Add type hints to state predicates, e.g. `is_completed()` — [#6561](https://github.com/PrefectHQ/prefect/pull/6561)
- Add error when sync compatible methods are used incorrectly — [#6565](https://github.com/PrefectHQ/prefect/pull/6565)
- Improve performance of task run submission — [#6527](https://github.com/PrefectHQ/prefect/pull/6527)
- Improve performance of flow run serialization for `/flow_runs/filter` endpoint — [#6553](https://github.com/PrefectHQ/prefect/pull/6553)
- Add field to states with untrackable dependencies due to result types — [#6472](https://github.com/PrefectHQ/prefect/pull/6472)
- Update `Task.map` iterable detection to exclude strings and bytes — [#6582](https://github.com/PrefectHQ/prefect/pull/6582)
- Add a version attribute to the block schema model — [#6491](https://github.com/PrefectHQ/prefect/pull/6491)
- Add better error handling in the telemetry service — [#6124](https://github.com/PrefectHQ/prefect/pull/6124)
- Update the Docker entrypoint display for the Prefect image — [#655](https://github.com/PrefectHQ/prefect/pull/6552)
- Add a block creation link to `prefect block type ls` — [#6493](https://github.com/PrefectHQ/prefect/pull/6493)
- Allow customization of notifications of queued flow runs — [#6538](https://github.com/PrefectHQ/prefect/pull/6538)
- Avoid duplicate saves of storage blocks as anonymous blocks — [#6550](https://github.com/PrefectHQ/prefect/pull/6550)
- Remove save of agent default infrastructure blocks — [#6550](https://github.com/PrefectHQ/prefect/pull/6550)
- Add a `--skip-upload` flag to `prefect deployment build` — [#6560](https://github.com/PrefectHQ/prefect/pull/6560)
- Add a `--upload` flag to `prefect deployment apply` — [#6560](https://github.com/PrefectHQ/prefect/pull/6560)
- Add the ability to specify relative sub-paths when working with remote storage for deployments — [#6518](https://github.com/PrefectHQ/prefect/pull/6518)
- Prevent non-UUID slugs from raising errors on `/block_document` endpoints — [#6541](https://github.com/PrefectHQ/prefect/pull/6541)
- Improve Docker image tag parsing to support the full Moby specification — [#6564](https://github.com/PrefectHQ/prefect/pull/6564)
### Fixes

- Set uvicorn `--app-dir` when starting Orion to avoid module collisions — [#6547](https://github.com/PrefectHQ/prefect/pull/6547)
- Resolve issue with Python-based deployments having incorrect entrypoint paths — [#6554](https://github.com/PrefectHQ/prefect/pull/6554)
- Fix Docker image tag parsing when ports are included — [#6567](https://github.com/PrefectHQ/prefect/pull/6567)
- Update Kubernetes Job to use `args` instead of `command` to respect image entrypoints — [#6581](https://github.com/PrefectHQ/prefect/pull/6581)
    - Warning: If you are using a custom image with an entrypoint that does not allow passthrough of commands, flow runs will fail.
- Fix edge case in `sync_compatible` detection when using AnyIO task groups — [#6602](https://github.com/PrefectHQ/prefect/pull/6602)
- Add check for infrastructure and storage block capabilities during deployment build — [#6535](https://github.com/PrefectHQ/prefect/pull/6535)
- Fix issue where deprecated work queue pages showed multiple deprecation notices — [#6531](https://github.com/PrefectHQ/prefect/pull/6531)
- Fix path issues with `RemoteFileSystem` and Windows — [#6620](https://github.com/PrefectHQ/prefect/pull/6620)
- Fix a bug where `RemoteFileSystem.put_directory` did not respect `local_path` — [#6620](https://github.com/PrefectHQ/prefect/pull/6620)

### Documentation

- Add tutorials for creating and using storage and infrastructure blocks — [#6608](https://github.com/PrefectHQ/prefect/pull/6608)
- Update tutorial for running flows in Docker — [#6612](https://github.com/PrefectHQ/prefect/pull/6612)
- Add example of calling a task from a task — [#6501](https://github.com/PrefectHQ/prefect/pull/6501)
- Update database documentation for Postgres to clarify required plugins — [#6566](https://github.com/PrefectHQ/prefect/pull/6566)
- Add example of using `Task.map` in docstring — [#6579](https://github.com/PrefectHQ/prefect/pull/6579)
- Add details about flow run retention policies — [#6577](https://github.com/PrefectHQ/prefect/pull/6577)
- Fix flow parameter name docstring in deployments — [#6599](https://github.com/PrefectHQ/prefect/pull/6599)


### Contributors

Thanks to our external contributors!

- @darrida
- @jmg-duarte
- @MSSandroid

## 2.2.0

### Exciting New Features 🎉
* Added automatic detection of static arguments to `Task.map` in https://github.com/PrefectHQ/prefect/pull/6513

### Fixes
* Updated deployment flow run retry settings with runtime values in https://github.com/PrefectHQ/prefect/pull/6489
* Updated media queries for flow-run-filter in https://github.com/PrefectHQ/prefect/pull/6484
* Added `empirical_policy` to flow run update route in https://github.com/PrefectHQ/prefect/pull/6486
* Updated flow run policy retry settings to be nullable in https://github.com/PrefectHQ/prefect/pull/6488
* Disallowed extra attribute initialization on `Deployment` objects in https://github.com/PrefectHQ/prefect/pull/6505
* Updated `deployment build` to raise an informative error if two infrastructure configs are provided in https://github.com/PrefectHQ/prefect/pull/6504
* Fixed calling async subflows from sync parents in https://github.com/PrefectHQ/prefect/pull/6514

## 2.1.1

### Fixes

* Fixed log on abort when the flow run context is not available in https://github.com/PrefectHQ/prefect/pull/6402
* Fixed error message in `submit_run` in https://github.com/PrefectHQ/prefect/pull/6453
* Fixed error if default parameters are missing on a deployment flow run in https://github.com/PrefectHQ/prefect/pull/6465
* Added error message if `get_run_logger` receives context of unknown type in https://github.com/PrefectHQ/prefect/pull/6401

## 2.1.0

### Build Deployments in Python
The new, YAML-based deployment definition provides a simple, extensible foundation for our new deployment creation experience. Now, by popular demand, we're extending that experience to enable you to define deployments and build them from within Python. You can do so by defining a `Deployment` Python object, specifying the deployment options as properties of the object, then building and applying the object using methods of `Deployment`. See the [documentation](https://docs.prefect.io/concepts/deployments/) to learn more.

### Simplified Agents & Work Queues
Agents and work queues give you control over where and how flow runs are executed. Now, creating an agent (and corresponding work queue) is even easier. Work queues now operate strictly by name, not by matching tags. Deployments, and the flow runs they generate, are explicitly linked to a single work queue, and the work queue is automatically created whenever a deployment references it. This means you no longer need to manually create a new work queue each time you want to want to route a deployment's flow runs separately. Agents can now pull from multiple work queues, and also automatically generate work queues that don't already exist. The result of these improvements is that most users will not have to interact directly with work queues at all, but advanced users can take advantage of them for increased control over how work is distributed to agents. These changes are fully backwards compatible. See the [documentation](https://docs.prefect.io/concepts/work-queues/) to learn more.

### Improvements and bug fixes
* Added three new exceptions to improve errors when parameters are incorrectly supplied to flow runs in https://github.com/PrefectHQ/prefect/pull/6091
* Fixed a task dependency issue where unpacked values were not being correctly traced in https://github.com/PrefectHQ/prefect/pull/6348
* Added the ability to embed `BaseModel` subclasses as fields within blocks, resolving an issue with the ImagePullPolicy field on the KubernetesJob block in https://github.com/PrefectHQ/prefect/pull/6389
* Added comments support for deployment.yaml to enable inline help in https://github.com/PrefectHQ/prefect/pull/6339
* Added support for specifying three schedule types - cron, interval and rrule - to the `deployment build` CLI in https://github.com/PrefectHQ/prefect/pull/6387
* Added error handling for exceptions raised during the pre-transition hook fired by an OrchestrationRule during state transitions in https://github.com/PrefectHQ/prefect/pull/6315
* Updated `visit_collection` to be a synchronous function in https://github.com/PrefectHQ/prefect/pull/6371
* Revised loop service method names for clarity in https://github.com/PrefectHQ/prefect/pull/6131
* Modified deployments to load flows in a worker thread in https://github.com/PrefectHQ/prefect/pull/6340
* Resolved issues with capture of user-raised timeouts in https://github.com/PrefectHQ/prefect/pull/6357
* Added base class and async compatibility to DockerRegistry in https://github.com/PrefectHQ/prefect/pull/6328
* Added `max_depth` to `visit_collection`, allowing recursion to be limited in https://github.com/PrefectHQ/prefect/pull/6367
* Added CLI commands for inspecting and deleting Blocks and Block Types in https://github.com/PrefectHQ/prefect/pull/6422
* Added a Server Message Block (SMB) file system block in https://github.com/PrefectHQ/prefect/pull/6344 - Special thanks to @darrida for this contribution!
* Removed explicit type validation from some API routes in https://github.com/PrefectHQ/prefect/pull/6448
* Improved robustness of streaming output from subprocesses in https://github.com/PrefectHQ/prefect/pull/6445
* Added a default work queue ("default") when creating new deployments from the Python client or CLI in https://github.com/PrefectHQ/prefect/pull/6458

### New Collections
- [prefect-monday](https://prefecthq.github.io/prefect-monday/)
- [prefect-databricks](https://prefecthq.github.io/prefect-databricks/)
- [prefect-fugue](https://github.com/fugue-project/prefect-fugue/)

**Full Changelog**: https://github.com/PrefectHQ/prefect/compare/2.0.4...2.1.0

## 2.0.4

### Simplified deployments
The deployment experience has been refined to remove extraneous artifacts and make configuration even easier. In particular:

-   `prefect deployment build` no longer generates a  `manifest.json` file. Instead, all of the relevant information is written to the `deployment.yaml` file.
- Values in the `deployment.yaml` file are more atomic and explicit
-   Local file system blocks are no longer saved automatically
-   Infrastructure block values can now be overwritten with the new `infra_overrides` field

### Start custom flow runs from the UI
Now, from the deployment page, in addition to triggering an immediate flow run with default parameter arguments, you can also create a custom run. A custom run enables you to configure the run's parameter arguments, start time, name, and more, all while otherwise using the same deployment configuration. The deployment itself will be unchanged and continue to generate runs on its regular schedule.

### Improvements and bug fixes
- Made timeout errors messages on state changes more intuitive
- Added debug level logs for task run rehydration
- Added basic CLI functionality to inspect Blocks; more to come
- Added support for filtering on state name to `prefect flow-run ls`
- Refined autogenerated database migration output

## 2.0.3

This release contains a number of bug fixes and documentation improvements.

### Introducing [`prefect-dbt`](https://prefecthq.github.io/prefect-dbt/)

We've released `prefect-dbt` - a collection of Prefect integrations for working with dbt in your Prefect flows. This collection has been built as part of a partnership with dbt Labs to ensure that it follows best practices for working with dbt.

### Improvements and bug fixes
- Azure storage blocks can use `.prefectignore`
- Resolved bugs and improved interface in the Orion client.
- Resolved a bug in Azure storage blocks that would cause uploads to get stuck.
- Resolved a bug where calling a flow in a separate thread would raise an exception.
- Resolved issues with loading flows from a deployment.
- Corrected some erroneous type annotations.
- Better handling of database errors during state transition validation.
- Better sanitization of labels for Kubernetes Jobs.
- Fixes `--manifest-only` flag of `prefect deployment build` command to ensure that using this flag, the manifest gets generated, but the upload to a storage location is skipped.
- Added support for multiple YAML deployment paths to the `prefect deployment apply` command.


## 2.0.2

This release implements a number of improvements and bug fixes in response to continued engagement by members of our community. Thanks, as always, to all who submitted ideas on how to make Prefect 2 even better.

### Introducing .prefectignore files
 .prefectignore files allow users to omit certain files or directories from their deployments. Similar to other .ignore files, the syntax supports pattern matching, so an entry of `*.pyc` will ensure *all* .pyc files are ignored by the deployment call when uploading to remote storage. Prefect provides a default .prefectignore file, but users can customize it to their needs.

### Improvements and bug fixes
- Users can now leverage Azure storage blocks.
- Users can now submit bug reports and feature enhancements using our issue templates.
- Block deletion is now more performant.
- Inconsistencies in UI button copy have been removed.
- Error messaging is clearer in the `deployment build` CLI command.
- Resolved timeout errors that occurred when using async task functions inside synchronous flows.

## 2.0.1

The response to Prefect 2 has been overwhelming in the best way possible. Thank you to the many community members who tried it out and gave us feedback! Thanks in particular to the students at this week's Prefect Associate Certification Course (PACC) in San Jose for their thoughtful recommendations. This release is a compilation of enhancements and fixes that make for a more resilient, performant, and refined Prefect experience.

### Improvements and bug fixes
- Schedules set via the API or UI are now preserved when building deployments from the CLI
- JSON types are now coerced to none, following Javascript convention and supporting standards compatibility
- The `prefect deployment execute` command has been removed to avoid confusion between running a flow locally from a Python script and running it by an agent using `prefect deployment run`
- This repository now includes templates for pull requests and issues to make bug reports and community contributions easier
- The `scheduler` and `flow-run-notifications` LoopServices have been made more resilient
- Log inserts have been made more performant through smaller log batches
- Local file system blocks created from the UI now point to the right `base_path`
- Support for unmapped values to Task.map has been added as requested by Club42 members
- The `deployment build` command now supports an optional output flag to customize the name of the deployment.yaml file, to better support projects with multiple flows

## 2.0.0

We're thrilled to announce that, with this release, Prefect 2.0 has exited its public beta! Hopefully, this release comes as no surprise. It is the culmination of nearly a year of building in public and incorporating your feedback. Prefect 2.0 is now the default version of the open source `prefect` framework provided [upon installation](https://docs.prefect.io/getting-started/installation/). We will continue enhancing Prefect 2.0 rapidly, but future breaking changes will be less frequent and more notice will be provided.

Prefect 2.0 documentation is now hosted at [docs.prefect.io](https://docs.prefect.io). Prefect 1.0 documentation is now hosted at [docs-v1.prefect.io](https://docs-v1.prefect.io).

### Upgrading from Prefect 1.0
Flows written with Prefect 1.0 will require modifications to run with Prefect 2.0. If you're using Prefect 1.0, please see our [guidance on Discourse for explicitly pinning your Prefect version in your package manager and Docker](https://discourse.prefect.io/t/the-general-availability-release-of-prefect-2-0-going-live-on-wednesday-27th-of-july-may-break-your-flows-unless-you-take-action-as-soon-as-possible/1227), so that you can make the transition to Prefect 2.0 when the time is right for you. See our [migration page](https://upgrade.prefect.io/) to learn more about upgrading.

### Upgrading from earlier versions of Prefect 2.0
We have shipped a lot of breaking changes to Prefect 2.0 over the past week. Most importantly, **recent changes to deployments required that schedules for all previously created deployments be turned off**. You can learn more about the changes via the [deployments concept documentation](https://docs.prefect.io/concepts/deployments/), the [tutorial](https://docs.prefect.io/tutorials/deployments/), or the [discourse guide](https://discourse.prefect.io/t/deployments-are-now-simpler-and-declarative/1255).

## 2.0b16

### Simplified, declarative deployments
Prefect 2.0's deployments are a powerful way to encapsulate a flow, its required infrastructure, its schedule, its parameters, and more. Now, you can create deployments simply, with just two commands:
1. `prefect deployment build ./path/to/flow/file.py:name_of_flow_obj --name "Deployment Name"` produces two files:
     - A manifest file, containing workflow-specific information such as the code location, the name of the entrypoint flow, and flow parameters
     - A `deployment.yaml` file - a complete specification of the metadata and configuration for the deployment such as the name, tags, and description
3. `prefect deployment apply ./deployment.yaml` creates or updates a deployment with the Orion server

Once the deployment is created with the Orion server, it can now be edited via the UI! See the [Deployments documentation to learn more](https://orion-docs.prefect.io/concepts/deployments/).

### Improvements and bug fixes
- The [Dask and Ray tutorials](https://orion-docs.prefect.io/tutorials/dask-ray-task-runners/) have been updated to reflect recent changes
- The [Blocks concept doc](https://orion-docs.prefect.io/concepts/blocks/) has been updated to reflect recent enhancements and includes additional examples
- The [Storage concept doc](https://orion-docs.prefect.io/concepts/storage/) has been updated to reflect recent enhancements
- All IntervalSchedules now require both an anchor date and a timezone
- The new S3 file system block enables you to read and write data as a file on Amazon S3
- The new GCS file system block allows you to read and write data as a file on Google Cloud Storage

## 2.0b15

### Uniquely refer to blocks with slugs
Blocks are a convenient way to secure store and retrieve configuration. Now, retrieving configuration stored with blocks is even easier with slugs, both human and machine readable unique identifiers. By default, block type slugs are a lowercase, dash delimited version of the block type name, but can be customized via the `_block_type_slug` field on a custom Block subclass. Block document slugs are a concatenation of [block-type-slug]/[block-document-name] and can be used as an argument to the `Block.load` method. Slugs and block document names may only include alphanumeric characters and dashes.

**Warning**: This breaking change makes this release incompatible with previous versions of the Orion server and Prefect Cloud 2.0

### Other improvements and bug fixes

## 2.0b14

### Retreive the state of your tasks or flows with the `return_state` kwarg
Beginning with 2.0b9, Prefect 2.0 began returning function results, instead of Prefect futures and states, by default. States are still an important concept in Prefect 2. They can be used to dictate and understand the behavior of your flows. Now, you can access the state for _any_ task or flow with the new `return_state` kwarg. Just set `return_state=True` in you flow or task call and you can access its state with the `.result()` method, even if it's been submitted to a task runner.

### `prefect cloud` commands are easier to use
The `prefect cloud login` command no longer overwrites your current profile with a new API URL and auth key. Instead, the command will prompt you to create a new profile when logging into Prefect Cloud 2.0. Subsequent calls to prefect cloud login using the same key will simply "log in" to prefect cloud by switching to the profile associated with that authentication key.

The new `prefect cloud workspace ls` command lists availible workspaces.

### Other improvements and bug fixes
- The anchor datetime (aka start datetime) for all newly created interval schedules will be the current date & time
- The `prefect orion start` command now handles keyboard interrupts
- CLI performance has been sped up 30-40% through improved import handling
- UI screenschots have been updated throughout the documentation
- Broken links don't feel as bad with our slick new 404 page

## 2.0b13

### Improvements and bug fixes
- RRule schedule strings are now validated on initialization to confirm that the provided RRule strings are valid
- Concepts docs have been updated for clarity and consistency
- `IntervalSchedule`'s now coerce naive datetimes to timezone-aware datetimes, so that interval schedules created with timezone-unaware datetimes will work

## 2.0b12

### Work queue pages now display upcoming runs
A new "Upcoming runs" tab has been added to the work queue page, enabling you to see all of the runs that are eligible for that work queue before they are picked up by an agent.

### Other improvements and bug fixes
- You can now set a concurrency limit when creating a work queue via the CLI
- In order to avoid unwittingly breaking references to shared blocks, block names are no longer editable
- Getting started documentation has been updated and edited for clarity
- Blocks API documentation has been updated to include system, kubernetes, and notifications block modules

## 2.0b11

This release builds upon the collection of small enhancements made in the previous release.

### Default storage has been removed
For convenience, earlier versions of Prefect 2.0 allowed for a global storage setting. With forthcoming enhancements to blocks, this will no longer be necessary.

### Other improvements and bug fixes
- We have published a [guide for migrating workflows from Prefect 1.0 (and lower) to Prefect 2.0](https://orion-docs.prefect.io/migration_guide/)
- The Flow run page now has a clearer empty state that is more consistent with other pages
- Tutorial documentation has been further updated to reflect new result behavior
- Tasks and flows now run in interruptible threads when timeouts are used
- Parameter validation no longer fails on unsupported types
- The UI now returns you to the blocks overview after deleting a block
- Flow run logs have been updated to improve user visibility into task runner usage
- Concurrency limits of 0 are now respected on work queues

## 2.0b10

This release is the first of a series of smaller releases to be released daily.

### Improvements and bug fixes
- The Blocks selection page now includes more complete and consistent metadata about each block type, including block icons, descriptions, and examples
- We've added a new [CLI style guide](https://github.com/PrefectHQ/prefect/blob/orion/docs/contributing/style.md#command-line-interface-cli-output-messages) for contributors
- Work queues no longer filter on flow runner types, this capability will instead be achieved through tags
- Tutorial documentation has been updated to reflect new result behavior

## 2.0b9

Big things are in the works for Prefect 2! This release includes breaking changes and deprecations in preparation for Prefect 2 graduating from its beta period to General Availability.

**With next week's release on July 27th, Prefect 2 will become the default package installed with `pip install prefect`. Flows written with Prefect 1 will require modifications to run with Prefect 2**. Please ensure that your package management process enables you to make the transition when the time is right for you.

### Code as workflows
As Prefect 2 usage has grown, we've observed a pattern among users, especially folks that were not previously users of Prefect 1. Working with Prefect was so much like working in native Python, users were often surprised that their tasks returned futures and states, Prefect objects, rather than results, the data that their Python functions were handling. This led to unfamiliar, potentially intimidating, errors in some cases. With this release, Prefect moves one step closer to code as workflows - tasks now return the results of their functions, rather than their states, by default. This means that you can truly take most native Python scripts, add the relevant @flow and @task decorators, and start running that script as a flow, benefitting from the observability and resilience that Prefect provides.

States and futures are still important concepts in dictating and understanding the behavior of flows. You will still be able to easily access and use them with the `.submit()` method. You will need to modify tasks in existing Prefect 2 flows to use this method to continue working as before.

### Other improvements and bug fixes
- A new `Secret` block can store a string that is encrypted at rest as well as obfuscated in logs and the UI
- Date filters on the flow run page in the UI now support filtering by date _and_ time
- Each work queue page in the UI now includes a command to start a corresponding agent
- Tutorials have been updated for increased clarity and consistency
- Cron schedule setting errors are now more informative
- Prefect now still works even if the active profile is missing
- Conda requirements regex now supports underscores and dots
- The previously deprecated `DeploymentSpec` has been removed

## 2.0b8

This is our biggest release yet! It's full of exciting new features and refinements to existing concepts. Some of these features are the result of careful planning and execution over the past few months, while others are responses to your feedback, unplanned but carefully considered. None would be possible without your continued support. Take it for a spin and let us know what you think!

This release removes the deprecated `DaskTaskRunner` and `RayTaskRunner` from the core library, breaking existing references to them. You can find them in their respective collections [prefect-ray](https://prefecthq.github.io/prefect-ray/) and [prefect-dask](https://prefecthq.github.io/prefect-dask). It also removes the previously deprecated restart policy for the `KubernetesFlowRunnner`. Most importantly, there are new **breaking changes** to the Deployments interface described below.

### Flow Run Retries
Flow run retries have been one of our most requested features, especially given how easy it is to run a flow as a "subflow" or "child flow" with Prefect 2.0. Flow run retries are configured just as task retries are - with the `retries` and `retry_delay_seconds` parameters.

If both a task and its flow have retries configured, tasks within the flow will retry up to their specified task retry limit for each flow run. For example, if you have a **flow** configured with a limit of 2 retries (up to 3 total runs, including the initial attempt), and a **task** in the flow configured with 3 retries (up to 4 attempts per flow run, including the initial attempt). The task could run up to a total of 12 attempts, since task retry limits are reset after each flow run or flow run attempt.

### Notifications
At any time, you can visit the Prefect UI to get a comprehensive view of the state of all of your flows, but when something goes wrong with one of them, you need that information immediately. Prefect 2.0’s new notifications can alert you and your team when any flow enters any state you specify, with or without specific tags.

To create a notification, go to the new Notifications page via the sidebar navigation and select “Create Notification.” Notifications are structured just as you would describe them to someone. For example, if I want to get a Slack message every time my daily-ETL flow fails, my notification will simply read:

> If a run of any flow with **any** tag enters a **failed** state, send a notification to **my-slack-webhook**

When the conditions of the notification are triggered, you’ll receive a simple message:

> The **fuzzy-leopard** run of the **daily-etl** flow entered a **failed** state at **yy-MM-dd HH:mm:ss TMZ**.

Currently, notifications can only be sent to a [Slack webhook](https://api.slack.com/messaging/webhooks) (or email addresses if you are using [Prefect Cloud 2.0](https://app.prefect.cloud)). Over time, notifications will support additional messaging services. Let us know which messaging services you’d like to send your notifications to!

### Flow packaging and deployment
We've revisited our flow packaging and deployment UX, making it both more powerful and easier to use. `DeploymentSpec`s are now just `Deployment`s. Most of the fields are unchanged, but there are a few differences:
- The `flow_storage` field has been replaced with a `packager` field.
- The `flow_location`, `flow_name`, and `flow` parameters are now just `flow`.

We now support customization of the deployment of your flow. Previously, we just uploaded the source code of the flow to a file. Now, we've designed a packaging systems which allows you to control how and where your flow is deployed. We're including three packagers in this release:

- `OrionPackager`: Serializes the flow and stores it in the Orion database, allowing you to get started without setting up remote storage.
- `FilePackager`: Serializes the flow and stores it in a file. The core library supports local and remote filesystems. Additional remote file systems will be available in collections.
- `DockerPackager`: Copies the flow into a new Docker image. You can take full control of the Docker image build or use Prefect to detect your current Python dependencies and install them in the image.

For packagers that support it, three serializers are available as well:

- `ImportSerializer`: Serializes to the import path of the flow. The flow will need to be importable at runtime.
- `SourceSerializer`: Serializes to the source code of the flow's module.
- `PickleSerializer`: Serializes the flow using cloudpickle with support for serialization full modules.

Learn more in the [Deployment concept documentation](https://docs.prefect.io/concepts/deployments/).

You can continue to use your existing `DeploymentSpec`s, but they are deprecated and will be removed in the coming weeks.

### Blocks
We've been working on Blocks behind the scenes for a while. Whether you know it or not, if you've used the past few releases, you've used them. Blocks enable you to securely store configuration with the Prefect Orion server and access it from your code later with just a simple reference. Think of Blocks as secure, UI-editable, type-checked environment variables. We're starting with just a few Blocks - mostly storage, but over time we’ll expand this pattern to include every tool and service in the growing modern data stack. You'll be able to set up access to your entire stack once in just a few minutes, then manage access forever without editing your code. In particular, we've made the following enhancements:
- Block document values can now be updated via the Python client with the `overwrite` flag.
- Blocks now support secret fields. By default, fields identified as secret will be obfuscated when returned to the Prefect UI. The actual values can still be retrieved as necessary.
-  `BlockSchema` objects have a new `secret_fields: List[str]` item in their schema's extra fields. This is a list of all fields that should be considered "secret". It also includes any secret fields from nested blocks referenced by the schema.
- You can now browse your Blocks on the new "Blocks" page, create, and edit them right in the UI.

### Other Improvements
- Task keys, previously a concatenation of several pieces of metadata, are now only the qualified function name. While it is likely to be globally unique, the key can be used to easily identify every instance in which a function of the same name is utilized.
- Tasks now have a `version` that you can set via the task decorator, like the flow version identifier on flow runs.
- An Orion setting, `PREFECT_ORION_DATABASE_PASSWORD`, has been added to allow templating in the database connection URL
- A link to API reference documentation has been added to the Orion startup message.
- Where possible, Prefect 2.0 now exits processes earlier for synchronous flow or task runs that are cancelled. This reduces the range of conditions under which a task run would be marked failed, but continue to run.
- All Prefect client models now allow extras, while the API continues to forbid them, such that older Prefect 2.0 clients can receive and load objects from the API that have additional fields, facilitating backwards compatibility.
- The _all_ attribute has been added to __init__.py for all public modules, declaring the public API for export.
- A new endpoint, `/deployments/{id}/work_queue_check`, enables you to to check which work queues the scheduled runs of a deployment will be eligible for.


### Bug fixes
- Attempting to create a schedule with a cron string that includes a "random" or "hashed" expression will now return an error.

### Contributors
- [Cole Murray](https://github.com/ColeMurray)
- [Oliver Mannion](https://github.com/tekumara)
- [Steve Flitcroft](https://github.com/redsquare)
- [Laerte Pereira](https://github.com/Laerte)

## 2.0b7

This release includes a number of important improvements and bug fixes in response to continued feedback from the community. Note that this release makes a **breaking change** to the Blocks API, making the `2.0b7` Orion server incompatible with previous Orion client versions.```

### Improvements
- Added the color select to the Orion UI in OSS (enabling users to change their state color scheme) for the UI.
- Added anonymous blocks, allowing Prefect to dynamically store blocks for you without cluttering your workspace.
- Performance improvements to the service that marks flows runs as late.
- Added the ability for flow names to include underscores for use in DeploymentSpecs.
- Split [Ray](https://prefecthq.github.io/prefect-ray/) and [Dask](https://prefecthq.github.io/prefect-dask/) task runners into their own collections.
- Removed delays to agent shutdown on keyboard interrupt.
- Added informative messaging when an agent is reading from a paused work queue.
- Improved task naming conventions for tasks defined using lambda functions

### Documentation improvements
- Updated screenshots and description of workflows to reflect new UI
- Revised and extended Prefect Cloud quickstart tutorial
- Added deployments page
- Added documentation for `prefect cloud workspace set` command

### Collections
- [prefect-sqlalchemy](https://prefecthq.github.io/prefect-sqlalchemy/)
- [prefect-dask](https://prefecthq.github.io/prefect-dask/)
- [prefect-ray](https://prefecthq.github.io/prefect-ray/)
- [prefect-snowflake](https://prefecthq.github.io/prefect-snowflake/)
- [prefect-openmetadata](https://prefecthq.github.io/prefect-openmetadata/)
- [prefect-airbyte](https://prefecthq.github.io/prefect-airbyte/)

Note that the Dask and Ray task runners have been moved out of the Prefect core library to reduce the number of dependencies we require for most use cases. Install from the command line with `pip install prefect-dask` and import with `from prefect_dask.task_runners import DaskTaskRunner`.

### Bug fixes
- [Allow Orion UI to run on Windows](https://github.com/PrefectHQ/prefect/pull/5802)
- Fixed a bug in terminal state data handling that caused timeouts
- Disabled flow execution during deployment creation to prevent accidental execution.
- Fixed a bug where Pydantic models being passed to Prefect tasks would drop extra keys and private attributes.
- Fixed a bug where the `KubernetesFlowRunner` was not serializable.

## 2.0b6

We're so grateful for the fountain of feedback we've received about Prefect 2. One of the themes in feedback was that Prefect 2's UI didn't reflect the same clarity and elegance that the rest of Prefect 2 did. We agreed! Today, we've proud to share Prefect 2's completely redesigned UI. It's simpler, faster, and easier to use. Give it a spin!

This release includes several other exciting changes, including:

- **Windows** support
- A new CLI command to delete flow runs: `prefect flow-run delete`
- Improved API error messages
- Support for type-checking with VS Code and other editors that look for a `py.typed` file

Here's a preview of the type hints that you'll start seeing now in editors like VS Code:

<img src="docs/img/release-notes/functionhint.png">

<img src="docs/img/release-notes/futurehint.png">

Note that this release makes a **breaking change** to the Blocks API, making the `2.0b6` Orion server incompatible with previous Orion client versions. You may not be familiar with Blocks, but it's likely that you have already used one in the `flow_storage` part of your `DeploymentSpec`. This change is foundational for powerful new features we're working on for upcoming releases. Blocks will make all sorts of exciting new use cases possible.

After the upgrade your data will remain intact, but you will need to upgrade to `2.0b6` to continue using the Cloud 2.0 API. You can upgrade in just a few simple steps:

-   Install the latest Prefect 2.0 python package: `pip install -U "prefect>=2.0b6"`
-   Restart any existing agent processes
	- If you are using an agent running on Kubernetes, update the Prefect image version to `2.0b6` in your Kubernetes manifest and re-apply the deployment.
	- You don't need to recreate any deployments or pause any schedules - stopping your agent process to perform an upgrade may result in some Late Runs, but those will be picked up once you restart your agent.

## 2.0b5

This release includes some small improvements that we want to deliver immediately instead of bundling them with the next big release.

The `prefect.testing` module is now correctly included in the package on PyPI.

The Prefect UI no longer uses a hard-coded API URL pointing at `localhost`. Instead, the URL is pulled from the `PREFECT_ORION_UI_API_URL` setting. This setting defaults to `PREFECT_API_URL` if set. Otherwise, the default URL is generated from `PREFECT_ORION_API_HOST` and `PREFECT_ORION_API_PORT`. If providing a custom value, the aforementioned settings may be templated into the given string.

## 2.0b4

We're really busy over here at Prefect! We've been getting great feedback from early adopters. There's a lot of work going on behind the scenes as we work on building some exciting new features that will be exclusive to Prefect 2.0, but we want to keep the enhancements flowing to you. In that spirit, there are a lot of quality-of-life improvements here!

While most of the development of Prefect 2.0 is still happening internally, we're incredibly excited to be getting contributions in our open source repository. Big shoutout to our contributors for this last release:

- @dannysepler
- @ColeMurray
- @albarrentine
- @mkarbo
- @AlessandroLollo


### Flow and task runners

- Flow runners now pass all altered settings to their jobs instead of just the API key and URL
- The Kubernetes flow runner supports configuration of a service account name
- The subprocess flow runner streams output by default to match the other flow runners
- The Dask task runner has improved display of task keys in the Dask dashboard
- The Dask task runner now submits the execution graph to Dask allowing optimization by the Dask scheduler

Note that the Dask and Ray task runners will be moving out of the core Prefect library into dedicated `prefect-ray` and `prefect-dask` collections with the next release. This will reduce the number of dependencies we require for most use cases. Since we now have concurrent execution built in to the core library, these packages do not need to be bundled with Prefect. We're looking forward to building additional tasks and flows specific to Ray and Dask in their respective collections.

### Collections

Speaking of collections, we've received our first [user-contributed collection](https://github.com/AlessandroLollo/prefect-cubejs). It includes tasks for [Cube.js](https://cube.dev/), check it out!

The following collections have also been recently released:

- [`prefect-great-expectations`](https://github.com/PrefectHQ/prefect-great-expectations)
- [`prefect-twitter`](https://github.com/PrefectHQ/prefect-twitter)
- [`prefect-github`](https://github.com/PrefectHQ/prefect-github)

You can see a list of all available collections in the [Prefect Collections Catalog](https://docs.prefect.io/collections/catalog/).

### Windows compatibility

We've excited to announce that we've begun work on Windows compatibility. Our full test suite isn't passing yet, but we have core features working on Windows. We expect the majority of the edge cases to be addressed in an upcoming release.

### Documentation improvements

We've added some new documentation and made lots of improvements to existing documentation and tutorials:

- Added documentation for associating conda environments with separate Prefect profiles
- Added storage steps and advanced examples to the Deployments tutorial
- Expanded documentation of storage options
- Added workspace details to the Prefect Cloud documentation
- Improved schedules documentation with examples
- Revised the Kubernetes tutorial to include work queue setup
- Improved tutorial examples of task caching

### CLI

- Deployments can be deleted from the CLI
- The CLI displays help by default
- `prefect version` is robust to server connection errors
- `prefect config view` shows sources by default
- `prefect deployment create` exits with a non-zero exit code if one of the deployments fails to be created
- `prefect config set` allows setting values that contain equal signs
- `prefect config set` validates setting types before saving them
- `prefect profile inpect` displays settings in a profile instead of duplicating prefect config view behavior
- `prefect storage create` trims long descriptions

### Bug squashing

We've eradicated some bugs, replacing them with good behavior:

- Flow runs are now robust to log worker failure
- Deployment creation is now robust to `ObjectAlreadyExists` errors
- Futures from async tasks in sync flows are now marked as synchronous
- Tildes (~) in user-provided paths for `PREFECT_HOME` are expanded
- Fixed parsing of deployments defined in YAML
- Deployment deletion cleans up scheduled runs

### Optimizations and refactors

You might not see these fixes in your day-to-day, but we're dedicated to improving performance and maintaining our reputation as maintainers of an approachable and clean project.

- The `state_name` is attached to run models for improved query performance
- Lifespan management for the ephemeral Orion application is now robust to deadlocks
- The `hello` route has moved out of the `admin` namespace so it is available on Prefect Cloud
- Improved readability and performance of profile management code
- Improved lower-bounds dependency parsing
- Tests are better isolated and will not run against a remote API
- Improved representation of Prefect `Setting` objects
- Added extensive tests for `prefect config` and `prefect profile` commands
- Moved testing utilities and fixtures to the core library for consumption by collections

## 2.0b3

### Improvements

- Improved filter expression display and syntax in the UI.
- Flow runs can be queried more flexibly and performantly.
- Improved results persistence handling.
- Adds code examples to schedules documentation.
- Added a unit testing utility, `prefect_test_harness`.
- Various documentation updates.

### Bug fixes

- The Scheduler no longer crashes on misconfigured schedules.
- The MarkLateRuns service no longer marks runs as `Late` several seconds too early.
- Dashboard filters including flow/task run states can now be saved.
- Flow runs can no longer transition from terminal states. The engine will no longer try to set the final state of a flow run twice.
- Scheduled flow runs are now deleted when their corresponding deployment is deleted.
- Work queues created in the UI now work the same as those created with the CLI.
- Kubernetes flow runners now correctly inject credentials into the execution environment.
- Work queues created via the UI now function correctly.

## 2.0b2


### Improvements

- Docker flow runners can connect to local API applications on Linux without binding to `0.0.0.0`.
- Adds `with_options` method to flows allowing override of settings e.g. the task runner.

### Bug fixes

- The CLI no longer displays tracebacks on sucessful exit.
- Returning pandas objects from tasks does not error.
- Flows are listed correctly in the UI dashboard.

## 2.0b1

We are excited to introduce this branch as [Prefect 2.0](https://www.prefect.io/blog/introducing-prefect-2-0/), powered by [Orion, our second-generation orchestration engine](https://www.prefect.io/blog/announcing-prefect-orion/)! We will continue to develop Prefect 2.0 on this branch. Both the Orion engine and Prefect 2.0 as a whole will remain under active development in beta for the next several months, with a number of major features yet to come.

This is the first release that's compatible with Prefect Cloud 2.0's beta API - more exciting news to come on that soon!

### Expanded UI
Through our technical preview phase, our focus has been on establishing the right [concepts](https://docs.prefect.io/concepts/overview/) and making them accessible through the CLI and API. Now that some of those concepts have matured, we've made them more accessible and tangible through UI representations. This release adds some very important concepts to the UI:

**Flows and deployments**

If you've ever created a deployment without a schedule, you know it can be difficult to find that deployment in the UI. This release gives flows and their deployments a dedicated home on the growing left sidebar navigation. The dashboard continues to be the primary interface for exploring flow runs and their task runs.

**Work queues**

With the [2.0a13 release](https://github.com/PrefectHQ/prefect/blob/orion/RELEASE-NOTES.md#work-queues), we introduced [work queues](https://docs.prefect.io/concepts/work-queues/), which could only be created through the CLI. Now, you can create and edit work queues directly from the UI, then copy, paste, and run a command that starts an agent that pulls work from that queue.

### Collections
Prefect Collections are groupings of pre-built tasks and flows used to quickly build data flows with Prefect.

Collections are grouped around the services with which they interact. For example, to download data from an S3 bucket, you could use the `s3_download` task from the [prefect-aws collection](https://github.com/PrefectHQ/prefect-aws), or if you want to send a Slack message as part of your flow you could use the `send_message` task from the [prefect-slack collection](https://github.com/PrefectHQ/prefect-slack).

By using Prefect Collections, you can reduce the amount of boilerplate code that you need to write for interacting with common services, and focus on the outcome you're seeking to achieve. Learn more about them in [the docs](https://docs.prefect.io/collections/catalog.md).

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

Check out the [work queue documentation](https://docs.prefect.io/concepts/work-queues/) for more details.

Note, `prefect agent start` now requires you to pass a work queue identifier and `prefect orion start` no longer starts an agent by default.

### Remote storage

Prior to this release, the Orion server would store your flow code and results in its local file system. Now, we've introduced storage with external providers including AWS S3, Google Cloud Storage, and Azure Blob Storage.

There's an interactive command, `prefect storage create`, which walks you through the options required to configure storage. Your settings are encrypted and stored in the Orion database.

Note that you will no longer be able to use the Kubernetes or Docker flow runners without configuring storage. While automatically storing flow code in the API was convenient for early development, we're focused on enabling the [hybrid model](https://www.prefect.io/why-prefect/hybrid-model/) as a core feature of Orion.

### Running tasks on Ray

We're excited to announce a new task runner with support for [Ray](https://www.ray.io/). You can run your tasks on an existing Ray cluster, or dynamically create one with each flow run. Ray has powerful support for customizing runtime environments, parallelizing tasks to make use of your full compute power, and dynamically creating distributed task infrastructure.

An [overview of using Ray](https://docs.prefect.io/concepts/task-runners/#running-tasks-on-ray) can be found in our documentation.

### Profiles

Prefect now supports profiles for configuration. You can store settings in profiles and switch between them. For example, this allows you to quickly switch between using a local and hosted API.

View all of the available commands with `prefect config --help` and check out our [settings documentation](https://docs.prefect.io/concepts/settings/) for a full description of how to use profiles.

We've also rehauled our [settings reference](https://docs.prefect.io/api-ref/prefect/settings/#prefect.settings.Settings) to make it easier to see all the available settings. You can override any setting with an environment variable or `prefect config set`.

## 2.0a12

### Filters
Orion captures valuable metadata about your flows, deployments, and their runs. We want it to be just as simple to retrieve this information as it is to record it. This release exposes a powerful set of filter operations to cut through this body of information with ease and precision. Want to see all of the runs of your Daily ETL flow? Now it's as easy as typing `flow:"Daily ETL"` into the filter bar. This update also includes a query builder UI, so you can utilize and learn these operators quickly and easily.

## 2.0a11

### Run Orion on Kubernetes
You can now can run the Orion API, UI, and agent on Kubernetes. We've included a new Prefect CLI command, `prefect kubernetes manifest orion`, that you can use to automatically generate a manifest that runs Orion as a Kubernetes deployment.

Note: Prefect 2.0 beta versions prior to 2.0b6 used the CLI command `prefect orion kubernetes-manifest`.

### Run flows on Kubernetes

With the `KubernetesJob` [infrastructure](https://orion-docs.prefect.io/concepts/infrastructure/), you can now run flows as Kubernetes Jobs. You may specify the Kubernetes flow runner when creating a deployment. If you're running Orion in Kubernetes, you don't need to configure any networking. When the agent runs your deployment, it will create a job, which will start a pod, which creates a container, which runs your flow. You can use standard Kubernetes tooling to display flow run jobs, e.g. `kubectl get jobs -l app=orion`.

## 2.0a10

### Concurrent task runner

Speed up your flow runs with the new Concurrent Task Runner. Whether your code is synchronous or asynchronous, this [task runner](https://docs.prefect.io/concepts/task-runners/) will enable tasks that are blocked on input/output to yield to other tasks. To enable this behavior, this task runner always runs synchronous tasks in a worker thread, whereas previously they would run in the main thread.

### Task run concurrency limits

When running a flow using a task runner that enables concurrent execution, or running many flows across multiple execution environments, you may want to limit the number of certain tasks that can run at the same time.

Concurrency limits are set and enforced with task run tags. For example, perhaps you want to ensure that, across all of your flows, there are no more than three open connections to your production database at once. You can do so by creating a “prod-db” tag and applying it to all of the tasks that open a connection to that database. Then, you can create a concurrency limit with `prefect concurrency-limit create prod-db 3`. Now, Orion will ensure that no more than 3 task runs with the “prod-db” tag will run at the same time. Check out [the documentation](https://docs.prefect.io/concepts/tasks/) for more information about task run concurrency limits and other task level concepts.

This feature was previously only available in a paid tier of Prefect Cloud, our hosted commercial offering. We’re very happy to move it to the open source domain, furthering our goal of making Orion the most capable workflow orchestration tool ever.

### Flow parameters

Previously, when calling a flow, we required passed arguments to be serializable data types. Now, flows will accept arbitrary types, allowing ad hoc flow runs and subflow runs to consume unserializable data types. This change is motivated by two important use-cases:

- The flow decorator can be added to a wider range of existing Python functions
- Results from tasks can be passed directly into subflows without worrying about types

Setting flow parameters via the API still requires serializable data so we can store your new value for the parameter. However, we support automatic deserialization of those parameters via type hints. See the [parameters documentation](https://docs.prefect.io/concepts/flows/#parameters) for more details.

### Database migrations

The run metadata that Orion stores in its database is a valuable record of what happened and why. With new database migrations for both SQLite and PostgreSQL, you can retain your data when upgrading. The CLI interface has been updated to include new commands and revise an existing command to leverage these migrations:

- `prefect orion reset-db` is now `prefect orion database reset`
- `prefect orion database upgrade` runs upgrade migrations
- `prefect orion database downgrade` runs downgrade migrations

**Breaking Change**
Because these migrations were not in place initially, if you have installed any previous version of Orion, you must first delete or stamp the existing database with `rm ~/.prefect/orion.db` or `prefect orion database stamp`, respectively. Learn more about database migrations in [the documentation](https://docs.prefect.io/tutorials/orchestration/#the-database).

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
Learn more about logging in [the docs](https://docs.prefect.io/concepts/logs/).

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

[Executors](https://docs.prefect.io/concepts/executors/) are the key building blocks that enable you to execute code in parallel, on other machines, or with other engines.

### Dask integration

Those of you already familiar with Prefect have likely used our Dask executor.
The first release of Orion came with a Dask executor that could run simple local clusters.
This allowed tasks to run in parallel, but did not expose the full power of Dask.
In this release of Orion, we've reached feature parity with the existing Dask executor.
You can [create customizable temporary clusters](https://docs.prefect.io/tutorials/dask-task-runner/) and [connect to existing Dask clusters](https://docs.prefect.io/tutorials/dask-task-runner/).
Additionally, because flows are not statically registered, we're able to easily expose Dask annotations, which allow you to [specify fine-grained controls over the scheduling of your tasks](https://docs.prefect.io/tutorials/dask-task-runner/) within Dask.


### Subflow executors

[Subflow runs](https://docs.prefect.io/concepts/flows/#composing-flows) are a first-class concept in Orion and this enables new execution patterns.
For example, consider a flow where most of the tasks can run locally, but for some subset of computationally intensive tasks you need more resources.
You can move your computationally intensive tasks into their own flow, which uses a `DaskExecutor` to spin up a temporary Dask cluster in the cloud provider of your choice.
Next, you simply call the flow that uses a `DaskExecutor` from your other, parent flow.
This pattern can be nested or reused multiple times, enabling groups of tasks to use the executor that makes sense for their workload.

Check out our [multiple executor documentation](https://docs.prefect.io/concepts/executors/#using-multiple-task-runners) for an example.


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
