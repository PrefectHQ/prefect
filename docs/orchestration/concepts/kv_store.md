# KV Store <Badge text="Cloud"/>

Key Value Store is a managed metadata database for Prefect Cloud.

**Keys** are strings. **Values** are JSON blobs.

The number of key value pairs allowed is limited by license, starting with 10 pairs on the Free tier. Values are limited to 10 KB in size.

Key value pairs can be configured via the Prefect CLI, Python library, API, and UI.

## UI

You can view, update, and delete key value pairs on the [KV Store page](https://cloud.prefect.io/team/kv) of the UI.  

## Setting key value pairs

Setting a key value pair will overwrite the existing value if the key exists.

:::: tabs
::: tab Python client
```python
from prefect.backend import set_key_value
key_value_uuid = set_key_value(key="foo", value="bar")
```
:::
::: tab CLI
```bash
$ prefect kv set foo bar
Key value pair set successfully
```
:::
::: tab GraphQL API
```graphql
mutation {
  set_key_value(input: { key : "foo", value: "\"bar\"" }) {
    id
  }
}
```
:::
::::

## Getting the value of a key

:::: tabs
::: tab Python client
```python
from prefect.backend import get_key_value
value = get_key_value(key="foo")
```
:::
::: tab CLI
```bash
$ prefect kv get foo
Key 'foo' has value 'bar'
```
:::
::: tab GraphQL API
```graphql
query {
  key_value (where: {key: {_eq: "foo"}}) {
    value
  }
}
```
:::
::::

## Deleting key value pairs

:::: tabs
::: tab Python client
```python
from prefect.backend import delete_key
success = delete_key(key="foo")
```
:::
::: tab CLI
```bash
$ prefect kv delete foo
Key 'foo' has been deleted
```
:::
::: tab GraphQL API
```graphql
mutation {
  delete_key_value(input: { key_value_id : "35c8cabb-ab30-41c2-b464-6c2ed39f0d5b" }) {
    success
  }
}
```
:::
::::

## Listing keys

:::: tabs
::: tab Python client
```python
from prefect.backend import list_keys
my_keys = list_keys()
```
:::
::: tab CLI
```bash
$ prefect kv list
foo
my-other-key
another-key
```
:::
::: tab GraphQL API
```graphql
query {
  key_value {
    id
    key
    value
  }
}
```
:::
::::

## Using key value pairs in flows

To interact with the KV Store from a flow, call the Prefect Core library functions in a task.

For example, let's say we wanted to track the last date a flow has been executed and pick up from that date.

```python
from datetime import datetime, timedelta
import prefect
from prefect import task, Flow
from prefect.backend import set_key_value, get_key_value

LAST_EXECUTED_KEY = 'my-flow-last-executed'

@task
def get_last_execution_date():
    last_executed = get_key_value(LAST_EXECUTED_KEY)
    return datetime.strptime(last_executed, "%Y-%m-%d")

@task
def run_etl(start_date):
    logger = prefect.context.get("logger")
    while start_date <= datetime.today():
        logger.info(f"Running ETL for date {start_date.strftime('%Y-%m-%d')}")
        # do some etl
        start_date += timedelta(days=1)
    return start_date.strftime('%Y-%m-%d')

@task
def set_last_execution_date(date):
    set_key_value(key=LAST_EXECUTED_KEY, value=date)

with Flow('my-flow') as flow:
    last_executed_date = get_last_execution_date()
    final_execution_date = run_etl(last_executed_date)
    set_last_execution_date(final_execution_date)
```