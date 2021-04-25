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

### Create an API Key

To authenticate, you'll need to create an [API Key](/orchestration/concepts/tokens.html#user) and configure it with the
[Prefect Command Line Interface](/orchestration/concepts/cli.html#cli).

- Login to [https://cloud.prefect.io](https://cloud.prefect.io)
- Navigate to the [API Keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Configure the CLI to use the key by running

```bash
prefect auth login -t <API_KEY>
```

### Create a Service Account Key

Running deployed Flows with an [Agent](/orchestration/agents/overview.html)
also requires an API key for the Agent. You can create one
using the CLI:

```bash
prefect auth create-token -n my-runner-token -s RUNNER
```

You'll need this token later in the tutorial. You can save it locally either in
your `~/.prefect/config.toml` config file, or as an environment variable:

:::: tabs
::: tab config.toml

```toml
# ~/.prefect/config.toml
[cloud.agent]
auth_token = <SERVICE_ACCOUNT_API_KEY>
```

:::
::: tab "Environment Variable"

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<SERVICE_ACCOUNT_API_KEY>
```

:::

::::
