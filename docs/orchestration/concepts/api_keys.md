# API Keys <Badge text="Cloud"/>

API keys are a central component for interacting with the Prefect Cloud API.  They encapsulate who you are as a user of the system along with your memberships to your various tenants.  API keys can also be generated for Service Accounts, allowing for keys with customizable permission sets.  Ultimately, all clients that interact with the Prefect Cloud API must provide an API key as a Bearer Token included in the request header.

### User API Keys

User-based API keys function as personal access keys.  When creating an API key, you can configure the following attributes:

- **API Key Name**: The name of this key; this is useful for organizational and bookkeeping purposes
- **API Key Expiration**: An optional expiration date for the key - if no expiration is provided, the key will never expire
- **Tenant**: Which tenant to associate the key with - this key will then have all of the permissions that you have as a member of that tenant.  For example, suppose you are a member of Tenant A as a Tenant Administrator, and Tenant B as a Read-Only User.  When you create an API key associated with Tenant A, it will have the ability to perform actions at the Tenant Admin level.  On the other hand, when you create an API key associated with Tenant B, it will only be able to perform queries and no mutations.

To generate an API key for yourself, navigate to User > API Keys within the UI and click "Create an API Key".

### Service Account API Keys

Service Account-based API keys are used for processes like the Prefect Agent or CI, which require the ability to execute or register flows on behalf of a tenant.  To create and manage both your tenant's Service Accounts and Service Account API keys, navigate to Team > Service Accounts.

When creating an API key, you can configure the following attributes:

- **API Key Name**: The name of this key; this is useful for organizational and bookkeeping purposes
- **API Key Expiration**: An optional expiration date for the key - if no expiration is provided, the key will never expire

::: tip Service Account Creation
Note that Service Accounts can only be created by Tenant Admins.
:::

::: tip GraphQL API
Every action you see in the UI can always be replicated via Prefect's GraphQL API.

To create an API key using GraphQL execute the `create_api_key` mutation against `https://api.prefect.io`. For more information on how to use the GraphQL API go [here](api.html).

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

To revoke an API key with the CLI run the `revoke-token` command with the ID of the key you want to revoke. For information on how to find an API key's ID look under [Querying for Key Information](tokens.html#querying-for-key-information).

```
$ prefect auth revoke-token -i $API_KEY_ID
```

### GraphQL

To revoke an API key using GraphQL execute the `delete_api_key` mutation against `https://api.prefect.io`. For information on how to find an API key's ID look under [Querying for Key Information](tokens.html#querying-for-key-information).

```graphql
mutation {
  delete_api_key(input: { key_id: "API_KEY_ID" }) {
    success
  }
}
```

## Querying for Key Information

To query for information about a specific API key with GraphQL, execute the following query against `https://api.prefect.io`. This will allow you to query for API key information, however it never returns the value of the key itself.

```graphql
query {
  auth_api_key {
    id
    name
    expires_at
  }
}
```

## Use and Persistence of Service Account Keys

Service account keys are generally used by Prefect Agents and flows to communicate with Prefect Cloud. A service account key is provided to an agent at start and every time it deploys a flow to run it is given that key that it then uses to communicate state back to Prefect Cloud. This means that whenever a service account key is revoked, all agents and flows which are currently using it are unable to communicate with Prefect Cloud and will need to be started with a new key in order to resume their work.

There are a few ways in which you can give a service account key to an agent. Each method has an extra level of persistence.

- Provide the service account key when the agent is started via the CLI. This method means the key will need to be provided each time the agent is started.

```
$ prefect agent <AGENT TYPE> start -t SERVICE_ACCOUNT_API_KEY
```

- Specify the service account key as an environment variable. This method means the key will only be available to processes which have the variable set.

```bash
$ export PREFECT__CLOUD__AGENT__AUTH_TOKEN=SERVICE_ACCOUNT_API_KEY
```

- Manually save your service account key in `$HOME/.prefect/config.toml`. This method ensures that the key will be available at all times if it is not overridden.

```toml
[cloud.agent]
auth_token = SERVICE_ACCOUNT_API_KEY
```

For information on the use of your user-scoped API keys visit the [Prefect Cloud API](api.html) page.
