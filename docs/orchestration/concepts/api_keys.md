# API Keys <Badge text="Cloud"/>

API Keys are how clients authenticate with the Prefect Cloud API.  They encapsulate the identity of a User or a service account.  Ultimately, all clients that interact with the Prefect Cloud API must provide an API Key as a Bearer Token included in the request header.

See our [API documentation](api.html) more information on how to use these keys to interact with the GraphQL API.

### User API Keys

Users can generate API keys to interact with the API with their personal permissions.  When creating an API key, you can configure the following attributes:

- **API Key Name**: A memorable name for the key
- **API Key Expiration**: An optional expiration date for the key. If no expiration is provided, the key will never expire
- **Default Tenant**: The tenant to associate with the API Key. Clients using this key will default to performing actions in this tenant, but they can also provide another tenant to perform actions in.

To generate an API key for your User, navigate to User > API Keys within the UI and click "Create an API Key".

::: tip Key best practice
When you need to create a long-lived token for CI, a Prefect Agent, or any use beyond local development, create an API key for a service account instead of for your user. Actions performed in an automated setting should not be linked to your user identity and should not require the permissions of a full user.
:::

### Service Account API Keys

Users can generate API Keys for service accounts, which have permissions restricted to the tenant the service account belongs to. These keys will not inherit the full permissions of the user creating them. To create and manage your tenant's service accounts and their associated API keys, navigate to Team > Service Accounts.  

When creating an API key, you can configure the following attributes:

- **API Key Name**: The name of this key; this is useful for organizational and bookkeeping purposes
- **API Key Expiration**: An optional expiration date for the key - if no expiration is provided, the key will never expire

::: tip Service account creation
Note that service accounts can only be created by tenant admins.
:::

::: tip GraphQL API
Every action you see in the UI can always be replicated via Prefect's GraphQL API.

To create an API key using GraphQL execute the `create_api_key` mutation against `https://api.prefect.io`. For more information on how to use the GraphQL API go [here](api.html).
For user_id, supply either a user or a service account id.

```graphql
mutation {
  create_api_key(input: { user_id: <user_id>, name: "my-api-key" }) {
    token
  }
}
```
:::

## Querying for API key metadata

Your API key metadata can be viewed in serveral ways. Note that we _do not store_ your API keys and you will not be able to view the value of the key after creation. When querying for keys, you will only be able to see metadata for keys created by your user or, if the you are a tenant admin, metadata for the all service account API keys in the tenant. 

:::: tabs

::: CLI

To see keys from the CLI, use the `prefect auth list-keys` command


```
$ prefect auth list-keys
NAME          ID                                    EXPIRES AT
test          9714235e-46ac-4fb8-9bb0-d615d5318fb9  NEVER
my_key        5441f413-4b9d-4630-8b1c-0103aa38736e  NEVER
their_key     01c0e2ea-8bfe-49e3-8c63-c477cf2ec024  2021-06-15T09:42:07.802718
```

:::

::: GraphQL

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

::: UI

To revoke an API key in the UI navigate to Team Settings > Service Accounts or User > API Keys. On your list of keys click the trash bin icon next to any key in order to delete it. A confirmation box should appear asking if you are sure you want to delete the key.

![token delete](/token_delete.png)

:::

::: CLI

To revoke an API key from the Prefect CLI, use the `prefect auth revoke-key` command. You will likely need to retrieve the ID of they key with `prefect auth list-keys` first.

```bash
prefect auth revoke-key --id API_KEY_ID
```

:::

::: GraphQL

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


## Use and Persistence of service account Keys in Agents

Prefect Agents and Flows use service account API Keys to authenticate with Prefect Cloud.  A service account API Key is provided to an agent at start, and each agent provides its API Key to flows that it starts.  Therefore, when a service account API Key is revoked (or the associated service account is removed), all agents and flows relying upon it will fail to authenticate with Prefect Cloud, and will need to be started with a new key.  

There are a few ways in which you can give a service account key to an agent. Each method has an extra level of persistence.

- Provide the service account key when the agent is started via the CLI. This method means the key will need to be provided each time the agent is started.

```
$ prefect agent <AGENT TYPE> start -t SERVICE_ACCOUNT_API_KEY
```

- Specify the service account API key as an environment variable. This method means the key will only be available in the active shell and its subshells.

```bash
$ export PREFECT__CLOUD__AGENT__AUTH_TOKEN=SERVICE_ACCOUNT_API_KEY
```

- Manually save your service account key in `$HOME/.prefect/config.toml`. This method ensures that the key will be available at all times if it is not overridden.

```toml
[cloud.agent]
auth_token = SERVICE_ACCOUNT_API_KEY
```

::: warning Deprecation of User Access Tokens and API Tokens
API keys replace the deprecated User Access Tokens and API Tokens, which used a different authentication paradigm. In effect, User API keys can be used in place of Personal Access Tokens, and service account API keys should replace API Tokens.
:::
