---
sidebarDepth: 0
title: Installation
---

# Installing Prefect

## Requirements

Prefect requires Python 3.6+.

## Installation

To install Prefect, run:

```bash
pip install prefect
```

or, if you prefer to use `conda`:

```bash
conda install -c conda-forge prefect
```

or `pipenv`:

```bash
pipenv install --pre prefect
```

## Optional dependencies

Prefect ships with a number of optional dependencies, which can be installed using "extras" syntax:

```bash
pip install "prefect[extra_1, extra_2]"
```

The extra packages include:

- `all_extras`: includes all of the optional dependencies
- `dev`: tools for developing Prefect itself
- `templates`: tools for working with string templates
- `viz`: tools for visualizing Prefect flows
- `aws`: tools for interacting with Amazon Web Services
- `google`: tools for interacting with Google Cloud Platform
- `kubernetes`: tools for interacting with Kubernetes API objects
- `twitter`: tools for interacting with the Twitter API
- `airtable`: tools for interacting with the Airtable API
- `spacy`: tools for building NLP pipelines using Spacy
- `redis`: tools for interacting with a Redis database

## Running the orchestration server

Prefect Core's server is an open-source backend that can orchestrate any flows written in the Prefect Core Python API. It stores flow run metadata in a Postgres database, exposes it over a GraphQL API, and provides an interactive web UI in Vue.js.

To run the server through Docker, run the command:

```bash
prefect server up
```

Navigate in a browser to `http://localhost:8080`. You will see the Prefect Server UI.

::: tip Backend toggle
The backend can be toggled between Prefect Core's server and Prefect Cloud by running the command `prefect backend` with either `server` or `cloud` for the desired option.
:::

## Development

For developing Prefect, see the [development guide](../development/overview.md).

## Docker

Prefect provides Docker images for master builds and versioned releases [here](https://hub.docker.com/r/prefecthq/prefect).

To run the latest Prefect Docker image:

```bash
docker run -it prefecthq/prefect:latest
```

Image tag breakdown:

| Tag              | Prefect Version          | Python Version |
|------------------|:------------------------:|---------------:|
| latest           | most recent PyPi version |            3.7 |
| master           | master build             |            3.7 |
| latest-python3.8 | most recent PyPi version |            3.8 |
| latest-python3.7 | most recent PyPi version |            3.7 |
| latest-python3.6 | most recent PyPi version |            3.6 |
| X.Y.Z-python3.8  | X.Y.Z                    |            3.8 |
| X.Y.Z-python3.7  | X.Y.Z                    |            3.7 |
| X.Y.Z-python3.6  | X.Y.Z                    |            3.6 |
