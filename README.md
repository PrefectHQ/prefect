[![CircleCI](https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=svg&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344)](https://circleci.com/gh/PrefectHQ/prefect/tree/master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# Prefect

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](https://docs.prefect.io); get the [code](#installation); ask us [anything](mailto:help@prefect.io)!

## Hello, world! 👋

```python
from prefect import task, Flow


@task
def say_hello():
    print("Hello, world!")


with Flow('My First Flow') as flow:
    say_hello()


flow.run() # "Hello, world!"
```

## License

Prefect is alpha software under active development by Prefect Technologies, Inc. This early preview is being provided to a limited number of partners to assist with development. By accessing or using the code or documentation, you are agreeing to the [alpha software end user license agreement](https://www.prefect.io/licenses/alpha-eula).

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and makes sure that the rules are followed.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Documentation

Pefect's documentation -- including concepts, tutorials, and a full API reference -- is available at [docs.prefect.io](https://docs.prefect.io)

[Documentation for developers](https://docs.prefect.io/guide/development/overview.html) is also available, covering code style, documentation, and testing.

## Installation

### Requirements

Prefect requires Python 3.4+. Dask execution requires Python 3.5+.

### Install latest release

The latest release of Prefect is `0.4.1`. To install it with optional visualization utilities:

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
git checkout 0.4.1
pip install ".[viz]"
```

Note that the visualization package additionally requires a non-Python dependency: [graphviz](https://www.graphviz.org/download/). Perhaps the easiest way to obtain `graphviz` is with [Homebrew](https://brew.sh/):
```bash
brew install graphviz
```

### Install master branch

To install the very latest version of Prefect, we recommend an "editable" install so that you
can automatically update Prefect by pulling the latest changes:

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e ".[viz]"
```
