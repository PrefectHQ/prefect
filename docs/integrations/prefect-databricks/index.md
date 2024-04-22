# prefect-databricks
 
<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-databricks/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-databricks?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/PrefectHQ/prefect-databricks/" alt="Stars">
        <img src="https://img.shields.io/github/stars/PrefectHQ/prefect-databricks?color=0052FF&labelColor=090422" /></a>
    <a href="https://pepy.tech/badge/prefect-databricks/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-databricks?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/PrefectHQ/prefect-databricks/pulse" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/PrefectHQ/prefect-databricks?color=0052FF&labelColor=090422" /></a>
    <br>
    <a href="https://prefect-community.slack.com" alt="Slack">
        <img src="https://img.shields.io/badge/slack-join_community-red.svg?color=0052FF&labelColor=090422&logo=slack" /></a>
    <a href="https://discourse.prefect.io/" alt="Discourse">
        <img src="https://img.shields.io/badge/discourse-browse_forum-red.svg?color=0052FF&labelColor=090422&logo=discourse" /></a>
</p>

## Welcome!

Prefect integrations for interacting with Databricks

The tasks within this collection were created by a code generator using the service's OpenAPI spec.

The service's REST API documentation can be found [here](https://docs.databricks.com/dev-tools/api/latest/index.html).

## Getting Started

### Python setup

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Installation

Install `prefect-databricks` with `pip`:

```bash
pip install prefect-databricks
```

### Lists jobs on the Databricks instance

```python
from prefect import flow
from prefect_databricks import DatabricksCredentials
from prefect_databricks.jobs import jobs_list


@flow
def example_execute_endpoint_flow():
    databricks_credentials = DatabricksCredentials.load("my-block")
    jobs = jobs_list(
        databricks_credentials,
        limit=5
    )
    return jobs

example_execute_endpoint_flow()
```

### Use `with_options` to customize options on any existing task or flow

```python
custom_example_execute_endpoint_flow = example_execute_endpoint_flow.with_options(
    name="My custom flow name",
    retries=2,
    retry_delay_seconds=10,
)
```

### Launch a new cluster and run a Databricks notebook

Notebook named `example.ipynb` on Databricks which accepts a name parameter:

```python
name = dbutils.widgets.get("name")
message = f"Don't worry {name}, I got your request! Welcome to prefect-databricks!"
print(message)
```

Prefect flow that launches a new cluster to run `example.ipynb`:

```python
from prefect import flow
from prefect_databricks import DatabricksCredentials
from prefect_databricks.jobs import jobs_runs_submit
from prefect_databricks.models.jobs import (
    AutoScale,
    AwsAttributes,
    JobTaskSettings,
    NotebookTask,
    NewCluster,
)


@flow
def jobs_runs_submit_flow(notebook_path, **base_parameters):
    databricks_credentials = DatabricksCredentials.load("my-block")

    # specify new cluster settings
    aws_attributes = AwsAttributes(
        availability="SPOT",
        zone_id="us-west-2a",
        ebs_volume_type="GENERAL_PURPOSE_SSD",
        ebs_volume_count=3,
        ebs_volume_size=100,
    )
    auto_scale = AutoScale(min_workers=1, max_workers=2)
    new_cluster = NewCluster(
        aws_attributes=aws_attributes,
        autoscale=auto_scale,
        node_type_id="m4.large",
        spark_version="10.4.x-scala2.12",
        spark_conf={"spark.speculation": True},
    )

    # specify notebook to use and parameters to pass
    notebook_task = NotebookTask(
        notebook_path=notebook_path,
        base_parameters=base_parameters,
    )

    # compile job task settings
    job_task_settings = JobTaskSettings(
        new_cluster=new_cluster,
        notebook_task=notebook_task,
        task_key="prefect-task"
    )

    run = jobs_runs_submit(
        databricks_credentials=databricks_credentials,
        run_name="prefect-job",
        tasks=[job_task_settings]
    )

    return run


jobs_runs_submit_flow("/Users/username@gmail.com/example.ipynb", name="Marvin")
```

Note, instead of using the built-in models, you may also input valid JSON. For example, `AutoScale(min_workers=1, max_workers=2)` is equivalent to `{"min_workers": 1, "max_workers": 2}`.