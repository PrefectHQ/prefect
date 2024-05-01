# Third-party Secrets: Connect to services without storing credentials in blocks

Credentials blocks and secret blocks are popular ways to store sensitive information for connecting to third-party services.

If using Prefect Cloud, these block values are stored in encrypted format.
Organizations whose security policies make such storage infeasible can still use Prefect to connect to third-party services securely.

In this example, we interact with a Snowflake database and store the credentials we need to connect in AWS Secrets Manager.
This example can be generalized to other third party services that require credentials.
We use Prefect Cloud in this example.

## Prerequisites

1. Prefect [installed](/getting-started/installation).
1. CLI authenticated to your [Prefect Cloud](https://app.prefect.cloud) account.
1. [Snowflake account](https://www.snowflake.com/).
1. [AWS account](https://aws.amazon.com/).

## Steps

1. Install `prefect-aws` and `prefect-snowflake` integration libraries.
1. Register blocks from the integration libraries.
1. Store Snowflake password in AWS Secrets Manager.
1. Create `AwsSecret` block to access the Snowflake password.
1. Create `AwsCredentials` block for authentication.
1. Ensure the compute environment has access to AWS credentials that are authorized to access the secret in AWS.
1. Create and use `SnowflakeCredentials` and `SnowflakeConnector` blocks in Python code to interact with Snowflake.

### Install `prefect-aws` and `prefect_snowflake` libraries

The following code will install and upgrade the necessary libraries and upgrade any dependencies.

<div class="terminal">
```bash
pip install -U prefect-aws prefect-snowflake
```
</div>

### Register blocks

Let Prefect Cloud know about the blocks we are going to use by registering them.

<div class="terminal">
```bash
prefect block register -m prefect_aws && prefect block register -m prefect_snowflake
```
</div>

### Store Snowflake password in AWS Secrets Manager

Go to the [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) console and create a new secret.
Alternatively, create a secret using the AWS CLI or a script.

1. In the UI, choose **Store a new secret**.
1. Select **Other type of secret**.
1. Input the key-value pair for your Snowflake password where the key is any string and the value is your Snowflake password.
1. Copy the key for future reference and click **Next**.
1. Enter a name for your secret, copy the name, and click **Next**.
1. For this demo, we won't rotate the key, so click **Next**.
1. Click **Store**.

### Create `AwsSecret` block to access your Snowflake password

You can create blocks with Python code or via the Prefect UI.
Block creation through the UI can help you visualize how the pieces fit together, so let's use it here.

On the Blocks page, click on **+** to add a new block and select **AWS Secret** from the list of block types.
Enter a name for your block and enter the secret name from AWS Secrets Manager.

### Create `AwsCredentials` block

In the **AwsCredentials** section, click **Add +** and a form will appear to create an AWS Credentials block.

Values for **Access Key ID** and **Secret Access Key** will be read from the compute environment.
My AWS **Access Key ID** and **Secret Access Key** values with permissions to read my AWS Secret are stored locally in my `~/.aws/credentials` file, so I'll leave those fields blank.
You could enter those values at block creation, but then they would be saved to the database, and that's what we're trying to avoid.

We need to specify a region in our local AWS config file or in our `AWSCredentials` block.
The `AwsCredentials` block takes precedence, so let's specify it here for portability.

Under the hood, Prefect is using the AWS `boto3` client to create a session.

Click **Create** to save the blocks.

### Ensure the compute environment has access to AWS credentials

Ensure the compute environment contains AWS credentials with authorization to access AWS Secrets Manager.
When we connect to Snowflake, Prefect will automatically use these credentials to authenticate and access the secret.

### Create and use `SnowflakeCredentials` and `SnowflakeConnector` blocks in Python code

Let's use Prefect's blocks for convenient access to Snowflake.
We won't save the blocks, to ensure the credentials are not stored in Prefect Cloud.

We'll create a flow that connects to Snowflake and calls two tasks.
The first task creates a table and inserts some data.
The second task reads the data out.

```python
import json
from prefect import flow, task
from prefect_aws import AwsSecret
from prefect_snowflake import SnowflakeConnector, SnowflakeCredentials


@task
def setup_table(snow_connector: SnowflakeConnector) -> None:
    with snow_connector as connector:
        connector.execute(
            "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
        )
        connector.execute_many(
            "INSERT INTO customers (name, address) VALUES (%(name)s, %(address)s);",
            seq_of_parameters=[
                {"name": "Ford", "address": "Highway 42"},
                {"name": "Unknown", "address": "Space"},
                {"name": "Me", "address": "Myway 88"},
            ],
        )


@task
def fetch_data(snow_connector: SnowflakeConnector) -> list:
    all_rows = []
    with snow_connector as connector:
        while True:
            new_rows = connector.fetch_many("SELECT * FROM customers", size=2)
            if len(new_rows) == 0:
                break
            all_rows.append(new_rows)
    return all_rows


@flow(log_prints=True)
def snowflake_flow():
    aws_secret_block = AwsSecret.load("my-snowflake-pw")
    snowflake_pw_json = aws_secret_block.read_secret()
    snowflake_pw_dict = json.loads(snowflake_pw_json)
    snowflake_pw_str = snowflake_pw_dict.get("my-snowflake-pw")

    snow_creds = SnowflakeCredentials(
        role="MYROLE",
        user="MYUSERNAME",
        account="ab12345.us-east-2.aws",
        password=snowflake_pw_str,
    )

    snow_connector = SnowflakeConnector(
        schema="MY_SCHEMA",
        database="MY_DATABASE",
        warehouse="COMPUTE_WH",
        fetch_size=1,
        credentials=snow_creds,
        poll_frequency_s=1,
    )

    setup_table(snow_connector)
    all_rows = fetch_data(snow_connector)
    print(all_rows)


if __name__ == "__main__":
    snowflake_flow()
```

Note that the flow reads the Snowflake password from the AWS Secret Manager and uses it in the `SnowflakeCredentials` block.
Then the `SnowflakeConnector` block uses the `SnowflakeCredentials` block to connect to Snowflake.

Fill in the relevant details for your Snowflake account and run the script.

Check out the [`prefect-snowflake` docs](/integrations/prefect-snowflake) for more examples of working with Snowflake.

## Next steps

Now you can turn your flow into a [deployment](/guides/prefect-deploy/) so that you and your team can run it remotely on a schedule, in response to an event, or manually.  

Make sure to specify the `prefect-aws` and `prefect-snowflake` dependencies in your work pool or deployment so that they are available to runtime.

Also ensure your compute has the AWS credentials for accessing the secret in AWS Secrets Manager.

Use this pattern to connect to other third-party services that require credentials, such as databases and APIs.
Feel free to use any cloud provider secret manager.
