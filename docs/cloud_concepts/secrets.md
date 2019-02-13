# Secrets

Secrets represent sensitive key / value pairs that might be required during execution of your Flow.  As an example,
the [ability to receive slack notifications from Prefect](../tutorials/slack-notifications.html#using-your-url-to-get-notifications) relies on a secret
URL.  It is easy to imagine other examples of Secrets that might be relevant, such as API credentials.

## Setting a Secret
As with everything in Prefect, there are two standard modes of operation: "local execution", intended mainly for testing or running non-production Flows, and "cloud execution" which utilizes the full Prefect backend.  

### Locally
During local execution, Secrets can easily be set and retrieved from your configuration file.  First, in your user configuration file set the `use_local_secrets` flag in the `[cloud]` section to `true`:
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
with however many key / value pairs you'd like.  

::: tip You don't have to store raw values in your config
Prefect will interpolate certain values from your OS environment, so you can specify values from environment variables via `"$ENV_VAR"`.
:::

### In Cloud

To set a secret in Prefect Cloud, simply issue the following simple GraphQL mutation:
```graphql
mutation{
  setSecret(input: {name: "KEY", value: "VALUE"}){
    success
  }
}
```

## Using a Secret

Secrets can be used anywhere, at any time.  This includes, but is not limited to:
- Tasks
- state handlers
- callbacks
- result handlers

Creating a Secret and pulling its value is as simple as:
```python
from prefect.client import Secret

s = Secret("NAME")
s.get() # returns the value
```

Note that `s.get()` will not work locally unless `use_local_secrets` is set to `true` in your config.  To pull a Secret value from Cloud requires admin-level permissions.

## Querying for Secrets

Viewing all secrets by name:

```graphql
query {
  secret(order_by: { name: asc }) {
    name
  }
}
```

::: warning Secrets are secret
You cannot query for the value of a Secret after it has been set.  These values are only available during Cloud execution.
:::
