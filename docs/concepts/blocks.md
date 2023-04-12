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

With blocks, you can securely store credentials for authenticating with services like AWS, GitHub, Slack, and any other system you'd like to orchestrate with Prefect. 

Blocks expose methods that provide pre-built functionality for performing actions against an external system. They can be used to download data from or upload data to an S3 bucket, query data from or write data to a database, or send a message to a Slack channel.

You may configure blocks through code or via the Prefect Cloud and the Prefect server UI.

You can access blocks for both configuring flow [deployments](/concepts/deployments/) and directly from within your flow code.

Prefect provides some built-in block types that you can use right out of the box. Additional blocks are available through [Prefect Integrations](/integrations/). To use these blocks you can `pip install` the package, then register the blocks you want to use with Prefect Cloud or a Prefect server.

Prefect Cloud and the Prefect server UI display a library of block types available for you to configure blocks that may be used by your flows.

![Viewing the new block library in the Prefect UI](../img/ui/block-library.png)

!!! tip "Blocks and parameters"
    Blocks are useful for configuration that needs to be shared across flow runs and between flows.

    For configuration that will change between flow runs, we recommend using [parameters](/concepts/flows/#parameters).

## Prefect built-in blocks

Prefect provides a broad range of commonly used, built-in block types. These block types are available in Prefect Cloud and the Prefect server UI.

| Block | Slug | Description |
| --- | --- | --- |
| [Azure](/concepts/filesystems/#azure) | `azure` | Store data as a file on Azure Datalake and Azure Blob Storage. |
| [Date Time](/api-ref/prefect/blocks/system/#prefect.blocks.system.DateTime) | `date-time` | A block that represents a datetime. |
| [Docker Container](/api-ref/prefect/infrastructure/#prefect.infrastructure.DockerContainer) | `docker-container` | Runs a command in a container. |
| [Docker Registry](/api-ref/prefect/infrastructure/#prefect.infrastructure.docker.DockerRegistry) | `docker-registry` | Connects to a Docker registry.  Requires a Docker Engine to be connectable. |
| [GCS](/concepts/filesystems/#gcs) | `gcs` | Store data as a file on Google Cloud Storage. |
| [GitHub](/concepts/filesystems/#github) | `github` | Interact with files stored on public GitHub repositories. |
| [JSON](/api-ref/prefect/blocks/system/#prefect.blocks.system.JSON) | `json` | A block that represents JSON. |
| [Kubernetes Cluster Config](/api-ref/prefect/blocks/kubernetes/#prefect.blocks.kubernetes.KubernetesClusterConfig) | <span class="no-wrap">`kubernetes-cluster-config`</span> | Stores configuration for interaction with Kubernetes clusters. |
| [Kubernetes Job](/api-ref/prefect/infrastructure/#prefect.infrastructure.KubernetesJob) | `kubernetes-job` | Runs a command as a Kubernetes Job. |
| [Local File System](/concepts/filesystems/#local-filesystem) | `local-file-system` | Store data as a file on a local file system. |
| [Microsoft Teams Webhook](/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.MicrosoftTeamsWebhook) | `ms-teams-webhook` | Enables sending notifications via a provided Microsoft Teams webhook. |
| [Opsgenie Webhook](/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.OpsgenieWebhook) | `opsgenie-webhook` | Enables sending notifications via a provided Opsgenie webhook. |
| [Pager Duty Webhook](/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.PagerDutyWebHook) | `pager-duty-webhook` | Enables sending notifications via a provided PagerDuty webhook. |
| [Process](/concepts/infrastructure/#process) | `process` | Run a command in a new process. |
| [Remote File System](/concepts/filesystems/#remote-file-system) | `remote-file-system` | Store data as a file on a remote file system.  Supports any remote file system supported by `fsspec`.  |
| [S3](/concepts/filesystems/#s3) | `s3` | Store data as a file on AWS S3. |
| [Secret](/api-ref/prefect/blocks/system/#prefect.blocks.system.Secret) | `secret` | A block that represents a secret value. The value stored in this block will be obfuscated when this block is logged or shown in the UI. |
| [Slack Webhook](/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.SlackWebhook) | `slack-webhook` | Enables sending notifications via a provided Slack webhook. |
| [SMB](/concepts/filesystems/#smb) | `smb` | Store data as a file on a SMB share. |
| [String](/api-ref/prefect/blocks/system/#prefect.blocks.system.String) | `string` | A block that represents a string. |
| [Twilio SMS](/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.TwilioSMS) | `twilio-sms` | Enables sending notifications via Twilio SMS. |
| [Webhook](/api-ref/prefect/blocks/webhook/#prefect.blocks.webhook.Webhook) | `webhook` | Block that enables calling webhooks. |

## Blocks in Prefect Integrations

Blocks can also be created by anyone and shared with the community. You'll find blocks that are available for consumption in many of the published [Prefect Integrations](/integrations/). The following table provides an overview of the blocks available from our most popular Prefect Integrations.

| Integration | Block | Slug |
| --- | --- | --- |
| [prefect-airbyte](https://prefecthq.github.io/prefect-airbyte/) | [Airbyte Connection](https://prefecthq.github.io/prefect-airbyte/connections/#prefect_airbyte.connections.AirbyteConnection) | `airbyte-connection` |
| [prefect-airbyte](https://prefecthq.github.io/prefect-airbyte/) | [Airbyte Server](https://prefecthq.github.io/prefect-airbyte/server/#prefect_airbyte.server.AirbyteServer) | `airbyte-server` |
| [prefect-aws](https://prefecthq.github.io/prefect-aws/) | [AWS Credentials](https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.AwsCredentials) | `aws-credentials` |
| [prefect-aws](https://prefecthq.github.io/prefect-aws/) | [ECS Task](https://prefecthq.github.io/prefect-aws/ecs/#prefect_aws.ecs.ECSTask) | `ecs-task` |
| [prefect-aws](https://prefecthq.github.io/prefect-aws/) | [MinIO Credentials](https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.MinIOCredentials) | `minio-credentials` |
| [prefect-aws](https://prefecthq.github.io/prefect-aws/) | [S3 Bucket](https://prefecthq.github.io/prefect-aws/s3/#prefect_aws.s3.S3Bucket) | `s3-bucket` |
| [prefect-azure](https://prefecthq.github.io/prefect-azure/) | [Azure Blob Storage Credentials](https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureBlobStorageCredentials) | `azure-blob-storage-credentials` |
| [prefect-azure](https://prefecthq.github.io/prefect-azure/) | [Azure Container Instance Credentials](https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureContainerInstanceCredentials) | `azure-container-instance-credentials` |
| [prefect-azure](https://prefecthq.github.io/prefect-azure/) | [Azure Container Instance Job](https://prefecthq.github.io/prefect-azure/container_instance/#prefect_azure.container_instance.AzureContainerInstanceJob) | `azure-container-instance-job` |
| [prefect-azure](https://prefecthq.github.io/prefect-azure/) | [Azure Cosmos DB Credentials](https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureCosmosDbCredentials) | `azure-cosmos-db-credentials` |
| [prefect-azure](https://prefecthq.github.io/prefect-azure/) | [AzureML Credentials](https://prefecthq.github.io/prefect-azure/credentials/#prefect_azure.credentials.AzureMlCredentials) | `azureml-credentials` |
| [prefect-bitbucket](https://prefecthq.github.io/prefect-bitbucket/) | [BitBucket Credentials](https://prefecthq.github.io/prefect-bitbucket/credentials/) | `bitbucket-credentials` |
| [prefect-bitbucket](https://prefecthq.github.io/prefect-bitbucket/) | [BitBucket Repository](https://prefecthq.github.io/prefect-bitbucket/repository/) | `bitbucket-repository` |
| [prefect-census](https://prefecthq.github.io/prefect-census/) | [Census Credentials](https://prefecthq.github.io/prefect-census/credentials/) | `census-credentials` |
| [prefect-census](https://prefecthq.github.io/prefect-census/) | [Census Sync](https://prefecthq.github.io/prefect-census/syncs/) | `census-sync` |
| [prefect-databricks](https://prefecthq.github.io/prefect-databricks/) | [Databricks Credentials](https://prefecthq.github.io/prefect-databricks/credentials/#prefect_databricks.credentials.DatabricksCredentials) | `databricks-credentials` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt CLI BigQuery Target Configs](https://prefecthq.github.io/prefect-dbt/cli/configs/bigquery/#prefect_dbt.cli.configs.bigquery.BigQueryTargetConfigs) | `dbt-cli-bigquery-target-configs` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt CLI Profile](https://prefecthq.github.io/prefect-dbt/cli/credentials/#prefect_dbt.cli.credentials.DbtCliProfile) | `dbt-cli-profile` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt Cloud Credentials](https://prefecthq.github.io/prefect-dbt/cloud/credentials/#prefect_dbt.cloud.credentials.DbtCloudCredentials) | `dbt-cloud-credentials` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt CLI Global Configs](https://prefecthq.github.io/prefect-dbt/cli/configs/base/#prefect_dbt.cli.configs.base.GlobalConfigs) | `dbt-cli-global-configs` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt CLI Postgres Target Configs](https://prefecthq.github.io/prefect-dbt/cli/configs/postgres/#prefect_dbt.cli.configs.postgres.PostgresTargetConfigs) | `dbt-cli-postgres-target-configs` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt CLI Snowflake Target Configs](https://prefecthq.github.io/prefect-dbt/cli/configs/snowflake/#prefect_dbt.cli.configs.snowflake.SnowflakeTargetConfigs) | `dbt-cli-snowflake-target-configs` |
| [prefect-dbt](https://prefecthq.github.io/prefect-dbt/) | [dbt CLI Target Configs](https://prefecthq.github.io/prefect-dbt/cli/configs/base/#prefect_dbt.cli.configs.base.TargetConfigs) | `dbt-cli-target-configs` |
| [prefect-docker](https://prefecthq.github.io/prefect-docker/) | [Docker Host](https://prefecthq.github.io/prefect-docker/host/) | `docker-host` |
| [prefect-docker](https://prefecthq.github.io/prefect-docker/) | [Docker Registry Credentials](https://prefecthq.github.io/prefect-docker/credentials/) | `docker-registry-credentials` |
| [prefect-email](https://prefecthq.github.io/prefect-email/) | [Email Server Credentials](https://prefecthq.github.io/prefect-email/credentials/) | `email-server-credentials` |
| [prefect-firebolt](https://prefecthq.github.io/prefect-firebolt/) | [Firebolt Credentials](https://prefecthq.github.io/prefect-firebolt/credentials/) | `firebolt-credentials` |
| [prefect-firebolt](https://prefecthq.github.io/prefect-firebolt/) | [Firebolt Database](https://prefecthq.github.io/prefect-firebolt/database/) | `firebolt-database` |
| [prefect-gcp](https://prefecthq.github.io/prefect-gcp/) | [BigQuery Warehouse](https://prefecthq.github.io/prefect-gcp/bigquery/#prefect_gcp.bigquery.BigQueryWarehouse) | `bigquery-warehouse` |
| [prefect-gcp](https://prefecthq.github.io/prefect-gcp/) | [GCP Cloud Run Job](https://prefecthq.github.io/prefect-gcp/cloud_run/#prefect_gcp.cloud_run.CloudRunJob) | `cloud-run-job` |
| [prefect-gcp](https://prefecthq.github.io/prefect-gcp/) | [GCP Credentials](https://prefecthq.github.io/prefect-gcp/credentials/#prefect_gcp.credentials.GcpCredentials) | `gcp-credentials` |
| [prefect-gcp](https://prefecthq.github.io/prefect-gcp/) | [GcpSecret](https://prefecthq.github.io/prefect-gcp/secret_manager/#prefect_gcp.secret_manager.GcpSecret) | `gcpsecret` |
| [prefect-gcp](https://prefecthq.github.io/prefect-gcp/) | [GCS Bucket](https://prefecthq.github.io/prefect-gcp/cloud_storage/#prefect_gcp.cloud_storage.GcsBucket) | `gcs-bucket` |
| [prefect-gcp](https://prefecthq.github.io/prefect-gcp/) | [Vertex AI Custom Training Job](https://prefecthq.github.io/prefect-gcp/aiplatform/#prefect_gcp.aiplatform.VertexAICustomTrainingJob) | `vertex-ai-custom-training-job` |
| [prefect-github](https://prefecthq.github.io/prefect-github/) | [GitHub Credentials](https://prefecthq.github.io/prefect-github/credentials/) | `github-credentials` |
| [prefect-github](https://prefecthq.github.io/prefect-github/) | [GitHub Repository](https://prefecthq.github.io/prefect-github/repository/) | `github-repository` |
| [prefect-gitlab](https://prefecthq.github.io/prefect-gitlab/) | [GitLab Credentials](https://prefecthq.github.io/prefect-gitlab/credentials/) | `gitlab-credentials` |
| [prefect-gitlab](https://prefecthq.github.io/prefect-gitlab/) | [GitLab Repository](https://prefecthq.github.io/prefect-gitlab/repositories/) | `gitlab-repository` |
| [prefect-hex](https://prefecthq.github.io/prefect-hex/) | [Hex Credentials](https://prefecthq.github.io/prefect-hex/credentials/#prefect_hex.credentials.HexCredentials) | `hex-credentials` |
| [prefect-hightouch](https://prefecthq.github.io/prefect-hightouch/) | [Hightouch Credentials](https://prefecthq.github.io/prefect-hightouch/credentials/) | `hightouch-credentials` |
| [prefect-kubernetes](https://prefecthq.github.io/prefect-kubernetes/) | [Kubernetes Credentials](https://prefecthq.github.io/prefect-kubernetes/credentials/) | `kubernetes-credentials` |
| [prefect-monday](https://prefecthq.github.io/prefect-monday/) | [Monday Credentials](https://prefecthq.github.io/prefect-monday/credentials/) | `monday-credentials` |
| [prefect-monte-carlo](https://prefecthq.github.io/prefect-monte-carlo/) | [Monte Carlo Credentials](https://prefecthq.github.io/prefect-monte-carlo/credentials/) | `monte-carlo-credentials` |
| [prefect-openai](https://prefecthq.github.io/prefect-openai/) | [OpenAI Completion Model](https://prefecthq.github.io/prefect-openai/completion/#prefect_openai.completion.CompletionModel) | `openai-completion-model` |
| [prefect-openai](https://prefecthq.github.io/prefect-openai/) | [OpenAI Image Model](https://prefecthq.github.io/prefect-openai/image/#prefect_openai.image.ImageModel) | `openai-image-model` |
| [prefect-openai](https://prefecthq.github.io/prefect-openai/) | [OpenAI Credentials](https://prefecthq.github.io/prefect-openai/credentials/#prefect_openai.credentials.OpenAICredentials) | `openai-credentials` |
| [prefect-slack](https://prefecthq.github.io/prefect-slack/) | [Slack Credentials](https://prefecthq.github.io/prefect-slack/credentials/#prefect_slack.credentials.SlackCredentials) | `slack-credentials` |
| [prefect-slack](https://prefecthq.github.io/prefect-slack/) | [Slack Incoming Webhook](https://prefecthq.github.io/prefect-slack/credentials/#prefect_slack.credentials.SlackWebhook) | `slack-incoming-webhook` |
| [prefect-snowflake](https://prefecthq.github.io/prefect-snowflake/) | [Snowflake Connector](https://prefecthq.github.io/prefect-snowflake/database/#prefect_snowflake.database.SnowflakeConnector) | `snowflake-connector` |
| [prefect-snowflake](https://prefecthq.github.io/prefect-snowflake/) | [Snowflake Credentials](https://prefecthq.github.io/prefect-snowflake/credentials/#prefect_snowflake.credentials.SnowflakeCredentials) | `snowflake-credentials` |
| [prefect-sqlalchemy](https://prefecthq.github.io/prefect-sqlalchemy/) | [Database Credentials](https://prefecthq.github.io/prefect-sqlalchemy/credentials/#prefect_sqlalchemy.credentials.DatabaseCredentials) | `database-credentials` |
| [prefect-sqlalchemy](https://prefecthq.github.io/prefect-sqlalchemy/) | [SQLAlchemy Connector](https://prefecthq.github.io/prefect-sqlalchemy/database/#prefect_sqlalchemy.database.SqlAlchemyConnector) | `sqlalchemy-connector` |
| [prefect-twitter](https://prefecthq.github.io/prefect-twitter/) | [Twitter Credentials](https://prefecthq.github.io/prefect-twitter/credentials/) | `twitter-credentials` |

## Using existing block types

Blocks are classes that subclass the `Block` base class. They can be instantiated and used like normal classes.

### Instantiating blocks

For example, to instantiate a block that stores a JSON value, use the `JSON` block:

```python
from prefect.blocks.system import JSON

json_block = JSON(value={"the_answer": 42})
```

### Saving blocks

If this JSON value needs to be retrieved later to be used within a flow or task, we can use the `.save()` method on the block to store the value in a block document on the Prefect database for retrieval later:

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

There's  also use the `SecretDict` field type provided by Prefect. This type will allow you to add a dictionary field to your block that will have values at all levels automatically obfuscated in the UI or in logs. This is useful for blocks where typing or structure of secret fields is not known until configuration time.

Here's an example of a block that uses `SecretDict`:

```python
from typing import Dict

from prefect.blocks.core import Block
from prefect.blocks.fields import SecretDict


class SystemConfiguration(Block):
    system_secrets: SecretDict
    system_variables: Dict


system_configuration_block = SystemConfiguration(
    system_secrets={
        "password": "p@ssw0rd",
        "api_token": "token_123456789",
        "private_key": "<private key here>",
    },
    system_variables={
        "self_destruct_countdown_seconds": 60,
        "self_destruct_countdown_stop_time": 7,
    },
)
```
`system_secrets` will be obfuscated when `system_configuration_block` is displayed, but `system_variables` will be shown in plain-text:

```python
print(system_configuration_block)
# SystemConfiguration(
#   system_secrets=SecretDict('{'password': '**********', 'api_token': '**********', 'private_key': '**********'}'), 
#   system_variables={'self_destruct_countdown_seconds': 60, 'self_destruct_countdown_stop_time': 7}
# )
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

### Handling updates to custom `Block` types
Let's say that you now want to add a `bucket_folder` field to your custom `S3Bucket` block that represents the default path to read and write objects from (this field exists on [our implementation](https://github.com/PrefectHQ/prefect-aws/blob/main/prefect_aws/s3.py#L292)).

We can add the new field to the class definition:


```python hl_lines="4"
class S3Bucket(Block):
    bucket_name: str
    credentials: AWSCredentials
    bucket_folder: str = None
    ...
```

Then [register the updated block type](#registering-blocks-for-use-in-the-prefect-ui) with either Prefect Cloud or your self-hosted Prefect server.


If you have any existing blocks of this type that were created before the update and you'd prefer to not re-create them, you can migrate them to the new version of your block type by adding the missing values:

```python
# Bypass Pydantic validation to allow your local Block class to load the old block version
my_s3_bucket_block = S3Bucket.load("my-s3-bucket", validate=False)

# Set the new field to an appropriate value
my_s3_bucket_block.bucket_path = "my-default-bucket-path"

# Overwrite the old block values and update the expected fields on the block
my_s3_bucket_block.save("my-s3-bucket", overwrite=True)
```

## Registering blocks for use in the Prefect UI

Blocks can be registered from a Python module available in the current virtual environment with a CLI command like this:

<div class="terminal">
```bash
$ prefect block register --module prefect_aws.credentials
```
</div>

This command is useful for registering all blocks found in the credentials module within [Prefect Integrations](/integrations/).

Or, if a block has been created in a `.py` file, the block can also be registered with the CLI command:

<div class="terminal">
```bash
$ prefect block register --file my_block.py
```
</div>

The registered block will then be available in the [Prefect UI](/ui/blocks/) for configuration.
