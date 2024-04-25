# prefect-dbt

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-dbt/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-dbt?color=26272B&labelColor=090422"></a>0
    <a href="https://pepy.tech/badge/prefect-dbt/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-dbt?color=26272B&labelColor=090422" /></a>
</p>

With prefect-dbt, you can easily trigger and monitor dbt Cloud jobs, execute dbt Core CLI commands, and incorporate other services, like Snowflake, into your dbt runs!

Check out the examples below to get started!

## Getting Started

Be sure to install [prefect-dbt](#installation) and [save a block](#saving-credentials-to-block) to run the examples below!

### Integrate dbt Cloud jobs with Prefect flows

If you have an existing dbt Cloud job, take advantage of the flow, `run_dbt_cloud_job`.

This flow triggers the job and waits until the job run is finished.

If certain nodes fail, `run_dbt_cloud_job` efficiently retries the specific, unsuccessful nodes.

```python
from prefect import flow

from prefect_dbt.cloud import DbtCloudJob
from prefect_dbt.cloud.jobs import run_dbt_cloud_job

@flow
def run_dbt_job_flow():
    result = run_dbt_cloud_job(
        dbt_cloud_job=DbtCloudJob.load("my-block-name"),
        targeted_retries=5,
    )
    return result

run_dbt_job_flow()
```

### Integrate dbt Core CLI commands with Prefect flows

`prefect-dbt` also supports execution of dbt Core CLI commands.

To get started, if you don't have a `DbtCoreOperation` block already saved,
set the commands that you want to run; it can include a mix of dbt and non-dbt commands.

Then, optionally specify the `project_dir`.

If `profiles_dir` is unset, it will try to use the `DBT_PROFILES_DIR` environment variable.
If that's also not set, it will use the default directory `$HOME/.dbt/`.

#### Using an existing profile

If you already have an existing dbt profile, specify the `profiles_dir` where `profiles.yml` is located.

```python
from prefect import flow
from prefect_dbt.cli.commands import DbtCoreOperation

@flow
def trigger_dbt_flow() -> str:
    result = DbtCoreOperation(
        commands=["pwd", "dbt debug", "dbt run"],
        project_dir="PROJECT-DIRECTORY-PLACEHOLDER",
        profiles_dir="PROFILES-DIRECTORY-PLACEHOLDER"
    ).run()
    return result

trigger_dbt_flow()
```

#### Writing a new profile

To setup a new profile, first [save and load a DbtCliProfile block](#saving-credentials-to-block) and use it in `DbtCoreOperation`.

Then, specify `profiles_dir` where `profiles.yml` will be written.

```python
from prefect import flow
from prefect_dbt.cli import DbtCliProfile, DbtCoreOperation

@flow
def trigger_dbt_flow():
    dbt_cli_profile = DbtCliProfile.load("DBT-CORE-OPERATION-BLOCK-NAME-PLACEHOLDER")
    with DbtCoreOperation(
        commands=["dbt debug", "dbt run"],
        project_dir="PROJECT-DIRECTORY-PLACEHOLDER",
        profiles_dir="PROFILES-DIRECTORY-PLACEHOLDER",
        dbt_cli_profile=dbt_cli_profile,
    ) as dbt_operation:
        dbt_process = dbt_operation.trigger()
        # do other things before waiting for completion
        dbt_process.wait_for_completion()
        result = dbt_process.fetch_result()
    return result

trigger_dbt_flow()
```

## Resources

If you need help getting started with or using dbt, please consult the [dbt documentation](https://docs.getdbt.com/docs/building-a-dbt-project/documentation).

### Installation

To use `prefect-dbt` with dbt Cloud:

```bash
pip install prefect-dbt
```

To use dbt Core (CLI):

```bash
pip install "prefect-dbt[cli]"
```

To use dbt Core with Snowflake profiles:

```bash
pip install "prefect-dbt[snowflake]"
```

To use dbt Core with BigQuery profiles:

```bash
pip install "prefect-dbt[bigquery]"
```

To use dbt Core with Postgres profiles:

```bash
pip install "prefect-dbt[postgres]"
```

!!! warning "Some dbt Core profiles require additional installation"

    According to dbt's [Databricks setup page](https://docs.getdbt.com/reference/warehouse-setups/databricks-setup), users must first install the adapter:

    ```bash
    pip install dbt-databricks
    ```

    Check out the [desired profile setup page](https://docs.getdbt.com/reference/profiles.yml) on the sidebar for others.

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Saving credentials to block

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or [saved through the UI](https://docs.prefect.io/ui/blocks/).

!!! info "Registering blocks"

    Register blocks in this module to
    [view and edit them](https://docs.prefect.io/ui/blocks/)
    on Prefect Cloud:

    ```bash
    prefect block register -m prefect_dbt
    ```

#### dbt Cloud

To create a dbt Cloud credentials block:

1. Head over to your [dbt Cloud profile](https://cloud.getdbt.com/settings/profile).
2. Login to your dbt Cloud account.
3. Scroll down to "API" or click "API Access" on the sidebar.
4. Copy the API Key.
5. Click Projects on the sidebar.
6. Copy the account ID from the URL: `https://cloud.getdbt.com/settings/accounts/<ACCOUNT_ID>`.
7. Create a short script, replacing the placeholders.

```python
from prefect_dbt.cloud import DbtCloudCredentials

DbtCloudCredentials(
    api_key="API-KEY-PLACEHOLDER",
    account_id="ACCOUNT-ID-PLACEHOLDER"
).save("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
```

Then, to create a dbt Cloud job block:

1. Head over to your [dbt home page](https://cloud.getdbt.com/).
2. On the top nav bar, click on Deploy -> Jobs.
3. Select a job.
4. Copy the job ID from the URL: `https://cloud.getdbt.com/deploy/<ACCOUNT_ID>/projects/<PROJECT_ID>/jobs/<JOB_ID>`
5. Create a short script, replacing the placeholders.

```python
from prefect_dbt.cloud import DbtCloudCredentials, DbtCloudJob

dbt_cloud_credentials = DbtCloudCredentials.load("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
dbt_cloud_job = DbtCloudJob(
    dbt_cloud_credentials=dbt_cloud_credentials,
    job_id="JOB-ID-PLACEHOLDER"
).save("JOB-BLOCK-NAME-PLACEHOLDER")
```

Congrats! You can now easily load the saved block, which holds your credentials:

```python
from prefect_dbt.cloud import DbtCloudJob

DbtCloudJob.load("JOB-BLOCK-NAME-PLACEHOLDER")
```

#### dbt Core CLI

!!! info "Available `TargetConfigs` blocks"

    The following may vary slightly depending on the service you want to incorporate.

    Visit the [API Reference](cli/configs/base) to see other built-in `TargetConfigs` blocks.

    If the desired service profile is not available, check out the
    [Examples Catalog](examples_catalog/#clicredentials-module) to see how you can
    build one from the generic `TargetConfigs` class.

To create dbt Core target config and profile blocks for BigQuery:

1. Save and load a [`GcpCredentials` block](https://prefecthq.github.io/prefect-gcp/#saving-credentials-to-a-block).
2. Determine the schema / dataset you want to use in BigQuery.
3. Create a short script, replacing the placeholders.

```python
from prefect_gcp.credentials import GcpCredentials
from prefect_dbt.cli import BigQueryTargetConfigs, DbtCliProfile

credentials = GcpCredentials.load("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
target_configs = BigQueryTargetConfigs(
    schema="SCHEMA-NAME-PLACEHOLDER",  # also known as dataset
    credentials=credentials,
)
target_configs.save("TARGET-CONFIGS-BLOCK-NAME-PLACEHOLDER")

dbt_cli_profile = DbtCliProfile(
    name="PROFILE-NAME-PLACEHOLDER",
    target="TARGET-NAME-placeholder",
    target_configs=target_configs,
)
dbt_cli_profile.save("DBT-CLI-PROFILE-BLOCK-NAME-PLACEHOLDER")
```

Then, to create a dbt Core operation block:

1. Determine the dbt commands you want to run.
2. Create a short script, replacing the placeholders.

```python
from prefect_dbt.cli import DbtCliProfile, DbtCoreOperation

dbt_cli_profile = DbtCliProfile.load("DBT-CLI-PROFILE-BLOCK-NAME-PLACEHOLDER")
dbt_core_operation = DbtCoreOperation(
    commands=["DBT-CLI-COMMANDS-PLACEHOLDER"],
    dbt_cli_profile=dbt_cli_profile,
    overwrite_profiles=True,
)
dbt_core_operation.save("DBT-CORE-OPERATION-BLOCK-NAME-PLACEHOLDER")
```

Congrats! You can now easily load the saved block, which holds your credentials:

```python
from prefect_dbt.cloud import DbtCoreOperation

DbtCoreOperation.load("DBT-CORE-OPERATION-BLOCK-NAME-PLACEHOLDER")
```

### Feedback

If you encounter any bugs while using `prefect-dbt`, feel free to open an issue in the [prefect](https://github.com/PrefectHQ/prefect) repository.

If you have any questions or issues while using `prefect-dbt`, you can find help in the [Prefect Slack community](https://prefect.io/slack).

### Contributing

If you'd like to help contribute to fix an issue or add a feature to `prefect-dbt`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Here are the steps:

1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
7. `git commit`, `git push`, and create a pull request
