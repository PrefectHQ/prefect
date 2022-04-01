---
description: Learn about contributing to Prefect 2.0.
tags:
    - open source
    - contributing
    - development
    - standards
---

# Contributing

Thanks for considering contributing to Prefect!

## Setting up a development environment

First, you'll need to download the source code and install an editable version of the Python package:

```bash
# Clone the repository and switch to the 'orion' branch
git clone https://github.com/PrefectHQ/prefect.git
git checkout orion
# Install the package with development dependencies
pip install -e ".[dev]"
# Setup pre-commit hooks for required formatting
pre-commit install
```

If you don't want to install the pre-commit hooks, you can manually install the formatting dependencies with:

```bash
pip install $(./scripts/precommit-versions.py)
```

You'll need to run `black` and `isort` before a contribution can be accepted.

## Contribution standards and best practices

Coming soon...

## Developer tooling

The Orion CLI provides several helpful CLI commands to aid development.

Start all services with hot-reloading on code changes (requires UI dependencies to be installed):

```bash
prefect dev start
```

Start an Orion API that reloads on code changes:

```bash
prefect dev api
```

Start an Orion agent that reloads on code changes:

```bash
prefect dev agent
```

### UI development

Developing the Orion UI requires that [npm](https://github.com/npm/cli) is installed.


Start a development UI that reloads on code changes:

```bash
prefect dev ui
```

Build the static UI (the UI served by `prefect orion start`):

```bash
prefect dev build-ui
```


### Kubernetes development

Generate a manifest to deploy a development API to a local kubernetes cluster:

```bash
prefect dev kubernetes-manifest
```

To access the Orion UI running in a Kubernetes cluster, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster. For example:

```bash
kubectl port-forward deployment/orion 4200:4200
```

This forwards port 4200 on the default internal loop IP for localhost to the “orion” deployment. 

To tell the local `prefect` command how to communicate with the Orion API running in Kubernetes, set the `PREFECT_API_URL` environment variable:

```bash
export PREFECT_API_URL=http://localhost:4200/api
```

Since you previously configured port forwarding for the localhost port to the Kubernetes environment, you’ll be able to interact with the Orion API running in Kubernetes when using local Prefect CLI commands.

For a demonstration, see the [Running flows in Kubernetes](/tutorials/kubernetes-flow-runner/) tutorial.

