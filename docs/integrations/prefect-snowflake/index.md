# prefect-snowflake

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-snowflake/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-snowflake?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-snowflake/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-snowflake?color=26272B&labelColor=090422" /></a>
</p>

## Welcome!

The prefect-snowflake collection makes it easy to connect to a Snowflake database in your Prefect flows. Check out the examples below to get started!

## Getting Started

### Integrate with Prefect flows

Prefect works with Snowflake by providing dataflow automation for faster, more efficient data pipeline creation, execution, and monitoring.

This results in reduced errors, increased confidence in your data, and ultimately, faster insights.

To set up a table, use the `execute` and `execute_many` methods. Then, use the `fetch_many` method to retrieve data in a stream until there's no more data.

By using the `SnowflakeConnector` as a context manager, you can make sure that the Snowflake connection and cursors are closed properly after you're done with them.

Be sure to install [prefect-snowflake](#installation) and [save to block](#saving-credentials-to-block) to run the examples below!

=== "Sync"

```python
from prefect import flow, task
from prefect_snowflake import SnowflakeConnector


@task
def setup_table(block_name: str) -> None:
    with SnowflakeConnector.load(block_name) as connector:
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
def fetch_data(block_name: str) -> list:
    all_rows = []
    with SnowflakeConnector.load(block_name) as connector:
        while True:
            # Repeated fetch* calls using the same operation will
            # skip re-executing and instead return the next set of results
            new_rows = connector.fetch_many("SELECT * FROM customers", size=2)
            if len(new_rows) == 0:
                break
            all_rows.append(new_rows)
    return all_rows

@flow
def snowflake_flow(block_name: str) -> list:
    setup_table(block_name)
    all_rows = fetch_data(block_name)
    return all_rows

snowflake_flow()
```

=== "Async"

```python
from prefect import flow, task
from prefect_snowflake import SnowflakeConnector
import asyncio

@task
async def setup_table(block_name: str) -> None:
    with await SnowflakeConnector.load(block_name) as connector:
        await connector.execute(
            "CREATE TABLE IF NOT EXISTS customers (name varchar, address varchar);"
        )
        await connector.execute_many(
            "INSERT INTO customers (name, address) VALUES (%(name)s, %(address)s);",
            seq_of_parameters=[
                {"name": "Ford", "address": "Highway 42"},
                {"name": "Unknown", "address": "Space"},
                {"name": "Me", "address": "Myway 88"},
            ],
        )

@task
async def fetch_data(block_name: str) -> list:
    all_rows = []
    with await SnowflakeConnector.load(block_name) as connector:
        while True:
            # Repeated fetch* calls using the same operation will
            # skip re-executing and instead return the next set of results
            new_rows = await connector.fetch_many("SELECT * FROM customers", size=2)
            if len(new_rows) == 0:
                break
            all_rows.append(new_rows)
    return all_rows

@flow
async def snowflake_flow(block_name: str) -> list:
    await setup_table(block_name)
    all_rows = await fetch_data(block_name)
    return all_rows

asyncio.run(snowflake_flow("example"))
```

### Access underlying Snowflake connection

If the native methods of the block don't meet your requirements, don't worry.

You have the option to access the underlying Snowflake connection and utilize its built-in methods as well.

```python
import pandas as pd
from prefect import flow
from prefect_snowflake.database import SnowflakeConnector
from snowflake.connector.pandas_tools import write_pandas

@flow
def snowflake_write_pandas_flow():
    connector = SnowflakeConnector.load("my-block")
    with connector.get_connection() as connection:
        table_name = "TABLE_NAME"
        ddl = "NAME STRING, NUMBER INT"
        statement = f'CREATE TABLE IF NOT EXISTS {table_name} ({ddl})'
        with connection.cursor() as cursor:
            cursor.execute(statement)

        # case sensitivity matters here!
        df = pd.DataFrame([('Marvin', 42), ('Ford', 88)], columns=['NAME', 'NUMBER'])
        success, num_chunks, num_rows, _ = write_pandas(
            conn=connection,
            df=df,
            table_name=table_name,
            database=snowflake_connector.database,
            schema=snowflake_connector.schema_  # note the "_" suffix
        )
```

## Resources

For more tips on how to use tasks and flows in an integration, check out [Using Collections](https://docs.prefect.io/integrations/usage/)!

### Installation

Install `prefect-snowflake` with `pip`:

```bash
pip install prefect-snowflake
```

A list of available blocks in `prefect-snowflake` and their setup instructions can be found [here](https://PrefectHQ.github.io/prefect-snowflake/blocks_catalog).

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Saving credentials to block

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or saved through the UI.

Below is a walkthrough on saving a `SnowflakeCredentials` block through code.

1. Head over to https://app.snowflake.com/.
2. Login to your Snowflake account, e.g. nh12345.us-east-2.aws, with your username and password.
3. Use those credentials to fill replace the placeholders below.

```python
from prefect_snowflake import SnowflakeCredentials

credentials = SnowflakeCredentials(
    account="ACCOUNT-PLACEHOLDER",  # resembles nh12345.us-east-2.aws
    user="USER-PLACEHOLDER",
    password="PASSWORD-PLACEHOLDER"
)
credentials.save("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
```

Then, to create a `SnowflakeConnector` block:

1. After logging in, click on any worksheet.
2. On the left side, select a database and schema.
3. On the top right, select a warehouse.
3. Create a short script, replacing the placeholders below.

```python
from prefect_snowflake import SnowflakeCredentials, SnowflakeConnector

credentials = SnowflakeCredentials.load("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")

connector = SnowflakeConnector(
    credentials=credentials,
    database="DATABASE-PLACEHOLDER",
    schema="SCHEMA-PLACEHOLDER",
    warehouse="COMPUTE_WH",
)
connector.save("CONNECTOR-BLOCK-NAME-PLACEHOLDER")
```

Congrats! You can now easily load the saved block, which holds your credentials and connection info:

```python
from prefect_snowflake import SnowflakeCredentials, SnowflakeConnector

SnowflakeCredentials.load("CREDENTIALS-BLOCK-NAME-PLACEHOLDER")
SnowflakeConnector.load("CONNECTOR-BLOCK-NAME-PLACEHOLDER")
```

!!! info "Registering blocks"

Register blocks in this module to
[view and edit them](https://docs.prefect.io/ui/blocks/)
on Prefect Cloud:

```bash
prefect block register -m prefect_snowflake
```

A list of available blocks in `prefect-snowflake` and their setup instructions can be found [here](https://PrefectHQ.github.io/prefect-snowflake/blocks_catalog).

### Feedback

If you encounter any bugs while using `prefect-snowflake`, feel free to open an issue in the [prefect-snowflake](https://github.com/PrefectHQ/prefect-snowflake) repository.

If you have any questions or issues while using `prefect-snowflake`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

Feel free to star or watch [`prefect-snowflake`](https://github.com/PrefectHQ/prefect-snowflake) for updates too!

### Contributing

If you'd like to help contribute to fix an issue or add a feature to `prefect-snowflake`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Here are the steps:

1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Insert an entry to [CHANGELOG.md](https://github.com/PrefectHQ/prefect-snowflake/blob/main/CHANGELOG.md)
7. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
8. `git commit`, `git push`, and create a pull request
