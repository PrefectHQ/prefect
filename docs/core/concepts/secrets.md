# Secrets

## Overview

Very often, workflows require sensitive information to run: API keys, passwords, tokens, credentials, etc. As a matter of best practice, such information should never be hardcoded into a workflow's source code, as the code itself will need to be guarded. Furthermore, sensitive information should not be provided via a Prefect `Parameter`, because Parameters, like many tasks, can have their results stored.

Prefect provides a mechanism called `Secrets` for working with sensitive information.

- `Secret` tasks, which are special tasks that can be used in your flow when working with sensitive information. Unlike regular tasks, `Secret` tasks are designed to access sensitive information at runtime and use a special `SecretResult` to ensure the results are not stored.
- The `prefect.client.secrets` API, which provides a lower-level interface for working with sensitive information. This API can be used where tasks are unavailable, including notifications, state handlers, and result handlers.

The most common case for secrets is to authenticate to third-party systems. For more information on best practices to do so, see our deployment recipe on [Third Party Authentication](../../orchestration/recipes/third_party_auth.md).

::: tip Keep secrets secret!
Though Prefect takes steps to ensure that `Secret` objects do not reveal sensitive information, other tasks may not be so careful. Once a secret value is loaded into your flow, it can be used for any purpose. Please use caution anytime you are working with sensitive data.
:::

## Mechanisms

### Local Context

The base `Secret` class first checks for secrets in local context, under `prefect.context.secrets`. This is useful for local testing, as secrets can be added to context by setting environment variables matching the configuration syntax `PREFECT__CONTEXT__SECRETS__{SECRETNAME}={SECRETVALUE}`. (Learn more about configuration in our [Configuration concept docs](configuration.md).)

For example, given an environment with the environment variable `PREFECT__CONTEXT__SECRETS__FOO=mypassword`, the value `"mypassword"` could be retrieved by using a `PrefectSecret` task or by using the secrets API directly, as shown below.

:::: tabs
::: tab PrefectSecret
```python
>>> from prefect.tasks.secrets import PrefectSecret
>>> p = PrefectSecret('foo')
>>> p.run()
'mypassword'
```
:::
::: tab Secret API
```python
>>> from prefect.client.secrets import Secret
>>> s = Secret("FOO")
>>> s.get()
'mypassword'
```
:::
::::

### Environment Variables

The `EnvVarSecret` task class reads secret values directly from environment variables.

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

### Prefect Cloud

For Cloud users, if the secret is not found in local context and `config.cloud.use_local_secrets=False`, the base `Secret` class queries the Prefect Cloud API for a stored secret. This call can only be made successfully by authenticated Prefect Cloud Agents.


## Default Secrets

A few common secrets, such as authentication keys for GCP or AWS, have a standard naming convention as Prefect secrets for use by the Prefect pipeline or tasks in Prefect's task library. If you follow this naming convention when storing your secrets in local context or environment variables, all supported Prefect interactions with those services will be automatically configured.

The following is a list of the default names and contents of Prefect Secrets that, if set and declared, can be used to automatically authenticate your flow with the listed service:

- `GCP_CREDENTIALS`: a dictionary containing a valid [Service Account Key](https://cloud.google.com/docs/authentication/getting-started)
- `AWS_CREDENTIALS`: a dictionary containing two required keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`, and an optional `SESSION_TOKEN`, which are passed directly to [the `boto3` client](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html)
- `GITHUB_ACCESS_TOKEN`: a string value of a GitHub [personal access token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line), requires `repo` scope

For example, when using local secrets, your Prefect installation can be configured to authenticate to AWS automatically by adding that specific `AWS_CREDENTIALS` key value pair into your secrets context like so:

```
export PREFECT__CONTEXT__SECRETS__AWS_CREDENTIALS='{"ACCESS_KEY": "abcdef", "SECRET_ACCESS_KEY": "ghijklmn"}'
```

Then all Prefect usages of AWS credentials will default to using the values in that dictionary.
