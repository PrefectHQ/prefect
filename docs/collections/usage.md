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
prefect block register -m prefect_aws.credentials
prefect block register -m prefect_aws.ecs
```

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

**Note**, to use the load method on Blocks, you must already have a block document [saved](/concepts/blocks/#saving-blocks) through code or saved through the UI.
