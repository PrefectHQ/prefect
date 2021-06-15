# Overview

Prefect includes a number of examples covering different features. These can be
viewed live in the docs, or accessed from the GitHub repo
[here](https://github.com/PrefectHQ/prefect/tree/master/examples).

## Running with Prefect Cloud or Server

When running with Prefect Cloud or Prefect Server, you can register the
examples in a new project with the Prefect CLI. You can either register all the
examples at once, or select specific examples by name.

```
# Create a new project named "Prefect Examples"
$ prefect create project "Prefect Examples"

# Register all the examples into the "Prefect Examples" project
$ prefect register --json https://docs.prefect.io/examples.json \
    --project "Prefect Examples"

# OR register only specific examples by specifying them by name
$ prefect register --json https://docs.prefect.io/examples.json \
    --project "Prefect Examples" \
    --name "Example: Parameters" \
    --name "Example: Mapping"
```

These can then be run using any agent with a ``prefect-examples`` label. For
example, to start a local agent for running the examples:

```
$ prefect agent local start -l prefect-examples
```

If you haven't already, we recommend going through the [Orchestration
Tutorial](/orchestration/tutorial/overview.md) beforehand.
