# Overview

Prefect includes a number of examples covering different features. These can be
viewed live in the docs, or accessed from the GitHub repo
[here](https://github.com/PrefectHQ/prefect/tree/master/examples).

When running with Prefect Cloud or Prefect Server, you can register all the
examples in a new Project by running the following:

```
# Create a new project (optional)
$ prefect create project "Prefect Examples"

# Register all the examples into the "Prefect Examples" project
$ prefect register --json https://docs.prefect.io/examples.json --project "Prefect Examples"
```

These can then be run using any agent with an ``prefect-examples`` label. For
example, to start a local agent for running the examples:

```
$ prefect agent local start -l prefect-examples
```
