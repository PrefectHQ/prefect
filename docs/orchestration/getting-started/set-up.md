# Orchestration Layer

## Server or Cloud?

If you want an orchestration layer, you have two options:  Prefect Server and Prefect Cloud. You can see an overview and comparison on the [welcome](/orchestration/README.md) page. 

Once you decide which option is best for you, follow the instructions below to set up Server or Cloud. 

:::: tabs
::: tab Cloud

## Create (or log into) your Prefect Cloud account
To use Prefect Cloud you'll need to go to login to (or set up an account for) Prefect Cloud at [https://cloud.prefect.io](https://cloud.prefect.io).

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

- Navigate to the [API Keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Login with the Prefect CLI `prefect auth login --key <YOUR-KEY>`

To learn more about API Keys including how to save them, set them through environment varaiables and how to use API Keys connected to a service account, check out the [API Key documentation](/orchestration/concepts/api_keys.md). 

:::

::: tab Server 

Prefect Server is included with the Prefect Core python package you installed earlier in the quick start guide.  Server requires Docker and Docker Compose to be installed. If you have Docker Desktop on your machine, you've got both of these. 

## Set backend 

Your first step is to make sure your backend is set to use Prefect Server by running 

  ```bash
$ prefect backend server
```
Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Start Server

You can start Server by running 

```bash
$ prefect server start
```

Ensure that you have docker installed on whichever machine you are running server. 

You should see a welcome message and be able to navigate to the server UI at http://localhost:8080

:::

::::