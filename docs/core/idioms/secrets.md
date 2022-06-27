# Authentication and Secrets in Prefect

The management of sensitive information (private keys, api access strings, passwords, etc.) is an integral aspect of production workflows. Prefect has a few ways to securely manage and use this sensitive information. This document will cover the use of local secrets _only_ however they easily translate to using [Prefect Cloud's secret management](/orchestration/concepts/secrets.html) option. For more information on Prefect Secrets visit the relevant [concept document](/core/concepts/secrets.html).

!!! warning use_local_secrets
    In order for local Secrets to be used make sure that the value of `prefect.config.use_local_secrets` is set to `True` (it is true by default).
:::

### Setting Secrets

Local Prefect Secrets can be set via similar methods to setting Prefect's [configuration](/core/concepts/configuration.html) either through a user config file or through environment variables.

For setting Secrets with a user config file edit the `config.toml` file (generally found in `~/.prefect/`) and place your secrets under `context.secrets`:

```toml
[context.secrets]

MY_SECRET = "api_key"
```

For setting Secrets with an environment variable:

```sh
export PREFECT__CONTEXT__SECRETS__MY_SECRET=api_key
```

### Using Secrets directly

Local Prefect Secrets can be retrieved directly through the Client Secrets API. This should **only** be used inside tasks and never passed between tasks. For passing Secrets between tasks you should use a [Secret task](/api/latest/tasks/secrets.html) as described below.

Functional API:
```python
from prefect import task, Flow
from prefect.client.secrets import Secret

@task
def access_secret():
    # Access your secret and now you can use it however you would like
    print(Secret("MY_SECRET").get())

with Flow("secret-retrieval") as flow:
    access_secret()
```

Imperative API:
```python
from prefect import Task, Flow
from prefect.client.secrets import Secret

class AccessSecret(Task):
    def run(self):
        # Access your secret and now you can use it however you would like
        print(Secret("MY_SECRET").get())

flow = Flow("secret-retrieval")
flow.add_task(AccessSecret())
```


### Passing Secrets between tasks

Prefect also has [Secret tasks](/api/latest/tasks/secrets.html) for passing secrets around between tasks. A Secret task is a special kind of task that has no result ever persisted. This means that you can securely provide secrets to the inputs of your tasks.

Functional API:
```python
from prefect import task, Flow
from prefect.tasks.secrets import PrefectSecret

@task
def access_secret(secret_value):
    # Access your secret and now you can use it however you would like
    print(secret_value)

with Flow("secret-retrieval") as flow:
    secret = PrefectSecret("MY_SECRET")
    access_secret(secret)
```

Imperative API:
```python
from prefect import Task, Flow
from prefect.tasks.secrets import PrefectSecret

class AccessSecret(Task):
    def run(self, secret_value):
        # Access your secret and now you can use it however you would like
        print(secret_value)

flow = Flow("secret-retrieval")

secret = PrefectSecret("MY_SECRET")

access_secret = AccessSecret()
access_secret.set_upstream(secret, key="secret_value", flow=flow)
```

