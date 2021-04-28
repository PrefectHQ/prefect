# API Keys <Badge text="Cloud"/>

API Keys are how clients authenticate with the Prefect Cloud API.  They encapsulate the identity of a User or a Service Account.  Ultimately, all clients that interact with the Prefect Cloud API must provide an API Key as a Bearer Token included in the request header.

For more information on how to use these keys to interact with the GraphQL API, go [here](api.html).
### User API Keys

Users can generate API Keys to serve as personal access keys.  When creating an API key, you can configure the following attributes:

- **API Key Name**: The name of this key
- **API Key Expiration**: An optional expiration date for the key - if no expiration is provided, the key will never expire
- **Tenant**: The tenant to associate with the key, by default - this key will inherit its associated user's permissions in all tenants to which the User has an existing membership, but the default tenant will be used when no tenant is specified.  Revoking permissions or memberships of that user will be reflected in the token.

To generate an API key for your User, navigate to User > API Keys within the UI and click "Create an API Key".

::: tip Key Management
Best Practice: When tempted to create a long-lived token for CI, a Prefect Agent, or any use beyond local development, use a Service Account API Key.  Your User API Key is effectively your identity and should be treated as such.
:::

### Service Account API Keys

Users can generate API Keys for Service Accounts, which have permissions restricted to the tenant the Service Account belongs to. These keys will not inherit the full permissions of the user creating them. To create and manage your tenant's Service Accounts and their associated API keys, navigate to Team > Service Accounts.  

When creating an API key, you can configure the following attributes:

- **API Key Name**: The name of this key; this is useful for organizational and bookkeeping purposes
- **API Key Expiration**: An optional expiration date for the key - if no expiration is provided, the key will never expire

::: tip Service Account Creation
Note that Service Accounts can only be created by Tenant Admins.
:::

::: tip GraphQL API
Every action you see in the UI can always be replicated via Prefect's GraphQL API.

To create an API key using GraphQL execute the `create_api_key` mutation against `https://api.prefect.io`. For more information on how to use the GraphQL API go [here](api.html).
For user_id, supply either a user or a service account

```graphql
mutation {
  create_api_key(input: { user_id: <user_id>, name: "my-api-key" }) {
    token
  }
}
```
:::

## Revoking Keys

### UI

To revoke an API key in the UI navigate to Team Settings > Service Accounts or User > API Keys. On your list of keys click the trash bin icon next to any key in order to delete it. A confirmation box should appear asking if you are sure you want to delete the key.

![token delete](/token_delete.png)

### CLI

To revoke an API key with the CLI run the `revoke-token` command with the ID of the key you want to revoke. For information on how to find an API key's ID look under [Querying for Key Information](api_keys.html#querying-for-key-information).

```
$ prefect auth revoke-token -i $API_KEY_ID
```

### GraphQL

To revoke an API key using GraphQL execute the `delete_api_key` mutation against `https://api.prefect.io`. For information on how to find an API key's ID look under [Querying for Key Information](api_keys.html#querying-for-key-information).

```graphql
mutation {
  delete_api_key(input: { key_id: "API_KEY_ID" }) {
    success
  }
}
```

## Querying for Key Information

To query for information about API Keys with GraphQL, execute the following query against `https://api.prefect.io`. This will return API Key information, but never the value of the key.  All User API Keys for the active User will be returned, along with any Service Account API Keys which the API Key is privileged to see in the the API Key's default tenant.  Only and all Administrators are privileged to see all Service Accounts--because all Service Accounts have the Administrator role, they can also see all API Keys for any Service Account in the tenant.

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

## Use and Persistence of Service Account Keys in Agents

Prefect Agents and Flows use Service Account API Keys to authenticate with Prefect Cloud.  A Service Account API Key is provided to an agent at start, and each agent provides its API Key to flows that it starts.  Therefore, when a Service Account API Key is revoked (or the associated Service Account is removed), all agents and flows relying upon it will fail to authenticate with Prefect Cloud, and will need to be started with a new key.  

There are a few ways in which you can give a service account key to an agent. Each method has an extra level of persistence.

- Provide the service account key when the agent is started via the CLI. This method means the key will need to be provided each time the agent is started.

```
$ prefect agent <AGENT TYPE> start -t SERVICE_ACCOUNT_API_KEY
```

- Specify the service account key as an environment variable. This method means the key will only be available in the active shell and its subshells.

```bash
$ export PREFECT__CLOUD__AGENT__AUTH_TOKEN=SERVICE_ACCOUNT_API_KEY
```

- Manually save your service account key in `$HOME/.prefect/config.toml`. This method ensures that the key will be available at all times if it is not overridden.

```toml
[cloud.agent]
auth_token = SERVICE_ACCOUNT_API_KEY
```

## Deprecation of User Access Tokens and API Tokens

API Keys replace the deprecated User Access Tokens and API Tokens, which previously followed a different paradigm.  In effect, User API Keys can be used in place of Personal Access Tokens, and Service Account API Keys should replace API Tokens (which can no longer be created in the UI), though they function slightly differently.
