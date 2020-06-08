---
title: 'PIN-9: Prefect CLI'
sidebarDepth: 0
---

# PIN 9: Prefect CLI

Date: May 20, 2019
Author: Josh Meek

## Status

Accepted

## Context

A command line interface is an incredibly powerful and useful tool for many software products. Having a well rounded CLI in Prefect should be no exception. After this is adopted, Prefect Cloud will have three modes to work with: visually through the UI, programmatically through the GraphQL API, and textually through the CLI.

## Proposal

I am proposing the creation of a Prefect CLI that will be used both for Prefect Cloud control as well as local flow execution. The CLI will definitely be more Cloud focused however it will also allow for some control of locally existing flows, storage, and environments.

All of the groups and commands do not need to be built out on first pass and instead they should gradually evolve over time to suit user needs. Below I will go into small details about each group. These are not the final groups and are subject to change.

### Help Texts

Mock of the main help text when running `prefect` from the command line:
```
$ prefect
Usage: prefect [OPTIONS] COMMAND [ARGS]...

  The Prefect CLI for creating, managing, and inspecting your flows.

  Note: a Prefect Cloud auth token is required for all Cloud related commands. If a token
  is not set in your Prefect config.toml then run `prefect auth add` to set it.

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

Mock of a group's commands (from `prefect get`):
```
$ prefect get --help
Usage: prefect get [OPTIONS] COMMAND [ARGS]...

  Get commands that refer to querying Prefect Cloud metadata.

  Usage:
      $ prefect get [OBJECT]

  Arguments:
      flow-runs   Query flow runs
      flows       Query flows
      projects    Query projects
      tasks       Query tasks

  Examples:
      $ prefect get flows
      NAME      VERSION   PROJECT NAME   AGE
      My-Flow   3         My-Project     3 days ago

      $ prefect get flows --project New-Proj --all-versions
      NAME        VERSION   PROJECT NAME   AGE
      Test-Flow   2         New-Proj       22 hours ago
      Test-Flow   1         New-Proj       1 month ago

      $ prefect get tasks --flow-name Test-Flow
      NAME          FLOW NAME   FLOW VERSION   AGE          MAPPED   TYPE
      first_task    Test-Flow   1              5 days ago   False    prefect.tasks.core.function.FunctionTask
      second_task   Test-Flow   1              5 days ago   True     prefect.tasks.core.function.FunctionTask

Options:
  -h, --help  Show this message and exit.
```

### Query Commands
These commands will be strictly cloud focused. Since Prefect Cloud allows rich metadata object manipulation and inspection, the CLI can query for their information in various ways.

`prefect get` will retrieve table formatted high level information about Prefect objects

`prefect describe` will retrieve more detailed JSON formatted metadata about Prefect objects

`prefect summarize` will retrieve summary statistics over time for Prefect objects

### Execution Commands
These commands deal with actual execution of code (both Cloud and local).

`prefect execute` allows users to specify environment information from Flow objects and both the `setup` and `execute` environment functions will be run

`prefect run` allows users to run their Flows via platforms and storage options such as Cloud, local, Docker, etc...

### Setup Commands
These commands enable users to easily manipulate Prefect configuration. Whether it be setting auth tokens for Prefect Cloud or handling environment-level changes; they can happen here.

### Miscallaneous Commands
These commands do not fall into another specific group and instead deal with processes such as viewing the current Prefect version or outputting a user's local config.

## Consequences
Adopting this CLI will allow for quicker user control over Prefect Cloud directly from the command line. The only downside I see is that this is largely based on Cloud so we need to take the necessary measures to include as many useful commands for working with local Prefect only.

## Actions
First pass PR will be accompanied with this PIN after it is debated on in the proposed issue. _I already have a big CLI branch waiting to open a pull request_ if we decide that we are ready for this first pass.

Process we could take:
- Merge in first draft of CLI
- Start using it and write documentation
- Improve and iterate on useful commands
