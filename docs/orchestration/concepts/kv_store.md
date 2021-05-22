# KV Store <Badge text="Cloud"/>

Key Value Store is a managed metadata database within Prefect Cloud.

**Keys** are strings. **Values** are json blobs.

The number of key value pairs allowed is limited by license, starting with 50 pairs on the Free tier. Values are limited to 1 MB in size.

Key value pairs can be configured via the Prefect CLI, Python client, API, and UI.

## UI

You can view, update, and delete key value pairs on the [KV Store page](https://cloud.prefect.io/team/kv) of the UI.  

## Setting Key Value Pairs

Setting a key value pair will overwrite the existing value if the key exists.

:::: tabs
::: tab Prefect library
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

## Getting the Value of a Key

:::: tabs
::: tab Prefect library
```python
from prefect.backend import get_key_value
value = get_key_value(key="foo")
```
:::
::: tab CLI
```bash
$ prefect kv get foo
Key foo has value bar
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

## Deleting Key Value Pairs

:::: tabs
::: tab Prefect library
```python
from prefect.backend import delete_key
success = delete_key(key="foo")
```
:::
::: tab CLI
```bash
$ prefect kv delete foo
Key foo has been deleted
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

## Listing Keys

:::: tabs
::: tab Prefect library
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