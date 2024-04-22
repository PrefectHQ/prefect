# prefect-databricks

Visit the full docs [here](https://PrefectHQ.github.io/prefect-databricks) to see additional examples and the API reference.
 
<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-databricks/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-databricks?color=0052FF&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-databricks/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-databricks?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/PrefectHQ/prefect-databricks/pulse" alt="Activity">
</p>

## Welcome!

Prefect integrations for interacting with Databricks

The tasks within this collection were created by a code generator using the service's OpenAPI spec.

The service's REST API documentation can be found [here](https://docs.databricks.com/dev-tools/api/latest/index.html).

## Getting Started

### Python setup

Requires an installation of Python 3.7+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://orion-docs.prefect.io/).

### Installation

Install `prefect-databricks` with `pip`:

```bash
pip install prefect-databricks
```

A list of available blocks in `prefect-databricks` and their setup instructions can be found [here](https://PrefectHQ.github.io/prefect-databricks/#blocks-catalog).

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

For more tips on how to use tasks and flows in a Collection, check out [Using Collections](https://orion-docs.prefect.io/collections/usage/)!

## Resources

If you encounter any bugs while using `prefect-databricks`, feel free to open an issue in the [prefect-databricks](https://github.com/PrefectHQ/prefect-databricks) repository.

If you have any questions or issues while using `prefect-databricks`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

Feel free to star or watch [`prefect-databricks`](https://github.com/PrefectHQ/prefect-databricks) for updates too!

## Contributing

If you'd like to help contribute to fix an issue or add a feature to `prefect-databricks`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Here are the steps:
1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Insert an entry to [CHANGELOG.md](https://github.com/PrefectHQ/prefect-databricks/blob/main/CHANGELOG.md)
7. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
8. `git commit`, `git push`, and create a pull request
