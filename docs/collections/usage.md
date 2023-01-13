---
description: Prefect Collections provide Prefect integrations that help you build dataflows quickly.
tags:
    - tasks
    - flows
    - blocks
    - collections
    - task library
    - contributing
---

# Using Collections

## Installing a Collection

To use a Prefect Collection, first install the collection via `pip`.

As an example, to use `prefect-aws`:

```bash
pip install prefect-aws
```

## Registering Blocks from a Collection

Once the Prefect Collection is installed, [register the blocks](/concepts/blocks/#registering-blocks-for-use-in-the-prefect-ui) within the collection to view them in the Prefect Cloud UI:

As an example, to register the blocks available in `prefect-aws`:

```bash
prefect block register -m prefect_aws
```

**Note**, to use the load method on Blocks, you must already have a block document [saved](/concepts/blocks/#saving-blocks) through code or saved through the UI.

Learn more about Blocks [here](/concepts/blocks)!

## Using Tasks and Flows from a Collection

Collections also contain pre-built tasks and flows that can be imported and called within your code.

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

## Customizing Tasks and Flows from a Collection

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

To learn more about how to use Collections, check out [Prefect recipes](https://github.com/PrefectHQ/prefect-recipes#diving-deeper-) on GitHub. These recipes provide examples of how Collections can be used in various scenarios.
