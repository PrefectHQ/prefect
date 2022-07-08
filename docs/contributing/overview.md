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

<div class="terminal">
```bash
# Clone the repository and switch to the 'orion' branch
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
git checkout orion
# Install the package with development dependencies
pip install -e ".[dev]"
# Setup pre-commit hooks for required formatting
pre-commit install
# Run tests
pytest
```
</div>

If you don't want to install the pre-commit hooks, you can manually install the formatting dependencies with:

<div class="terminal">
```bash
pip install $(./scripts/precommit-versions.py)
```
</div>

You'll need to run `black` and `isort` before a contribution can be accepted.

!!! note "Windows support is under development"
    Support for Prefect on Windows is a work in progress.

    Right now, we're focused on your ability to develop and run flows and tasks on Windows, along with running the API server, orchestration engine, and UI.

    Currently, we cannot guarantee that the tooling for developing Prefect itself in a Windows environment is fully functional.

## Contribution standards and best practices

Coming soon...

## Developer tooling

The Orion CLI provides several helpful CLI commands to aid development.

Start all services with hot-reloading on code changes (requires UI dependencies to be installed):

<div class="terminal">
```bash
prefect dev start
```
</div>

Start an Orion API that reloads on code changes:

<div class="terminal">
```bash
prefect dev api
```
</div>

Start an Orion agent that reloads on code changes:

<div class="terminal">
```bash
prefect dev agent
```
</div>

### UI development

Developing the Orion UI requires that [npm](https://github.com/npm/cli) is installed.

Start a development UI that reloads on code changes:

<div class="terminal">
```bash
prefect dev ui
```
</div>

Build the static UI (the UI served by `prefect orion start`):

<div class="terminal">
```bash
prefect dev build-ui
```
</div>

### Kubernetes development

Generate a manifest to deploy a development API to a local kubernetes cluster:

<div class="terminal">
```bash
prefect dev kubernetes-manifest
```
</div>

To access the Orion UI running in a Kubernetes cluster, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster. For example:

<div class="terminal">
```bash
kubectl port-forward deployment/orion 4200:4200
```
</div>

This forwards port 4200 on the default internal loop IP for localhost to the “orion” deployment.

To tell the local `prefect` command how to communicate with the Orion API running in Kubernetes, set the `PREFECT_API_URL` environment variable:

<div class="terminal">
```bash
export PREFECT_API_URL=http://localhost:4200/api
```
</div>

Since you previously configured port forwarding for the localhost port to the Kubernetes environment, you’ll be able to interact with the Orion API running in Kubernetes when using local Prefect CLI commands.

For a demonstration, see the [Running flows in Kubernetes](/tutorials/kubernetes-flow-runner/) tutorial.
