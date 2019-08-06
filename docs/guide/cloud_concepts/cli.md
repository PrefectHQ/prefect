# CLI

In conjunction with both the GraphQL API and the UI, Prefect offers a fully integrated CLI for working with Prefect Cloud. With the GraphQL API being the backbone for communicating with Prefect Cloud, we have designed the CLI to operate as a wrapper for GraphQL queries and mutations.

In this current state the Prefect CLI functions mainly as a way to read Prefect Cloud metadata as well as a lightweight way to perform some more functional tasks such as running a flow that was deployed to Cloud.

::: warning Commands subject to change!
The CLI is being built to comply with Cloud user demands on what is deemed useful. Therefore the names and outputs of some of these are subject to change during the Cloud rollout process.
:::

## Interacting with the CLI

Once you have Prefect installed (either through pip or conda) you may begin working with the CLI directly in your terminal. To see the CLI simply run `prefect` from the command line and you should see an output similar to the one below:

```
$ prefect
Usage: prefect [OPTIONS] COMMAND [ARGS]...

  The Prefect CLI for creating, managing, and inspecting your flows.

  Note: a Prefect Cloud API token is required for all Cloud related commands. If a token
  is not set then run `prefect auth login` to set it.

  Query Commands:
      get         List high-level object information
      describe    Retrieve detailed object descriptions
      summarize   Aggregate query information

  Execution Commands:
      execute     Execute a flow's environment
      run         Run a flow

  Setup Commands:
      auth        Handle Prefect Cloud authorization

  Miscellaneous Commands:
      version     Get your current Prefect version
      config      Output your Prefect config

Options:
  -h, --help  Show this message and exit.
```

From this help output you can see that the commands are broken into the categories `query`, `execution`, `setup`, and `miscellaneous`.
