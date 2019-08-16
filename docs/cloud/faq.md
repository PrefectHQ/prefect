# Prefect Cloud FAQ

[[toc]]

### Does Prefect have a UI, and if so, how can I use it?

Prefect absolutely has a User Interface (UI).  The [Prefect Core Engine](https://github.com/PrefectHQ/prefect) is designed for building and testing your Prefect workflows locally, and consequently does not require a database or any other sort of monitoring service running (which is what any UI _requires_ in order to expose stateful information!).  Prefect Cloud is our recommended persistent orchestration layer for monitoring and orchestrating workflows in a production setting, and the Cloud API is what drives our UI. To gain access to Cloud, please [contact us](https://www.prefect.io/lighthouse-partners).

### Is using Dask a requirement of Prefect?

No - Dask is our preferred executor for distributed and parallelizable workflows, but running your workflows on Dask is _not_ a requirement.  [Any of Prefect's executors](https://docs.prefect.io/api/unreleased/engine/executors.html) are available for use in deployment, and we are always interested in adding new ones.

### How is Prefect different from Airflow?

For some of the main distinctions, see our blogpost: [Why Not Airflow?](https://medium.com/the-prefect-blog/why-not-airflow-4cfa423299c4).

### How can I include non-Python Tasks in a Prefect Flow?

Ultimately, Python is Prefect's API; consequently, to run a process external to Python requires using Python to call out to an external "system" to run the particular task.  Some common ways to call out to external, non-Python dependencies include:
- subprocess calls
- running / interacting with Docker containers
- running / interacting with Kubernetes Jobs
- using an established Python API / SDK (e.g. `pyspark`)

### Is Cloud a fully managed service? / Where does Cloud run?

We have developed an innovative "hybrid" model for Prefect Cloud - it is probably more accurate to think of Prefect Cloud as "on-prem lite".  Prefect Cloud hosts a database and associated services which are responsible for tracking _metadata_ about your Flows and Tasks.  The actual execution of your workflows occurs in _your infrastructure_, and is orchestrated through your Prefect Agent.  

::: tip Prefect Cloud requires no access to your infrastructure
Surprisingly, Prefect Cloud requires _no access_ to your infrastructure or code.  Information and communication flows in one direction - _from_ your Agent and workflows _to_ Cloud, but never the other way around. To better understand how data is managed, please see our write-up on [Cloud Dataflow](dataflow.html).
:::

### Is there a fully on-prem version of Prefect Cloud?

Yes - please [contact us](https://www.prefect.io/lighthouse-partners) for details.

### How does the Prefect Scheduler work?

There are two distinct "implementations" of the scheduler:

- the Prefect Core standalone version: this "scheduler" is more of a convenience method than a real scheduler.  It can be triggered by calling `flow.run()` on a Prefect Flow object.  If the Flow has no schedule, a run will begin immediately.  Otherwise, the process will block until the next scheduled time has been reached. 
- the Prefect Cloud scheduler service: this horizontally-scalable service is responsible for one thing: creating "Scheduled" states for Flows which are then picked up by your Prefect Agent and submitted for execution (at the appropriate time).  These Scheduled states are created in two distinct ways:
    - anytime a user creates a Flow Run manually, e.g., when calling the [`createFlowRun` GraphQL mutation](cloud_concepts/flow_runs.html#creating-a-flow-run)
    - the scheduler is constantly scanning the database looking for Flows with active schedules; anytime one is found that hasn't been processed recently, the next 10 runs are scheduled via the creation of `Scheduled` states

Note that regardless of which scheduler is being used, dependencies between Prefect Tasks typically _do not involve a scheduler_; rather, the executor being used for the flow run handles when each dependency is finished and the next can begin.

::: tip In Cloud, flow.run() is never called
As previously stated, `flow.run` is purely a convenience method for running your Flows on schedule locally and testing your Flow execution locally.  When the Prefect Agent submits a Flow for execution, a `CloudFlowRunner` is created and interacted with directly.
:::
