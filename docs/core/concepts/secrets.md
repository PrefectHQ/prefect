# Secrets

## Overview

Very often, workflows require sensitive information to run: API keys, passwords, tokens, credentials, etc. As a matter of best practice, such information should never be hardcoded into a workflow's source code, as the code itself will need to be guarded. Furthermore, sensitive information should not be provided via a Prefect `Parameter`, because Parameters, like many tasks, can have their results stored.

Prefect provides a mechanism called `Secrets` for working with sensitive information. `Secrets` are a special kind of task; they may be instantiated and used as the input to any other task. However, `Secret` tasks differ from regular tasks in two ways:
- they access sensitive information at runtime
- they use a special `ResultHandler` to ensure that their results are not serialized

::: tip Keep secrets secret!
Though Prefect takes steps to ensure that `Secret` objects do not reveal sensitive information, other tasks may not be so careful. Once a secret value is loaded into your flow, it can be used for any purpose. Please use caution anytime you are working with sensitive data.
:::

## Mechanisms

### Local Context

The base `Secret` class first checks for secrets in local context, under `prefect.context.secrets`. This is useful for local testing, as secrets can be added to context by setting the environment variable `PREFECT__CONTEXT__SECRETS__FOO`, corresponding to `secrets.foo`.

### Prefect Cloud

If the secret is not found in local context, the base `Secret` class queries the Prefect Cloud API for a stored secret. This call can only be made successfully by authenticated Prefect Cloud Agents.

### Environment Variables

The `EnvVarSecret` class reads secret values from environment variables.

```python
from prefect import task, Flow
from prefect.tasks.secrets import EnvVarSecret

@task
def print_value(x):
    print(x)

with Flow("Example") as flow:
    secret = EnvVarSecret("PATH")
    print_value(secret)

flow.run() # prints the value of the "PATH" environment variable
```
