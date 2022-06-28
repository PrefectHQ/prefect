# Secrets

## Overview

Very often, workflows require sensitive information to run: API keys, passwords, tokens, credentials, etc. As a matter of best practice, such information should never be hardcoded into a workflow's source code, as the code itself will need to be guarded. Furthermore, sensitive information should not be provided via a Prefect `Parameter`, because Parameters, like many tasks, can have their results stored.

Prefect provides a mechanism called `Secrets` for working with sensitive information.

- `Secret` tasks, which are special tasks that can be used in your flow when working with sensitive information. Unlike regular tasks, `Secret` tasks are designed to access sensitive information at runtime and use a special `SecretResult` to ensure the results are not stored.
- The `prefect.client.secrets` API, which provides a lower-level interface for working with sensitive information. This API can be used where tasks are unavailable, including notifications, state handlers, and result handlers.

The most common case for secrets is to authenticate to third-party systems. For more information on best practices to do so, see our deployment recipe on [Third Party Authentication](../../orchestration/recipes/third_party_auth.md).

!!! tip Keep secrets secret!
    Though Prefect takes steps to ensure that `Secret` objects do not reveal sensitive information, other tasks may not be so careful. Once a secret value is loaded into your flow, it can be used for any purpose. Please use caution anytime you are working with sensitive data.


## Mechanisms

### Local Context

The base `Secret` class first checks for secrets in local context, under `prefect.context.secrets`. This is useful for local testing, as secrets can be added to context by setting environment variables matching the configuration syntax `PREFECT__CONTEXT__SECRETS__{SECRETNAME}={SECRETVALUE}`. (Learn more about configuration in our [Configuration concept docs](configuration.md).)

For example, given an environment with the environment variable `PREFECT__CONTEXT__SECRETS__FOO=mypassword`, the value `"mypassword"` could be retrieved by using a `PrefectSecret` task or by using the Secrets API directly, as shown below.

`PrefectSecret`:

```python
>>> from prefect.tasks.secrets import PrefectSecret
>>> p = PrefectSecret('foo')
>>> p.run()
'mypassword'
```

Secrets API:

```python
>>> from prefect.client.secrets import Secret
>>> s = Secret("FOO")
>>> s.get()
'mypassword'
```

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

```bash
export PREFECT__CONTEXT__SECRETS__AWS_CREDENTIALS='{"ACCESS_KEY": "abcdef", "SECRET_ACCESS_KEY": "ghijklmn"}'
```

Then all Prefect usages of AWS credentials will default to using the values in that dictionary.

## External Secrets Engines

### Hashicorp Vault

The ability to integrate with an existing [Hashicorp Vault](https://www.vaultproject.io/) client to retrieve secrets is possible via the `VaultSecret` class.

The `VaultSecret` class works similarly to the base `Secrets` class, with the addition of Vault connection credentials, supplied via a Prefect secret named `VAULT_CREDENTIALS`. With the supplied credentials a secret can be retrieved from the Vault instance using the `"<mount_point>/<path>"` of the remote secret.

#### Vault Server

The Vault server address is defined via an environment variable `VAULT_ADDR` as outlined in the [Vault documentation](https://www.vaultproject.io/docs/commands#vault_addr).
The VaultSecret class supports both `VAULT_ADDR` and `vault_addr`.


#### Authentication methods

`VaultSecret` exposes a number of authentication mechanisms, made available in the order of precedence:

1. [token](https://www.vaultproject.io/docs/auth/token): `{ 'VAULT_TOKEN: '<token>' }`

2. [appRole](): `{ 'VAULT_ROLE_ID': '<role-id>', 'VAULT_SECRET_ID': '<secret-id>' }`

3. [kubernetesRole](https://www.vaultproject.io/docs/auth/kubernetes): `{ 'VAULT_KUBE_AUTH_ROLE': '<>', 'VAULT_KUBE_AUTH_PATH': '<>' 'VAULT_KUBE_TOKEN_FILE': '<>' }`

For example, given the `VAULT_CREDENTIALS='{"VAULT_TOKEN": "<token>" }'`, the value `"token"` will be used to autheticate against the Vault instance specified by the `VAULT_ADDR` using the token based authentication mechanism.

```bash
export VAULT_ADDR='http://vault.example.com'
export PREFECT__CONTEXT__SECRETS__VAULT_CREDENTIALS='{"VAULT_TOKEN": "<token>"}'
```

```python
from prefect.tasks.secrets.vault_secret import VaultSecret

secret = VaultSecret("secret/test/path/to/secret").run()
```
