# Secrets

Prefect Secrets provide a common way to store any sensitive values (access
tokens, passwords, credentials, ...) used by your flows. Storing these values
external to your flow's source is good practice, and helps keep your
credentials safe.

Secrets can be configured in two places:

- If using Prefect Cloud, secrets can be stored directly in Cloud (these will
  be secure in [Vault](https://www.vaultproject.io) in our backend). Note that
  Prefect Server _does not_ support this feature.

- Secrets can also be set locally using environment variables or your
  `~/.prefect/config.toml` file.

Secrets are resolved locally first, falling back to Prefect Cloud (if
supported). If you're using Prefect Server, only local secrets are supported.

We recommend using secrets stored in Prefect Cloud when possible, as these can
be accessed in deployed flows in a uniform manner. Local secrets also work
fine, but may require more work to deploy to remote environments.


## Setting Cloud Secrets <Badge text="Cloud"/>

There are a few different ways to configure secrets in Prefect Cloud.

### UI

To set a secret in the UI, visit the [Secrets page](/orchestration/ui/team-settings.md#secrets).

![](/orchestration/ui/team-secrets.png)

### Prefect Client

To set a secret with the Prefect Client:

```python
from prefect import Client

client = Client()
client.set_secret(name="MYSECRET", value="MY SECRET VALUE")
```

### GraphQL <Badge text="GQL"/>

To set a secret using GraphQL, issue the following mutation:

```graphql
mutation {
  set_secret(input: { name: "MYSECRET", value: "MY SECRET VALUE" }) {
    success
  }
}
```

## Setting Local Secrets

To configure a secret locally (not using Prefect Cloud), you can set the value
in your [Prefect configuration file](/core/concepts/configuration.md) through
either the `~/.prefect/config.toml` file or an environment variable.

:::: tabs
::: tab `~/.prefect/config.toml`
```toml
[context.secrets]
MYSECRET = "MY SECRET VALUE"
```
:::
::: tab Environment Variable
```bash
$ export PREFECT__CONTEXT__SECRETS__MYSECRET="MY SECRET VALUE"
```
:::
::::

Note that this configuration only affects the environment in which it's
configured. So if you set values locally, they'll affect flows run locally or
via a [local agent](/orchetration/agents/local.md), but _not_ flows deployed
via other agents (since those flow runs happen in a different environment). To
set local secrets on flow runs deployed by an agent, you can use the `--env`
flag to forward environment variables into the flow run environment.

For example, here we configure a secret `MYSECRET` for all flow runs deployed
by a docker agent.

```bash
$ prefect agent docker start --env PREFECT__CONTEXT__SECRETS__MYSECRET="MY SECRET VALUE"
```


## Using Secrets

Though most commonly used in tasks, secrets can be used in all parts of Prefect
for loading credentials in a secure way.

### Using Secrets in Tasks

When using secrets in your tasks, it's generally best practice to pass the
secret value in as a parameter, rather than loading the secret from within your
task. This makes it easier to swap out what secret should be used, or to pass
in secret values loaded via other mechanisms.

The standard way to do this is to use a
[PrefectSecret](/api/latest/tasks/secrets.html#prefectsecret) task to load the
secret, and pass the result to your task as an argument.

```python
from prefect import task, Flow
from prefect.tasks.secrets import PrefectSecret

@task
def my_task(credentials):
    """A task that requires credentials to access something. Passing the
    credentials in as an argument allows you to change how/where the
    credentials are loaded (though we recommend using `PrefectSecret` tasks to
    load them."""
    pass

with Flow("example") as flow:
    my_secret = PrefectSecret("MYSECRET")
    res = my_task(credentials=my_secret)
```

### Using Secrets Elsewhere

To load secrets in Prefect components other than tasks, you'll need to make use
of `prefect.client.Secret`:

```python
from prefect.client import Secret

# Load the value of `MYSECRET`
my_secret_value = Secret("MYSECRET").get()
```

Where it makes sense, we recommend making the secret name configurable in your
components (e.g. passed in as a parameter, perhaps with a default value) to
support changing the secret name without changing the code. For example, the
[GitHub](/orchestration/flow_config/storage.md#github) storage class takes a
`access_token_secret` kwarg for configuring the name of the access token
secret.
