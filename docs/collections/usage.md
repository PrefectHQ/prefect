---
description: Prefect Collections provide pre-built tasks and flows that help you build workflows quickly.
tags:
    - tasks
    - flows
    - blocks
    - collections
    - task library
    - contributing
---

# Using Collections

## Installing Collections

To use a Prefect Collection, first install the collection via `pip`.

As an example, to use `prefect-aws`:

```bash
pip install prefect-aws
```

## Registering Blocks within Collections

Then, register to view the blocks on Prefect Cloud:

```bash
prefect block register -m prefect_aws.credentials
prefect block register -m prefect_aws.ecs
```

## Running Tasks within Collections

The AWS tasks and flows in that collection can then be imported and called within your flow:

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

**Note**, to use the load method on Blocks, you must already have a block document [saved](../../concepts/blocks/#saving-blocks) through code or saved through the UI.
