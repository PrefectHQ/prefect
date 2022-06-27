# Installation

## Basic installation

Prefect requires Python 3.7+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

To install Prefect, run:

Pip:

```bash
pip install prefect
```

Conda:

```bash
conda install -c conda-forge prefect
```

Pipenv:

```bash
pipenv install --pre prefect
```

## Installing optional dependencies

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


