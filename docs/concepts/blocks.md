---
description: Prefect blocks package configuration storage, infrastructure, and secrets for use with deployments or flow scripts.
tags:
  - blocks
  - storage
  - secrets
  - configuration
  - infrastructure
  - deployments
---

# Blocks

Blocks are a primitive within Prefect that enable the storage of configuration and provide an interface for interacting with external systems.

Blocks are useful for configuration that needs to be shared across flow runs and between flows. For configuration that will change between flow runs, we recommend using [parameters](/concepts/flows/#parameters).

With blocks, you are able to securely store credentials for authenticating with services like AWS, GitHub, Slack, or any other system you'd like to orchestrate with Prefect. Blocks also expose methods that provide pre-built functionality for performing actions against an external system. Blocks can be used to download data from or upload data to an S3 bucket, query data from or write data to a database, or send a message to a Slack channel.

Blocks can also be created by anyone and shared with the community. You'll find blocks that are available for consumption in many of the published [Prefect Collections](/collections/catalog).

## Using existing block types

Blocks are classes that subclass the `Block` base class. They can be instantiated and used like normal classes.

### Instantiating blocks

For example, to instantiate a block that stores a JSON value, use the `JSON` block:

```python
from prefect.blocks.system import JSON

json_block = JSON(value={"the_answer": 42})
```

### Saving blocks

If this JSON value needs to be retrieved later to be used within a flow or task, we can use the `.save()` method on the block to store the value in a block document on the Orion DB for retrieval later:

```python
json_block.save(name="life-the-universe-everything")
```

!!! tip "Utilizing the UI"
    Blocks documents can also be created and updated via the [Prefect UI](/ui/blocks/).

### Loading blocks

The name given when saving the value stored in the JSON block can be used when retrieving the value during a flow or task run:

```python hl_lines="6"
from prefect import flow
from prefect.blocks.system import JSON

@flow
def what_is_the_answer():
    json_block = JSON.load("life-the-universe-everything")
    print(json_block.value["the_answer"])

what_is_the_answer() # 42
```

Blocks can also be loaded with a unique slug that is a combination of a block type slug and a block document name.

To load our JSON block document from before, we can run the following:

```python hl_lines="3"
from prefect.blocks.core import Block

json_block = Block.load("json/life-the-universe-everything")
print(json_block.value["the-answer"]) #42
```

!!! tip "Sharing Blocks"
    Blocks can also be loaded by fellow Workspace Collaborators, available on [Prefect Cloud](/ui/cloud/).

## Creating new block types

To create a custom block type, define a class that subclasses `Block`. The `Block` base class builds off of Pydantic's `BaseModel`, so custom blocks can be [declared in same manner as a Pydantic model](https://pydantic-docs.helpmanual.io/usage/models/#basic-model-usage).

Here's a block that represents a cube and holds information about the length of each edge in inches:

```python
from prefect.blocks.core import Block

class Cube(Block):
    edge_length_inches: float
```

You can also include methods on a block include useful functionality. Here's the same cube block with methods to calculate the volume and surface area of the cube:

```python hl_lines="6-10"
from prefect.blocks.core import Block

class Cube(Block):
    edge_length_inches: float

    def get_volume(self):
        return self.edge_length_inches**3

    def get_surface_area(self):
        return 6 * self.edge_length_inches**2
```

Now the `Cube` block can be used to store different cube configuration that can later be used in a flow:

```python
from prefect import flow

rubiks_cube = Cube(edge_length_inches=2.25)
rubiks_cube.save("rubiks-cube")

@flow
def calculate_cube_surface_area(cube_name):
    cube = Cube.load(cube_name)
    print(cube.get_surface_area())

calculate_cube_surface_area("rubiks-cube") # 30.375
```

### Secret fields

All block values are encrypted before being stored, but if you have values that you would not like visible in the UI or in logs, then you can use the `SecretStr` field type provided by Pydantic to automatically obfuscate those values. This can be useful for fields that are used to store credentials like passwords and API tokens.

Here's an example of an `AWSCredentials` block that uses `SecretStr`:

```python hl_lines="8"
from typing import Optional

from prefect.blocks.core import Block
from pydantic import SecretStr

class AWSCredentials(Block):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[SecretStr] = None
    aws_session_token: Optional[str] = None
    profile_name: Optional[str] = None
    region_name: Optional[str] = None
```

Because `aws_secret_access_key` has the `SecretStr` type hint assigned to it, the value of that field will not be exposed if the object is logged:

```python
aws_credentials_block = AWSCredentials(
    aws_access_key_id="AKIAJKLJKLJKLJKLJKLJK",
    aws_secret_access_key="secret_access_key"
)

print(aws_credentials_block)
# aws_access_key_id='AKIAJKLJKLJKLJKLJKLJK' aws_secret_access_key=SecretStr('**********') aws_session_token=None profile_name=None region_name=None
```

### Blocks metadata

The way that a block is displayed can be controlled by metadata fields that can be set on a block subclass.

Available metadata fields include:

| Property          | Description                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| \_block_type_name | Display name of the block in the UI. Defaults to the class name.                                                                             |
| \_block_type_slug | Unique slug used to reference the block type in the API. Defaults to a lowercase, dash-delimited version of the block type name.             |
| \_logo_url        | URL pointing to an image that should be displayed for the block type in the UI. Default to `None`.                                           |
| \_description     | Short description of block type. Defaults to docstring, if provided.                                                                         |
| \_code_example    | Short code snippet shown in UI for how to load/use block type. Default to first example provided in the docstring of the class, if provided. |

### Nested blocks

Block are composable. This means that you can create a block that uses functionality from another block by declaring it as an attribute on the block that you're creating. It also means that configuration can be changed for each block independently, which allows configuration that may change on different time frames to be easily managed and configuration can be shared across multiple use cases.

To illustrate, here's a an expanded `AWSCredentials` block that includes the ability to get an authenticated session via the `boto3` library:

```python
from typing import Optional

import boto3
from prefect.blocks.core import Block
from pydantic import SecretStr

class AWSCredentials(Block):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[SecretStr] = None
    aws_session_token: Optional[str] = None
    profile_name: Optional[str] = None
    region_name: Optional[str] = None

    def get_boto3_session(self):
        return boto3.Session(
            aws_access_key_id = self.aws_access_key_id
            aws_secret_access_key = self.aws_secret_access_key
            aws_session_token = self.aws_session_token
            profile_name = self.profile_name
            region_name = self.region
        )
```

The `AWSCredentials` block can be used within an S3Bucket block to provide authentication when interacting with an S3 bucket:

```python hl_lines="5"
import io

class S3Bucket(Block):
    bucket_name: str
    credentials: AWSCredentials

    def read(self, key: str) -> bytes:
        s3_client = self.credentials.get_boto3_session().client("s3")

        stream = io.BytesIO()
        s3_client.download_fileobj(Bucket=self.bucket_name, key=key, Fileobj=stream)

        stream.seek(0)
        output = stream.read()

        return output

    def write(self, key: str, data: bytes) -> None:
        s3_client = self.credentials.get_boto3_session().client("s3")
        stream = io.BytesIO(data)
        s3_client.upload_fileobj(stream, Bucket=self.bucket_name, Key=key)
```

You can use this `S3Bucket` block with previously saved `AWSCredentials` block values in order to interact with the configured S3 bucket:

```python
my_s3_bucket = S3Bucket(
    bucket_name="my_s3_bucket",
    credentials=AWSCredentials.load("my_aws_credentials")
)

my_s3_bucket.save("my_s3_bucket")
```

Saving block values like this links the values of the two blocks so that any changes to the values stored for the `AWSCredentials` block with the name `my_aws_credentials` will be seen the next time that block values for the `S3Bucket` block named `my_s3_bucket` is loaded.

Values for nested blocks can also be hard coded by not first saving child blocks:

```python
my_s3_bucket = S3Bucket(
    bucket_name="my_s3_bucket",
    credentials=AWSCredentials(
        aws_access_key_id="AKIAJKLJKLJKLJKLJKLJK",
        aws_secret_access_key="secret_access_key"
    )
)

my_s3_bucket.save("my_s3_bucket")
```

In the above example, the values for `AWSCredentials` are saved with `my_s3_bucket` and will not be usable with any other blocks.

## Registering blocks for use in the Prefect UI:

Blocks can be registered from a Python module available in the current virtual environment with a CLI command like this:

```bash
$ prefect block register --module prefect_aws.credentials
```

This command is useful for registering all blocks found in the credentials module within [Prefect Collections](/collections/catalog/).

Or, if a block has been created in a `.py` file, the block can also be registered with the CLI command:

```bash
$ prefect block register --file my_block.py
```

The registered block will then be available in the [Prefect UI](/ui/blocks/) for configuration.
