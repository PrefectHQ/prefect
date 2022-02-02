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

Developing the Orion UI requires NPM to be installed.


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


