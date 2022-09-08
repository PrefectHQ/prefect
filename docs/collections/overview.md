---
description: Prefect Collections provide pre-built tasks and flows that help you build workflows quickly.
tags:
    - tasks
    - flows
    - collections
    - task library
    - contributing
    - Airbyte
    - AWS
    - Azure
    - CubeJS
    - Dask
    - Databricks
    - dbt
    - send email
    - Fugue
    - GCP
    - GitHub
    - Great Expectations
    - Jupyter
    - MetricFlow
    - Monday
    - OpenMetadata
    - Ray
    - Slack
    - Snowflake
    - SQLAlchemy
    - Stitch
    - Transform
    - Twitter
---

# Prefect Collections

Prefect Collections are groupings of pre-built tasks and flows used to quickly build dataflows with Prefect. 

Collections are grouped around the services with which they interact. For example, to download data from an S3 bucket, you could use the `s3_download` task from the `prefect-aws` collection, or if you want to send a Slack message as part of your flow you could use the `send_message` task from the `prefect-slack` collection. 

By using Prefect Collections, you can reduce the amount of boilerplate code that you need to write for interacting with common services, and focus on outcome you're seeking to achieve.

## Usage

To use a Prefect Collection, first install the collection via `pip`. As an example, to use `prefect-aws`:

```bash
pip install prefect-aws
```

The AWS tasks and flows in that collection can then be imported and called within your flow:

```python
from prefect import flow
from prefect_aws import AwsCredentials
from prefect_aws.secrets_manager import read_secret


@flow
def connect_to_database():
    aws_credentials = AwsCredentials(
        aws_access_key_id="access_key_id",
        aws_secret_access_key="secret_access_key"
    )
    secret_value = read_secret(
        secret_name="db_password",
        aws_credentials=aws_credentials
    )

    # Use secret_value to connect to a database
```

## Available Collections

To see the list of available Prefect Collections and links to each collection's GitHub repository and documentation, please refer to the [Collection Catalog](catalog.md) in the Prefect documentation.

## Contributing Collections

Anyone can create and share a Prefect Collection and we encourage anyone interested in creating a collection to do so!

### Generating a project

To help you get started with your collection, we've created a template that gives the tools you need to create and publish your collection. 

To generate a collection from the template, run the following:

```bash
# 1. Install cookiecutter
pip install cookiecutter

# 2. Generate a Prefect Collection project
cookiecutter https://github.com/PrefectHQ/prefect-collection-template
```

After your project has been generated, refer to the MAINTAINERS.md in the generated project for information about developing your collection.

### Listing in the Collections Catalog

To list your collection in the Prefect Collections Catalog, submit a PR to the Prefect repository adding a file to the `docs/collections/catalog` directory with details about your collection. Please use `TEMPLATE.yaml` in that folder as a guide.
