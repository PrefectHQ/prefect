# Secrets

Prefect secrets are a way to store any sensitive key-value pairs to which your flow might need access. One such example is
the [secret URL used to receive Slack notifications from Prefect](../../core/tutorials/slack-notifications.html#using-your-url-to-get-notifications).
Other examples are [AWS Credentials](../../core/task_library/aws.html), [Github Access Tokens](../../core/task_library/github.html), or [Twitter API credentials](../../core/task_library/twitter.html).

Prefect Cloud persists secrets on a per-team basis using [Vault](https://www.vaultproject.io).

## Setting a secret

There are two standard modes of operation: local execution, intended mainly for testing and running non-production flows, and cloud execution, which utilizes the Prefect Cloud API.

### Local testing

During local execution, secrets can easily be set in your configuration file, or set directly in `prefect.context`. First, in your user configuration file set the `use_local_secrets` flag in the `[cloud]` section to `true`:

```
[cloud]
use_local_secrets = true
```

::: tip
When settings secrets via `.toml` config files, you can use the [TOML Keys](https://github.com/toml-lang/toml#keys) docs for data structure specifications. Running `prefect` commands with invalid `.toml` config files will lead to tracebacks that contain references to: `..../toml/decoder.py`.
:::

This is also the default setting, so you only need to change this if you've changed it yourself.

Now, to populate your local secrets you can add an additional section to your user config:

```
[context.secrets]
KEY = VALUE
```

with however many key / value pairs you'd like. This will autopopulate `prefect.context.secrets["KEY"]` with your specified value. Alternatively, you can set the `KEY` / `VALUE` pair directly:

```python
import prefect

prefect.context.setdefault("secrets", {}) # to make sure context has a secrets attribute
prefect.context.secrets["KEY"] = "VALUE"
```

::: tip You don't have to store raw values in your config
Prefect will interpolate certain values from your OS environment, so you can specify values from environment variables via `"$ENV_VAR"`. Note that secrets set this way will always result in lowercase names.
:::

### Cloud Execution

#### Core Client

To set a secret with the Core client:

```python
client.set_secret(name="my secret", value=42)
```

#### GraphQL <Badge text="GQL"/>

To set a secret using GraphQL, issue the following mutation:

```graphql
mutation {
  setSecret(input: { name: "KEY", value: "VALUE" }) {
    success
  }
}
```

::: tip You can overwrite secrets
Changing the value of a secret is as simple as re-issuing the above mutation with the new value.
:::

## Using a secret

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

Note that `s.get()` will _not_ work locally unless `use_local_secrets` is set to `true` in your config.

::: warning Secrets are secret!
You cannot query for the value of a secret after it has been set. Calls to `Secret.get()` will _only_ work during Cloud execution.
:::

## Querying for secret names <Badge text="GQL"/>

Viewing all secrets by name:

```graphql
query {
  secret(order_by: { name: asc }) {
    name
  }
}
```
