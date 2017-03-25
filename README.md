# Prefect

Prefect is a brand-new workflow manager.

Users create `tasks` that are organized in `flows`, and Prefect makes sure they run.

## Core Ideas

Tasks can exchange data to facilitate processing pipelines.

Prefect flows are fully dynamic. New tasks (and even new flows) can be generated at any time, even in the middle of execution. In addition, flows can be parameterized at runtime.

Flows can be run on a schedule, but Prefect will happily execute them on-demand or even in a "long-running" mode that has limited support for streaming workflows. In fact, most Prefect components, like its scheduler, are actually run as Prefect flows.

GUI is responsive

## Instructions
*Don't Panic*

Prefect is a brand new project. Much of it has yet to be written, so the API should be considered experimental and subject to change without warning.


## "...Prefect?"

From the Latin *praefectus*, meaning "one who is in charge", a prefect is an official who oversees a domain and ensures that the rules are followed.

It also happens to be the name of a roving researcher for that wholly remarkable book, *The Hitchhiker's Guide to the Galaxy*.


## Requirements

Prefect requires Python 3.5+

## Installation

To install Prefect for development:
```bash
git clone https://gitlab.com/jlowin/prefect.git
pip install -e ./prefect
```

## Comparison to Other Projects

### Airflow
Airflow is a wonderful and mature workflow manager, and the author of Prefect is a PMC member and committer of the [Apache Airflow](https://github.com/apache/incubator-airflow) project. Prefect is a brand-new project that shares no code and is not compatible with Airflow.

Airflow is used in production by hundreds of companies because it combines a best-in-class batch scheduler with an informative web interface and easy job ("DAG") authoring tools.

However, it has limited support for ad-hoc (off-schedule) jobs. DAGs must remain static and can not be parameterized. DAGs and tasks can not be generated dynamically. Data is not passed between tasks.

Rewriting Airflow to support more modern, flexible workflows is an enormous task. Prefect was started because it seemed simpler to start from scratch.

At this time, Prefect is very immature and users should prefer Airflow.

### Dask
[Dask](http://dask.pydata.org) and its [Distributed](http://distributed.readthedocs.io/en/latest/) subproject represent state-of-the-art for distributed computation in Python (or any language).

Distributed is a core part of Prefect, and Prefect users should be running a Distributed cluster. However, Prefect uses a different execution model than Distributed.

Distributed expects a chain of functions where the result of each successful function is passed to the next function in the chain. Prefect expects a flow of tasks where each task runs when the tasks before it meet a certain criteria (including failure). Prefect tasks *can* exchange data but it is not expected. In addition to this different trigger model, Prefect handles task management (like retries and timeouts) as well as a database for maintaining state and a GUI for monitoring and launching flows.

If a user simply wants to submit functions to the cluster for distributed execution, then Prefect will be overkill. However, a Prefect task could be used to store or schedule that submission.

### Spark
[Spark](http://spark.apache.org/) is a powerful distributed computing project similar in many ways to Dask -- see [this comparison](http://dask.pydata.org/en/latest/spark.html) for more detail. Like Dask, Spark serves a different purpose than Prefect even though they share a similar concept of chaining functions together. Prefect can be used to schedule and run Spark jobs, but it wouldn't replace those jobs themselves.

## Unit Tests
To simply run tests (note some tests will require a database):
1. Execute: `pytest`

To run tests exactly as they are run in GitLab CI (including all databases and infrastructure):
1. Install the [GitLab CI Runner](https://docs.gitlab.com/runner/install/index.html)
1. Install [Docker](https://docs.docker.com/engine/installation/) and start the Docker Engine
1. Execute: `gitlab-runner exec docker test`
