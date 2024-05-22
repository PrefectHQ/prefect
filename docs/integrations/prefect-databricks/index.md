# prefect-databricks

Prefect integrations for interacting with Databricks

The tasks within this collection were created by a code generator using the service's OpenAPI spec.

The service's REST API documentation can be found [here](https://docs.databricks.com/dev-tools/api/latest/index.html).

## Getting started

### Prerequisites

- [Prefect installed](https://docs.prefect.io/latest/getting-started/installation/) in a virtual environment.
- A [Databricks account](https://databricks.com/) and the necessary permissions to access desired services.

### Install `prefect-databricks`

<div class="terminal">
```bash
pip install prefect-databricks
```
</div>

### List jobs on the Databricks instance

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

## Resources

For assistance using Databricks, consult the [Databricks documentation](https://www.databricks.com/databricks-documentation).

Refer to the prefect-databricks API documentation linked in the sidebar to explore all the capabilities of the prefect-databricks library.
