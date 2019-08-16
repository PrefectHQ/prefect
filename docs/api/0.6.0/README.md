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

Prefect's documentation -- including concepts, tutorials, and a full API reference -- is always available at [docs.prefect.io](https://docs.prefect.io).

## Contributing

Read about Prefect's [community](https://docs.prefect.io/guide/welcome/community.html) or dive in to the [development guides](https://docs.prefect.io/guide/development/overview.html) for information about contributions, documentation, code style, and testing.

Join our [Slack](https://join.slack.com/t/prefect-public/shared_invite/enQtNzE5OTU3OTQwNzc1LTQ5M2FkZmQzZjI0ODg1ZTBmOTc0ZjVjYWFjMWExZDAyYzBmYjVmMTE1NTQ1Y2IxZTllOTc4MmI3NzYxMDlhYWU) to chat about Prefect, ask questions, and share tips.

Prefect is committed to ensuring a positive environment. All interactions are governed by our [Code of Conduct](https://docs.prefect.io/guide/welcome/code_of_conduct.html).

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

or `pipenv`:
```
pipenv install --pre prefect
```

### Install bleeding edge

```bash
git clone https://github.com/PrefectHQ/prefect.git
pip install ./prefect
```

## License

Prefect is licensed under the Apache Software License version 2.0.
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 16, 2019 at 04:54 UTC</p>
