# Overview and Setup

Welcome to the Prefect Deployment Tutorial! This tutorial will cover:

- Setting up your environment to use either [Prefect
  Cloud](https://cloud.prefect.io) or [Prefect
  Server](/orchestration/server/overview.md)
- Configuring and registering your first Flow
- Using a [Prefect Agent](/orchestration/agents/overview.md) to run that Flow

If you haven't yet, you might want to go through the [Prefect Core
Tutorial](http://localhost:8080/core/tutorial/01-etl-before-prefect.html),
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

Note that you can change backends at any time by rerunning the `prefect backend
...` command.

## Authenticating with Prefect Cloud <Badge text="Cloud"/>

If you're using Prefect Cloud, you'll also need to authenticate with the
backend before you can proceed further.

### Create a Personal Access Token

To authenticate, you'll need to create a [Personal Access
Token](/orchestration/concepts/tokens.html#user) and configure it with the
[Prefect Command Line Interface](/orchestration/concepts/cli.html#cli).

- Login to [https://cloud.prefect.io](https://cloud.prefect.io)
- In the hamburger menu in the top left corner go to **User** -> **Personal
  Access Tokens** -> **Create A Token**.
- Copy the created token
- Configure the CLI to use the access token by running

```bash
prefect auth login -t <COPIED_TOKEN>
```

### Create a Runner Token

Running deployed Flows with an [Agent](/orchestration/agents/overview.html)
also requires a `RUNNER`-scoped API token for the Agent. You can create one
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
auth_token = <COPIED_RUNNER_TOKEN>
```
:::
::: tab "Environment Variable"

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<COPIED_RUNNER_TOKEN>
```
:::
::::
