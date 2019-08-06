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

From this help output you can see that the commands are broken into the categories `query`, `execution`, `setup`, and `miscellaneous`. Each category has groups (e.g. `get`, `describe`) and each group has commands for interacting with particular Prefect objects (e.g. `prefect get flows`). Every group and command is also provided with help documentation that can be accessed through `--help` or `-h`.

## Query Commands

### get

`get` is used to retrieve high level information about Prefect Cloud objects. Currently CLI users can get flows, flow-runs, projects, tasks, ang logs.

#### get flows

Running `prefect get flows` without any extra arguments will output a table of your current flows.
```
$ prefect get flows
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   2         New-Proj       22 hours ago
my-flow     1         Demo           2 weeks ago
```

To get more specific flow information you can optionally provide values for `--name`, `--version`, `--project` which will filter the table that is shown.

```
$ prefect get flows --name my-flow
NAME        VERSION   PROJECT NAME   AGE
my-flow     1         Demo           2 weeks ago
```

```
$ prefect get flows --project New-Proj
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   2         New-Proj       22 hours ago
```

```
$ prefect get flows --project New-Proj --version 1
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   1         New-Proj       1 month ago
```

By default this command shows the most recent version of a flow. To see all versions use the `--all-versions` flag.

```
$ prefect get flows --all-versions
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   2         New-Proj       22 hours ago
Test-Flow   1         New-Proj       1 month ago
my-flow     1         Demo           2 weeks ago
```

#### get flow-runs

Running `prefect get flow-runs` without any extra arguments will output a table of your most recent flow runs (default is the 10 most recent).
```
$ prefect get flow-runs
NAME                FLOW NAME    STATE      AGE             START TIME           DURATION
archetypal-terrier  my-flow      Scheduled  2 minutes ago
turquoise-gazelle   my-flow      Success    2 weeks ago     2019-07-25 18:30:04  00:00:02
agate-parakeet      my-flow      Success    2 weeks ago     2019-07-25 17:58:29  00:00:02
wonderful-boa       my-flow      Success    2 weeks ago     2019-07-25 16:37:34  00:00:02
pastoral-auk        my-flow      Success    2 weeks ago     2019-07-25 16:04:43  00:00:02
nebulous-lyrebird   my-flow      Success    2 weeks ago     2019-07-25 14:41:35  00:00:02
mighty-jellyfish    my-flow      Success    2 weeks ago     2019-07-25 14:41:30  00:00:02
coral-lemming       my-flow      Success    2 weeks ago     2019-07-25 14:40:41  00:00:02
magenta-oxpecker    my-flow      Success    2 weeks ago     2019-07-25 14:37:55  00:00:02
rapid-gibbon        my-flow      Success    2 weeks ago     2019-07-25 14:36:25  00:00:02
```

::: warning Prettier Output
In each output the `DURATION` column timestamp was trimmed in order to make the tables fit better on this page.
:::

To increase the amount retrieved you can specify a `--limit` integer. Similar to other get commands `get flow-runs` supports filtering of `--flow` and `--project` where a certain flow name or project name can be provided to filter the table.

There is an extra argument to filter only for flow runs which have started (either are currently running or have entered a finished state) by using the `--started` flag. In the output below notice that the flow run with the name `archetypal-terrier ` is missing because it has not started.

```
$ prefect get flow-runs --started
NAME                FLOW NAME    STATE      AGE             START TIME           DURATION
turquoise-gazelle   my-flow      Success    2 weeks ago     2019-07-25 18:30:04  00:00:02
agate-parakeet      my-flow      Success    2 weeks ago     2019-07-25 17:58:29  00:00:02
wonderful-boa       my-flow      Success    2 weeks ago     2019-07-25 16:37:34  00:00:02
pastoral-auk        my-flow      Success    2 weeks ago     2019-07-25 16:04:43  00:00:02
nebulous-lyrebird   my-flow      Success    2 weeks ago     2019-07-25 14:41:35  00:00:02
mighty-jellyfish    my-flow      Success    2 weeks ago     2019-07-25 14:41:30  00:00:02
coral-lemming       my-flow      Success    2 weeks ago     2019-07-25 14:40:41  00:00:02
magenta-oxpecker    my-flow      Success    2 weeks ago     2019-07-25 14:37:55  00:00:02
rapid-gibbon        my-flow      Success    2 weeks ago     2019-07-25 14:36:25  00:00:02
```

#### get projects

#### get tasks

#### get logs

### describe

## Execution Commands

## Setup Commands

## Miscellaneous Commands
