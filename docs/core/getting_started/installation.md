---
sidebarDepth: 0
title: Installation
---

# Installing Prefect

## Requirements

Prefect requires Python 3.6+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

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

### Optional dependencies

Prefect ships with a number of optional dependencies, which can be installed using "extras" syntax:

```bash
pip install "prefect[extra_1, extra_2]"
```

Examples of extra packages include:

- `all_extras`: includes all of the optional dependencies
- `dev`: tools for developing Prefect itself
- `templates`: tools for working with string templates
- `viz`: tools for visualizing Prefect flows
- `aws`: tools for interacting with Amazon Web Services
- `azure`: tools for interacting with Microsoft Azure
- `google`: tools for interacting with Google Cloud Platform
- `kubernetes`: tools for interacting with Kubernetes API objects
- `twitter`: tools for interacting with the Twitter API
- `airtable`: tools for interacting with the Airtable API
- `spacy`: tools for building NLP pipelines using Spacy
- `redis`: tools for interacting with a Redis database

## Running the local server and UI

Prefect includes an open-source server and UI for orchestrating and managing flows. The local server stores flow metadata in a Postgres database and exposes a GraphQL API. The local server requires [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/) to be running. If you've installed [Docker Desktop](https://www.docker.com/products/docker-desktop), you've got both of these.

::: tip Once you are ready to deploy into production, you can use [Prefect Cloud](https://www.prefect.io/cloud) to orchestrate your workflows. :::

Before running the server for the first time, run:

```
prefect backend server
``` 

This configures Prefect for local orchestration, and saves the configuration in your local `~/.prefect` directory. 

Next, to start the server, UI, and all required infrastructure, run:

```
prefect server start
```

Once all components are running, you can view the UI by opening a browser and visiting [http://localhost:8080](http://localhost:8080).

Please note that executing flows from the server requires at least one Prefect Agent to be running: `prefect agent start`.

Finally, to register any flow with the server, call `flow.register()`. For more detail, please see the [orchestration docs](https://docs.prefect.io/orchestration/).

## Docker

Prefect provides Docker images for master builds and versioned releases [here](https://hub.docker.com/r/prefecthq/prefect).

To run the latest Prefect Docker image:

```bash
docker run -it prefecthq/prefect:latest
```

Image tag breakdown:

| Tag              |     Prefect Version      | Python Version |
| ---------------- | :----------------------: | -------------: |
| latest           | most recent PyPi version |            3.7 |
| master           |       master build       |            3.7 |
| latest-python3.8 | most recent PyPi version |            3.8 |
| latest-python3.7 | most recent PyPi version |            3.7 |
| latest-python3.6 | most recent PyPi version |            3.6 |
| X.Y.Z-python3.8  |          X.Y.Z           |            3.8 |
| X.Y.Z-python3.7  |          X.Y.Z           |            3.7 |
| X.Y.Z-python3.6  |          X.Y.Z           |            3.6 |
| all_extras       | most recent PyPi version |            3.8 |
| all_extras-X.Y.Z |          X.Y.Z           |            3.8 |
