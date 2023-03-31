---
description: Prefect Integrations provide Prefect integrations that help you build dataflows quickly.
tags:
    - tasks
    - flows
    - blocks
    - integrations
    - task library
    - contributing
---

# Using Integrations

## Installing an Integration

Install the Integration via `pip`.

For example, to use `prefect-aws`:

```bash
pip install prefect-aws
```

## Registering Blocks from an Integration

Once the Prefect Integration is installed, [register the blocks](/concepts/blocks/#registering-blocks-for-use-in-the-prefect-ui) within the integration to view them in the Prefect Cloud UI:

For example, to register the blocks available in `prefect-aws`:

```bash
prefect block register -m prefect_aws
```

!!! tip "Updating blocks from an integrations"
    If you install an updated Prefect integration that adds fields to a block type, you will need to re-register that block type.

!!! tip "Loading a block in code"
    To use the `load` method on a Block, you must already have a block document [saved](/concepts/blocks/#saving-blocks) either through code or through the Prefect UI.

Learn more about Blocks [here](/concepts/blocks)!

## Using Tasks and Flows from an Integration

Integrations also contain pre-built tasks and flows that can be imported and called within your code.

As an example, to read a secret from AWS Secrets Manager with the `read_secret` task:

```python
from prefect import flow
from prefect_aws import AwsCredentials
from prefect_aws.secrets_manager import read_secret

@flow
def connect_to_database():
    aws_credentials = AwsCredentials.load("MY_BLOCK_NAME")
    secret_value = read_secret(
        secret_name="db_password",
        aws_credentials=aws_credentials
    )

    # Use secret_value to connect to a database
```

## Customizing Tasks and Flows from an Integration

To customize the settings of a task or flow pre-configured in a collection, use `with_options`:
    
```python
from prefect import flow
from prefect_dbt.cloud import DbtCloudCredentials
from prefect_dbt.cloud.jobs import trigger_dbt_cloud_job_run_and_wait_for_completion

custom_run_dbt_cloud_job = trigger_dbt_cloud_job_run_and_wait_for_completion.with_options(
    name="Run My DBT Cloud Job",
    retries=2,
    retry_delay_seconds=10
)

@flow
def run_dbt_job_flow():
    run_result = custom_run_dbt_cloud_job(
        dbt_cloud_credentials=DbtCloudCredentials.load("my-dbt-cloud-credentials"),
        job_id=1
    )

run_dbt_job_flow()

``` 
## Recipes and Tutorials

To learn more about how to use Integrations, check out [Prefect recipes](https://github.com/PrefectHQ/prefect-recipes#diving-deeper-) on GitHub. These recipes provide examples of how Integrations can be used in various scenarios.
