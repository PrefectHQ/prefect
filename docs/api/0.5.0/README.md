---
sidebarDepth: 0
editLink: false
---


<div align="center" style="margin-bottom:40px;">
<img src="/assets/wordmark-color-horizontal.svg"  width=600 >
</div>

# API Reference

This API reference is automatically generated from Prefect's source code and unit-tested to ensure it's up to date.


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

Pefect's documentation -- including concepts, tutorials, and a full API reference -- is always available at [docs.prefect.io](https://docs.prefect.io).

[Documentation for developers](https://docs.prefect.io/guide/development/overview.html) is also available, covering code style, documentation, and testing.

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and makes sure that the rules are followed. Similarly, Prefect is responsible for making sure that workflows execute properly.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Installation

### Requirements

Prefect requires Python 3.5+.

### Install latest release

```bash
pip install prefect
```

### Install bleeding edge

```bash
git clone https://github.com/PrefectHQ/prefect.git
pip install ./prefect
```

## License

Prefect is licensed under the Apache Software License version 2.0.
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.0 on March 29, 2019 at 17:39 UTC</p>
