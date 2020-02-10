# Configure Your Environment

## Log in to Prefect Cloud

Before you are able to use the many features of Prefect Cloud, you'll need to authenticate your local machine. This is achievable by retrieving a [Personal Access Token](/cloud/concepts/tokens.html#user) from the UI and providing it to the [Prefect Command Line Interface](/cloud/concepts/cli.html#cli).

To obtain a Personal Access Token, navigate to [https://cloud.prefect.io](https://cloud.prefect.io) and through the hamburger menu in the top left corner go **User** -> **Personal Access Tokens** -> **Create A Token**.

Lastly, authenticate your machine with Prefect Cloud:

```bash
prefect auth login -t <COPIED_USER_TOKEN>
```

::: warning CLI not installed
If the `prefect` command is not found then Prefect may not be installed. Go [here](/core/getting_started/installation.html) for instructions on how to install Prefect.
:::

## Create a Runner Token

Running deployed Flows requires an Agent being authenticated against Prefect Cloud. To do this, let's generate a `RUNNER`-scoped API token:

```bash
prefect auth create-token -n my-runner-token -r RUNNER
```

Keep this runner token handy for future steps, or store it as an environment variable:

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<COPIED_RUNNER_TOKEN>
```