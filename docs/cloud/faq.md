# Prefect FAQ

[[toc]]

### Does Prefect have a UI, and if so, how can I use it?

Prefect absolutely has a User Interface (UI). The [Prefect Core Engine](https://github.com/PrefectHQ/prefect) is designed for building and testing your Prefect workflows locally, and consequently does not require a database or any other sort of monitoring service running (which is what any UI _requires_ in order to expose stateful information!). Prefect Cloud is our recommended persistent orchestration layer for monitoring and orchestrating workflows in a production setting, and the Cloud API is what drives our UI. To gain access to Cloud, please [contact us](https://www.prefect.io/lighthouse-partners).

### What is the difference between Prefect Core and Prefect Cloud?

[Prefect Core](https://github.com/PrefectHQ/prefect) is a complete package for building, testing and executing workflows locally.  For some use cases, this is sufficient functionality. However, many people quickly begin looking for features related to monitoring, observability, multi-flow orchestration and persistence.  This is where Prefect Cloud comes into play - Cloud is designed as a complete distributed orchestration and monitoring service for your Prefect Core workflows.  Cloud offers such features as a database for your states, a secure GraphQL API, a UI, among many other things.  Note that our "Hybrid" Cloud Architecture allows Prefect to orchestrate and monitor your workflows [without requiring access to your personal code or data](dataflow.html).

### Is using Dask a requirement of Prefect?

No - Dask is our preferred executor for distributed and parallelizable workflows, but running your workflows on Dask is _not_ a requirement. [Any of Prefect's executors](https://docs.prefect.io/api/unreleased/engine/executors.html) are available for use in deployment, and we are always interested in adding new ones.

### What are the requirements of Prefect Cloud?

Prefect Cloud currently requires that all Flows are containerized using [Docker](https://www.docker.com). Extensive knowledge of Docker is not required, and Prefect Core has many convenient interfaces and utility functions for interacting with Docker.  Your Prefect Agent also requires access to a platform which is capable of running Docker containers.  In addition to Docker, your Prefect Agent needs the ability to communicate _out_ to Cloud (but not the other way around - Prefect Cloud _never_ requires access to your code, data or infrastructure).

Other than the python dependencies of Prefect Core, there are no additional requirements for deploying Flows to Prefect Cloud.

### How is Prefect different from Airflow?

For some of the main distinctions, see our blogpost: [Why Not Airflow?](https://medium.com/the-prefect-blog/why-not-airflow-4cfa423299c4).

### How can I include non-Python Tasks in a Prefect Flow?

Ultimately, Python is Prefect's API; consequently, to run a process external to Python requires using Python to call out to an external "system" to run the particular task. Some common ways to call out to external, non-Python dependencies include:

- subprocess calls
- running / interacting with Docker containers
- running / interacting with Kubernetes Jobs
- using an established Python API / SDK (e.g. `pyspark`)

### Is Cloud a fully managed service? / Where does Cloud run?

We have developed an innovative "hybrid" model for Prefect Cloud - it is probably more accurate to think of Prefect Cloud as "on-prem lite". Prefect Cloud hosts a database and associated services which are responsible for tracking _metadata_ about your Flows and Tasks. The actual execution of your workflows occurs in _your infrastructure_, and is orchestrated through your Prefect Agent.

::: tip Prefect Cloud requires no access to your infrastructure
Surprisingly, Prefect Cloud requires _no access_ to your infrastructure or code. Information and communication is always initiated in one direction - _from_ your Agent and workflows _to_ Cloud, but never the other way around. To better understand how data is managed, please see our write-up on [Cloud Dataflow](dataflow.html).
:::

### How does the Prefect Scheduler work?

There are two distinct "implementations" of the scheduler:

- the Prefect Core standalone version: this "scheduler" is more of a convenience method than a real scheduler. It can be triggered by calling `flow.run()` on a Prefect Flow object. If the Flow has no schedule, a run will begin immediately. Otherwise, the process will block until the next scheduled time has been reached.
- the Prefect Cloud scheduler service: this horizontally-scalable service is responsible for one thing: creating "Scheduled" states for Flows which are then picked up by your Prefect Agent and submitted for execution (at the appropriate time). These Scheduled states are created in two distinct ways:
  - anytime a user creates a Flow Run manually, e.g., when calling the [`createFlowRun` GraphQL mutation](concepts/flow_runs.html#creating-a-flow-run)
  - the scheduler is constantly scanning the database looking for Flows with active schedules; anytime one is found that hasn't been processed recently, the next 10 runs are scheduled via the creation of `Scheduled` states

Note that regardless of which scheduler is being used, dependencies between Prefect Tasks typically _do not involve a scheduler_; rather, the executor being used for the flow run handles when each dependency is finished and the next can begin.

::: tip In Cloud, flow.run() is never called
As previously stated, `flow.run` is purely a convenience method for running your Flows on schedule locally and testing your Flow execution locally. When the Prefect Agent submits a Flow for execution, a `CloudFlowRunner` is created and interacted with directly.
:::

### Do you have an integration for service X?

Yes! Prefect can integrate with any service and we have a growing Task Library of pre-built tasks for working with internal and external services.

People sometimes mistake the library for an inclusive list of possible "integrations". While our Task Library will help you save time writing custom code for a particular service, remember that Prefect is completely agnostic what your tasks do. If the Task Library doesn't have a service that you use, you can write it yourself. You could even contribute your code back to the library to help others!

The same holds true for alerting and metrics collection services - a common way of hooking into these is through the use of Prefect state handlers or logging handlers, which can be completely customized with your own logic and code.

### Does Prefect support backfills?

Yes! Because Prefect makes no assumptions about the relationship of your workflow to time, performing a backfill depends largely on the nature of your workflow.  If one of your tasks is responsive to time (e.g., a templated SQL query), it is best practice to rely on _either_ Prefect [Parameters](../core/concepts/parameters.html) or Prefect [Context](../core/concepts/execution.html#context) for inferring time-based information.  Because both Parameters and Context values can be provided on an individual run basis, performing a backfill is as simple as looping over the desired values and creating individual flow runs for each value.
