# API Keys <Badge text="Cloud"/>

API keys are how clients authenticate with the Prefect Cloud API.  They encapsulate the identity of a User or a service account.  Ultimately, all clients that interact with the Prefect Cloud API must provide an API key as a Bearer Token included in the request header.

See our [API documentation](api.html) more information on how to use these keys to interact with the GraphQL API.

### User API Keys

Users can generate API keys to interact with the API with their personal permissions.  When creating an API key, you can configure the following attributes:

- **API Key Name**: A memorable name for the key
- **API Key Expiration**: An optional expiration date for the key. If no expiration is provided, the key will never expire
- **Default Tenant**: The tenant to associate with the API key. Clients using this key will default to performing actions in this tenant, but they can also provide another tenant to perform actions in.

To generate an API key for your User, navigate to Account Settings > API Keys within the UI and click "Create an API Key".

!!! tip Security best practice
When you need to create a long-lived key for CI, a Prefect Agent, or any use beyond local development, create an API key for a service account instead of for your user. Actions performed in an automated setting should not be linked to your user identity and should not require the permissions of a full user.
:::

### Service Account API Keys

Users can generate API keys for service accounts, which have permissions restricted to the tenant the service account belongs to. These keys will not inherit the full permissions of the user creating them. To create and manage your tenant's service accounts and their associated API keys, navigate to Team > Service Accounts.  

When creating an API key, you can configure the following attributes:

- **API Key Name**: The name of this key; this is useful for organizational and bookkeeping purposes
- **API Key Expiration**: An optional expiration date for the key - if no expiration is provided, the key will never expire

!!! tip Service account creation
    Note that service accounts can only be created by tenant admins.
:::

!!! tip GraphQL API
    To create an API key using GraphQL use the `create_api_key` mutation. For more information on how to use the GraphQL API go [here](api.html). For a user_id, supply either your user id or a service account id.

    ```graphql
    mutation {
      create_api_key(input: { user_id: <user_id>, name: "my-api-key" }) {
        key
      }
    }
    ```
:::


## Using API keys

To authenticate with an API key, we recommend using the CLI.

```bash
$ prefect auth login --key <YOUR-KEY>
```

This will store your key on disk and load it each time you use Prefect locally. Once you've logged in, you can easily view the tenants you belong to and switch between tenants.

You may also provide your key with an environment variable or the config. This is often preferable for CI jobs. If you want to use a tenant other than the default tenant associated with the key, you'll need to set that as well.

:::: tabs

::: tab Environment

```bash
$ export PREFECT__CLOUD__API_KEY="<YOUR-KEY>"
# Optional
$ export PREFECT__CLOUD__TENANT_ID="<TENANT-ID>"
```
:::

::: tab Prefect Config

Modify `~/.prefect/config.toml`

```toml
[cloud]
api_key = "<YOUR-KEY>"

# Optional
tenant_id = "<TENANT-ID>"
```

:::

::::


!!! tip Specifying a key for agents
    Agents will load keys from these default locations as described above, but you can also pass an override directly to the agent when you start it. For example:

    ```bash
    $ prefect agent local start --key "<YOUR-KEY>"
    ```
:::

## Querying for API key metadata

Your API key metadata can be viewed in several ways. Note that we _do not store_ your API keys and you will not be able to view the value of the key after creation. When querying for keys, you will only be able to see metadata for keys created by your user or, if the you are a tenant admin, metadata for the all service account API keys in the tenant.

:::: tabs

::: tab CLI

To see keys from the CLI, use the `prefect auth list-keys` command


```
$ prefect auth list-keys
NAME          ID                                    EXPIRES AT
test          9714235e-46ac-4fb8-9bb0-d615d5318fb9  NEVER
my_key        5441f413-4b9d-4630-8b1c-0103aa38736e  NEVER
their_key     01c0e2ea-8bfe-49e3-8c63-c477cf2ec024  2021-06-15T09:42:07.802718
```

:::

::: tab GraphQL

To query for information about API keys with GraphQL, use the `auth_api_key` query.

```graphql
query {
  auth_api_key {
    id
    name
    expires_at
    user_id
  }
}
```

Example response:

```json
  "data": {
    "auth_api_key": [
      {
        "id": "9714235e-46ac-4fb8-9bb0-d615d5318fb9",
        "name": "test",
        "expires_at": null,
        "user_id": "84ac3f7e-78b3-458c-93cf-81bd920669b8"
      },
      {
        "id": "5441f413-4b9d-4630-8b1c-0103aa38736e",
        "name": "my_key",
        "expires_at": null,
        "user_id": "b5810ca3-f90b-4698-8c22-ae958aabc992"
      },
      {
        "id": "01c0e2ea-8bfe-49e3-8c63-c477cf2ec024",
        "name": "their_key",
        "expires_at": "2021-06-15T09:42:07.802718",
        "user_id": "b5810ca3-f90b-4698-8c22-ae958aabc992"
      },
    ]
  }
```

:::

::::

## Revoking Keys

:::: tabs

::: tab UI

To revoke an API key in the UI navigate to Team Settings > Service Accounts or Account Settings > API Keys. On your list of keys click the trash bin icon next to any key in order to revoke it. A confirmation box should appear asking if you are sure you want to revoke the key.

![api key revoke](/api_key_revoke.png)

:::

::: tab CLI

To revoke an API key from the Prefect CLI, use the `prefect auth revoke-key` command. You will likely need to retrieve the ID of they key with `prefect auth list-keys` first.

```bash
$ prefect auth revoke-key --id API_KEY_ID
```

:::

::: tab GraphQL

To revoke an API key using GraphQL execute the `delete_api_key` mutation. For information on how to find an API key's ID, see [Querying for API key metadata]](api_keys.html#querying-for-api-key-metadata).

```graphql
mutation {
  delete_api_key(input: { key_id: "API_KEY_ID" }) {
    success
  }
}
```

:::

::::

## Using API keys with older versions of Prefect

!!! warning
    As of version 1.0.0, API tokens are no longer supported as an authentication method.

    This section describes how you can use API keys for authentication in place of how you may have previously used tokens.

    Note that, if you have logged in with an API key, but a token still exists on your machine, the API key will be used and the token will be ignored.
:::

If you are running a version of Prefect older than 0.15.0, note that:

- The `prefect auth login` CLI command will not work with API keys.
- The `PREFECT__CLOUD__API_KEY` setting will be ignored. 


In most cases you can use API keys as you previously used tokens. Here are a few examples where API keys are used in place of tokens.

Using an API key as a token for registering flows:
```bash
$ export PREFECT__CLOUD__AUTH_TOKEN="<YOUR-KEY>"
```

Using an API key as a token for starting an agent by CLI:
```bash
$ prefect agent local start -k "<SERVICE_ACCOUNT_API_KEY>"
```

Using an API key as a token for starting an agent by environment:
```bash
$ export PREFECT__CLOUD__AGENT__AUTH_TOKEN="<YOUR-KEY>"
$ prefect agent local start
```

## Removing API tokens

As of version 1.0.0, API tokens are no longer supported. 

If you used `prefect auth login` with an API token or had set an API token in your config or environment, you would have received warnings starting with version 0.15.0. 

`prefect auth status` will warn about existing authentication tokens and advise on removal.

If you logged in with `prefect auth login`, you can remove your token with the CLI command:

```bash
$ prefect auth purge-tokens
``` 

You can remove the tokens manually by using the command `rm -r ~/.prefect/client`.

If you set your token in the environment, you can unset it with `unset PREFECT__CLOUD__AUTH_TOKEN`.

If you set your token in the config, you will have to modify `~/.prefect/config.toml` to remove it.

If you have logged in with an API key, but a token still exists on your machine, the API key will be used and the token will be ignored.
