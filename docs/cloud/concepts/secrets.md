# Secrets

Secrets represent sensitive key / value pairs that might be required during execution of your Flow. As an example,
the [ability to receive slack notifications from Prefect](../../core/tutorials/slack-notifications.html#using-your-url-to-get-notifications) relies on a secret
URL. It is easy to imagine other examples of Secrets that might be relevant, such as API credentials.

## Setting a Secret

As with everything in Prefect, there are two standard modes of operation: "local execution", intended mainly for testing or running non-production Flows, and "cloud execution" which utilizes the Prefect Cloud API.

### Local testing

During local execution, Secrets can easily be set in your configuration file, or set directly in `prefect.context`. First, in your user configuration file set the `use_local_secrets` flag in the `[cloud]` section to `true`:

```
[cloud]
use_local_secrets = true
```

This is also the default setting, so you only need to change this if you've changed it yourself.

Now, to populate your local secrets you can simply add an additional section to your user config:

```
[context.secrets]
KEY = VALUE
```

with however many key / value pairs you'd like.  This will autopopulate `prefect.context.secrets["KEY"]` with your specified value.  Alternatively, you can set the `KEY` / `VALUE` pair directly: 

```python
import prefect

prefect.context.setdefault("secrets", {}) # to make sure context has a secrets attribute
prefect.context.secrets["KEY"] = "VALUE"
```

::: tip You don't have to store raw values in your config
Prefect will interpolate certain values from your OS environment, so you can specify values from environment variables via `"$ENV_VAR"`.  Note that secrets set this way will always result in lowercase names.
:::

### Cloud Execution

#### Core Client

To set a secret with the Core client:

```python
client.set_secret(name="my secret", value=42)
```

#### GraphQL <Badge text="GQL"/>

With GraphQL, simply issue the following mutation:

```graphql
mutation {
  setSecret(input: { name: "KEY", value: "VALUE" }) {
    success
  }
}
```

::: tip You can overwrite Secrets
Changing the value of a Secret is as simple as re-issuing the above mutation with the new value.
:::

## Using a Secret

Secrets can be used anywhere, at any time. This includes, but is not limited to:

- tasks
- state handlers
- callbacks
- result handlers

Creating a secret and pulling its value is as simple as:

```python
from prefect.client import Secret

s = Secret("my secret") # create a secret object
s.get() # retrieve its value
```

Note that `s.get()` will *not* work locally unless `use_local_secrets` is set to `true` in your config.

::: warning Secrets are secret!
You cannot query for the value of a Cloud Secret after it has been set. Calls to `Secret.get()` will *only* work during Cloud execution.
:::

## Querying for Secret names <Badge text="GQL"/>

Viewing all secrets by name:

```graphql
query {
  secret(order_by: { name: asc }) {
    name
  }
}
```
