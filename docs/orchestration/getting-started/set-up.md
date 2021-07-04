# Orchestration Layer

## Server or Cloud?

If you want an orchestration layer, you have two options:  Prefect Core server and Prefect Cloud. You can see an overview and comparison on the [welcome](/orchestration/README.md) page. 

Once you decie which option is best for you, follow the instructions below to set up server or Cloud. 

:::: tabs
::: tab Cloud

## Create (or log into) your Prefect Cloud account
To use Prefect Cloud you'll need to go to our Prefect Cloud web app and set up (or join) an account.  

## Set backend 

Once you have an account set up, make sure your backend is set to use Prefect Cloud by running 

  ```bash
$ prefect backend cloud
```

Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Authenticate with Prefect Cloud 

Next you'll need to authenticate with the backend before you can proceed further.

### Create an API key and login

To authenticate, you'll need to create an [API Key](/orchestration/concepts/api_keys.md) and save it. 

- Login to [https://cloud.prefect.io](https://cloud.prefect.io)
- Navigate to the [API Keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Login with the Prefect CLI `prefect auth login --key <YOUR-KEY>`

**IS THIS STILL POSSIBLE?*** - Do we need to update the UI Tutorial again?

- Save the key locally either in your `~/.prefect/config.toml` config file, or as an environment variable:

```bash
# ~/.prefect/config.toml
[cloud]
auth_token = <API_KEY>
```

```bash
export PREFECT__CLOUD__AUTH_TOKEN=<API_KEY>
```

# Create a Service Account Key

Running deployed Flows with an [Agent](https://docs.prefect.io/orchestration/agents/overview.html) also requires an API key for the Agent. You can create one in the [Service Accounts](/team/service-accounts) page of the UI.

You can save it locally either in your `~/.prefect/config.toml` config file, or as an environment variable:

```bash
# ~/.prefect/config.toml
[cloud.agent]
auth_token = <SERVICE_ACCOUNT_API_KEY>
```

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<SERVICE_ACCOUNT_API_KEY>
```

:::

::: tab Core server 

Prefect Core server is included with the Prefect Core python package you installed earlier in the quick start guide.  Server requires Docker and Docker Compose to be installed. If you have Docker Desktop on your machine, you've got both of these. 

## Set backend 

Your first step is to make sure your backend is set to use Prefect Core server by running 

  ```bash
$ prefect backend server
```
Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Start server

You can start server by running 

```bash
$ prefect server start
```

Ensure that you have docker installed on whichever machine you are running server. 

You should see a welcome message and be able to navigate to the server UI at http://localhost:8080

:::

::::