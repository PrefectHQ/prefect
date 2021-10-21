# FAQ

[[toc]]

### Does Prefect have a UI, and if so, how can I use it?

The Prefect Cloud platform includes a UI for monitoring and managing any workflows you build with Prefect Core. You can kick off new runs, get live-updating states, browse workflow structures, stream logs, and more.

You can sign up for a free Cloud account [right here](https://www.prefect.io/download) or check out the [UI docs](/orchestration/ui/dashboard.html) if you're only curious.

### What is the difference between Prefect Core and Prefect Cloud?

[Prefect Core](https://github.com/PrefectHQ/prefect) is a complete package for building, testing and executing workflows locally. For some use cases, this is sufficient functionality. However, many people quickly begin looking for features related to monitoring, observability, multi-flow orchestration and persistence. This is where Prefect Cloud comes into play - Cloud is designed as a complete distributed orchestration and monitoring service for your Prefect Core workflows. Cloud offers such features as a database for your states, a secure GraphQL API, a UI, among many other things. Note that our "Hybrid" Cloud Architecture allows Prefect to orchestrate and monitor your workflows [without requiring access to your personal code or data](/orchestration/faq/dataflow.html).

### Is using Dask a requirement of Prefect?

No - Dask is our preferred executor for distributed and parallelizable workflows, but running your workflows on Dask is _not_ a requirement. [Any of Prefect's executors](/api/latest/executors.html) are available for use during deployment, and we are always interested in adding new ones.

### What are the requirements of Prefect Cloud?

Prefect Cloud currently requires that all flows are containerized using [Docker](https://www.docker.com). Extensive knowledge of Docker is not required, and Prefect Core has many convenient interfaces and utility functions for interacting with Docker. Your Prefect agent also requires access to a platform which is capable of running Docker containers. In addition to Docker, your Prefect Agent needs the ability to communicate _out_ to Cloud (but not the other way around - Prefect Cloud _never_ requires access to your code, data or infrastructure).

Other than the Python dependencies of Prefect Core, there are no additional requirements for registering flows with Prefect Cloud.

### How is Prefect different from Airflow?

For some of the main distinctions, see our blogpost: [Why Not Airflow?](https://medium.com/the-prefect-blog/why-not-airflow-4cfa423299c4).

### How can I include non-Python tasks in a Prefect flow?

Ultimately, Python is Prefect's API; consequently, to run a process external to Python requires using Python to call out to an external "system" to run the particular task. Some common ways to call out to external, non-Python dependencies include:

- subprocess calls
- running / interacting with Docker containers
- running / interacting with Kubernetes Jobs
- using an established Python API / SDK (e.g. `pyspark`)

### Is Cloud a fully managed service? / Where does Cloud run?

We have developed an innovative "hybrid" model for Prefect Cloud - it is probably more accurate to think of Prefect Cloud as "on-prem lite". Prefect Cloud hosts a database and associated services which are responsible for tracking _metadata_ about your flows and tasks. The actual execution of your workflows occurs in _your infrastructure_, and is orchestrated through your Prefect agent.

::: tip Prefect Cloud requires no access to your infrastructure
Surprisingly, Prefect Cloud requires _no access_ to your infrastructure or code. Information and communication is always initiated in one direction - _from_ your agent and workflows _to_ Cloud, but never the other way around. To better understand how data is managed, please see our write-up on [Cloud Dataflow](/orchestration/faq/dataflow.html).
:::

### How does the Prefect Scheduler work?

There are two distinct "implementations" of the scheduler:

- the Prefect Core standalone version: this "scheduler" is more of a convenience method than a real scheduler. It can be triggered by calling `flow.run()` on a Prefect `Flow` object. If the flow has no schedule, a run will begin immediately. Otherwise, the process will block until the next scheduled time has been reached.
- the Prefect Cloud scheduler service: this horizontally-scalable service is responsible for one thing: creating "Scheduled" states for flows which are then picked up by your Prefect agent and submitted for execution (at the appropriate time). These Scheduled states are created in two distinct ways:
  - anytime a user creates a flow run manually, e.g., when calling the [`create_flow_run` GraphQL mutation](/orchestration/concepts/flow_runs.html#graphql)
  - the scheduler is constantly scanning the database looking for flows with active schedules; anytime one is found that hasn't been processed recently, the next 10 runs are scheduled via the creation of `Scheduled` states

Note that regardless of which scheduler is being used, dependencies between Prefect tasks typically _do not involve a scheduler_; rather, the executor being used for the flow run handles when each dependency is finished and the next can begin.

::: tip In Cloud, flow.run() is never called
As previously stated, `flow.run` is purely a convenience method for running your Flows on schedule locally and testing flow execution locally. When the Prefect agent submits a flow for execution, a `CloudFlowRunner` is created and interacted with directly.
:::

### Do you have an integration for service X?

Yes! Prefect can integrate with any service and we have a [growing library](../core/task_library/overview.html) of pre-built tasks for working with internal and external services.

People sometimes mistake the library for an inclusive list of possible "integrations". While our Task Library will help you save time writing custom code for a particular service, remember that Prefect is completely agnostic what your tasks do. If the Task Library doesn't have a service that you use, you can write it yourself. You could even contribute your code back to the library to help others!

The same holds true for alerting and metrics collection services - a common way of hooking into these is through the use of Prefect state handlers or logging handlers, which can be completely customized with your own logic and code.

### Does Prefect support backfills?

Yes! Because Prefect makes no assumptions about the relationship of your workflow to time, performing a backfill depends largely on the nature of your workflow. If one of your tasks is responsive to time (e.g., a templated SQL query), it is best practice to rely on _either_ Prefect [`Parameters`](../core/concepts/parameters.html) or Prefect [`Context`](../core/concepts/execution.html#context) for inferring time-based information. Because both parameters and context values can be provided on an individual run basis, performing a backfill is as simple as looping over the desired values and creating individual flow runs for each value.
