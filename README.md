test

## Hello, world! 👋

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](https://docs.prefect.io); get the [code](#installation); ask us [anything](mailto:help@prefect.io)!

```python
from prefect import task, Flow


@task
def say_hello():
    print("Hello, world!")


with Flow("My First Flow") as flow:
    say_hello()


flow.run() # "Hello, world!"
```

## Docs

Prefect's documentation -- including concepts, tutorials, and a full API reference -- is always available at [docs.prefect.io](https://docs.prefect.io).

[Documentation for developers](https://docs.prefect.io/guide/development/overview.html) is also available, covering code style, documentation, and testing.

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and makes sure that the rules are followed. Similarly, Prefect is responsible for making sure that workflows execute properly.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Installation

### Requirements

Prefect requires Python 3.5+.

### Install latest release

Using `pip`:

```bash
pip install prefect
```

or `conda`:

```bash
conda install -c conda-forge prefect
```

### Install bleeding edge

```bash
git clone https://github.com/PrefectHQ/prefect.git
pip install ./prefect
```

## License

Prefect is licensed under the Apache Software License version 2.0.
