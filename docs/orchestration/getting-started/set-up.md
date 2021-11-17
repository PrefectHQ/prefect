# Orchestration Layer

The Prefect orchestration layer lets you move from running single flows as scripts to running, monitoring, and scheduling many flows through a single web UI. 

Prefect Cloud and the Prefect Core server provide ready-to-use backend for maintaining task and flow state and inspecting their progress regardless of where you task and flow code runs.

## Prefect Cloud and Core Server

If you want an orchestration layer, you have two options: Prefect Cloud or Prefect Core server. You can see an overview and comparison on the [welcome](/orchestration/README.md) page. 

We encourage users to try Prefect Cloud first, unless your environment has restricted access to the Internet, or you prefer a self-hosted server for which you want to build your own authentication and scaling mechanism.

This guide focusses on setting up Prefect Cloud. More information on Prefect Core server is available in the [Prefect Server documentation](/orchestration/server/overview.html).

### Create (or log into) your Prefect Cloud account

To use Prefect Cloud, log in to or set up a free-tier account for Prefect Cloud at [https://cloud.prefect.io](https://cloud.prefect.io).

If your team needs support for additional users, automations, multi-tenant permissions, SSO, and other features, you can easily [scale up to a bigger Prefect Cloud license](https://www.prefect.io/pricing/).

### Set the Prefect Cloud backend 

Once you have a Prefect Cloud account set up, configure Prefect to use the Prefect Cloud backend by running the following command: 

```bash
$ prefect backend cloud
```

Note that you can change backends between Prefect Cloud and Prefect Core server at any time by running the `prefect backend cloud` or `prefect backend server` command.

### Authenticate with Prefect Cloud 

Next you'll need to authenticate with the backend before you can proceed further.

#### Create an API key and log in

To authenticate, you'll need to create an [API Key](/orchestration/concepts/api_keys.md) and save it. 

- Navigate to the [API keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Log in with the Prefect CLI by running the following command: 

```bash
$ prefect auth login --key <YOUR-KEY>
```

To learn more about API keys including how to save them, how to set them through environment variables, and how to use API keys connected to a service account, check out the [API key documentation](/orchestration/concepts/api_keys.md). 

Once you're authenticated with Prefect Cloud, you can [Deploy a flow](/orchestration/getting-started/registering-and-running-a-flow.md), which includes creating or selecting a project, registering your flow, and starting an Agent.

