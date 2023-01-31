# Installation

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

## Basic installation

Prefect requires Python 3.7+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

To install Prefect, run:

:::: tabs
::: tab Pip

```bash
$ pip install prefect
```

:::

::: tab Conda

```bash
$ conda install -c conda-forge prefect
```

:::

::: tab Pipenv

```bash
pipenv install --pre prefect
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


