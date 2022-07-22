# Installation

## Basic installation

Prefect requires Python 3.7+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

::: tip 
Note with the general availability of [Prefect 2.0](https://docs.prefect.io/v2/getting-started/installation/), you will have to specify the Prefect version when installing or updating Prefect 1.0 via a package manager.
:::

To install Prefect 1.0, run:

:::: tabs
::: tab Pip

```bash
pip install "prefect==1.*"
```

:::

::: tab Conda

```bash
conda install -c conda-forge "prefect>=1.24,<2"
```

:::

::: tab Pipenv

```bash
pipenv install "prefect==1.*"
```

:::

::::

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


