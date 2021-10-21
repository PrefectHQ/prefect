---
title: Overview and Setup
---

<div align="center" style="margin-top:50px; margin-bottom:40px">
    <img src="/orchestration/tutorial/header-illustration.svg" width=500>
</div>

# Overview and Setup

Welcome to the Prefect Deployment Tutorial! This tutorial will cover:

- Setting up your environment to use either [Prefect
  Cloud](https://cloud.prefect.io) or [Prefect
  Server](/orchestration/server/overview.md)
- Configuring and registering your first Flow
- Using a [Prefect Agent](/orchestration/agents/overview.md) to run that Flow

If you haven't yet, you might want to go through the [Prefect Core
Tutorial](/core/tutorial/01-etl-before-prefect.html),
which covers in greater detail how to write Prefect Flows.

## Install Prefect

Before starting the tutorial, you'll need a working install of the core Prefect
library.

You can find installation instructions [here](/core/getting_started/installation.html).

## Select an Orchestration Backend

Prefect supports two different orchestration backends:

- `cloud` - our [hosted service](https://cloud.prefect.io)
- `server` - the [open source backend](/orchestration/server/overview.md),
  deployed on your infrastructure

To use Prefect with either backend, you must first select that backend via
the CLI:

:::: tabs
::: tab Cloud

```bash
$ prefect backend cloud
```

:::

::: tab Server

```bash
$ prefect backend server
```

:::
::::

Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Authenticating with Prefect Cloud <Badge text="Cloud"/>

If you're using Prefect Cloud, you'll also need to authenticate with the
backend before you can proceed further.

### Create an API key and login

To authenticate, you'll need to create an [API key](/orchestration/concepts/api_keys.md) and save it. 

- Login to [https://cloud.prefect.io](https://cloud.prefect.io)
- Navigate to the [API Keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Login with the Prefect CLI `prefect auth login --key <YOUR-KEY>`


::: tip Authentication for agents

When running deployed Flows with an [Agent](/orchestration/agents/overview.html) we recommend creating an API key associated with a service account instead of your user. See the [API keys documentation](/orchestration/concepts/api_keys.md) for details.

:::