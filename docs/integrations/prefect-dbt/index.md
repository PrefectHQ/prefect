# prefect-dbt

With prefect-dbt, you can trigger and observe dbt Cloud jobs, execute dbt Core CLI commands, and incorporate other tools, such as Snowflake, into your dbt runs.
Prefect provides a global view of the state of your workflows and allows you to take action based on state changes.

## Getting started 

1. [Install prefect-dbt](#installation) 
1. [Register newly installed blocks types](#registering-block-types)

Explore the examples below to learn how to use Prefect with dbt.

### Integrate dbt Cloud jobs with Prefect flows

If you have an existing dbt Cloud job, you can use the pre-built flow `run_dbt_cloud_job` to trigger a job run and wait until the job run is finished.

If some nodes fail, `run_dbt_cloud_job` efficiently retries the unsuccessful nodes.

Prior to running this flow, [save your dbt Cloud credentials to a DbtCloudCredentials block](#saving-credentials-to-a-block)

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

`prefect-dbt` supports execution of dbt Core CLI commands.

If you don't have a `DbtCoreOperation` block saved, create one and set the commands that you want to run. 

Optionally, specify the `project_dir`.
If `profiles_dir` is not set, the `DBT_PROFILES_DIR` environment variable will be used.
If `DBT_PROFILES_DIR` is not set, the default directory will be used `$HOME/.dbt/`.

#### Using an existing profile

If you have an existing dbt profile, specify the `profiles_dir` where `profiles.yml` is located.
You can use it in code like this:

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

Then, specify`profiles_dir` where `profiles.yml` will be written.
Here's example code with placeholders:

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

If you need help using dbt, consult the [dbt documentation](https://docs.getdbt.com/docs/building-a-dbt-project/documentation).

### Installation

To install `prefect-dbt` for use with dbt Cloud:

<div class = "terminal">
```bash
pip install prefect-dbt
```
</div>

To install with additional functionality for dbt Core (CLI):

<div class = "terminal">
```bash
pip install "prefect-dbt[cli]"
```
</div>

To install with additional functionality for dbt Core and Snowflake profiles:

<div class = "terminal">
```bash
pip install "prefect-dbt[snowflake]"
```
</div>

To install with additional functionality for dbt Core and BigQuery profiles:

<div class = "terminal">
```bash
pip install "prefect-dbt[bigquery]"
```
</div>

To install with additional functionality for dbt Core and Postgres profiles:

<div class = "terminal">
```bash
pip install "prefect-dbt[postgres]"
```
</div>

!!! warning "Some dbt Core profiles require additional installation"

    According to dbt's [Databricks setup page](https://docs.getdbt.com/reference/warehouse-setups/databricks-setup), users must first install the adapter:

    <div class = "terminal">
    ```bash
    pip install dbt-databricks
    ```
    </div>

    Check out the [desired profile setup page](https://docs.getdbt.com/reference/profiles.yml) on the sidebar for others.

prefect-dbt requires Python 3.8 or newer.

We recommend using a Python virtual environment manager such as conda, venv, or pipenv.

### Registering block types

Register the block types in the prefect-dbt module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_dbt
```
</div>

### Saving credentials to a block

Blocks can be [created through code](/concepts/blocks/#saving-blocks) or through the UI.

#### dbt Cloud

To create a dbt Cloud Credentials block do the following:

1. Go to your [dbt Cloud profile](https://cloud.getdbt.com/settings/profile).
2. Log in to your dbt Cloud account.
3. Scroll to **API** or click **API Access** on the sidebar.
4. Copy the API Key.
5. Click **Projects** on the sidebar.
6. Copy the account ID from the URL: `https://cloud.getdbt.com/settings/accounts/<ACCOUNT_ID>`.
7. Create and run the following script, replacing the placeholders.

```python
from prefect_dbt.cloud import DbtCloudCredentials

DbtCloudCredentials(
    api_key="API-KEY-PLACEHOLDER",
    account_id="ACCOUNT-ID-PLACEHOLDER"
).save("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
```

Then, to create a dbt Cloud job block do the following:

1. Head over to your [dbt home page](https://cloud.getdbt.com/).
2. On the top nav bar, click on **Deploy** -> **Jobs**.
3. Select a job.
4. Copy the job ID from the URL: `https://cloud.getdbt.com/deploy/<ACCOUNT_ID>/projects/<PROJECT_ID>/jobs/<JOB_ID>`
5. Create and run the following script, replacing the placeholders.

```python
from prefect_dbt.cloud import DbtCloudCredentials, DbtCloudJob

dbt_cloud_credentials = DbtCloudCredentials.load("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
dbt_cloud_job = DbtCloudJob(
    dbt_cloud_credentials=dbt_cloud_credentials,
    job_id="JOB-ID-PLACEHOLDER"
).save("JOB-BLOCK-NAME-PLACEHOLDER")
```

You can now load the saved block, which can access your credentials:

```python
from prefect_dbt.cloud import DbtCloudJob

DbtCloudJob.load("JOB-BLOCK-NAME-PLACEHOLDER")
```

#### dbt Core CLI

!!! info "Available `TargetConfigs` blocks"

    Visit the [API Reference](cli/configs/base) to see other built-in `TargetConfigs` blocks.

    If the desired service profile is not available, check out the [Examples Catalog](examples_catalog/#clicredentials-module) to see how you can  build one from the generic `TargetConfigs` class.

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
