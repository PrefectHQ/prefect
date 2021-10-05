# Installation

## Python setup

Prefect requires Python 3.7+

We assume you are familiar with managing a Python installation using tools like `pip`, `conda` or `virtualenv`.

## Installing the latest version

Prefect is published as a Python package. To install it, run the following in a shell

```bash
pip install prefect==2.0a1
```

## Installing the bleeding edge

If you'd like to test with the most up-to-date code, you can install directly off the `orion` branch on GitHub:

```bash
pip install https://github.com/PrefectHQ/prefect@orion
```

!!! warning "`main` may not be stable"
    Please be aware that this method installs unreleased code and may not be stable.

## Installing for development

If you would like to install a version of Prefect for development, first clone the Prefect repository
and then install in editable mode with `pip`:

```bash
git clone https://github.com/PrefectHQ/prefect.git 
# or git clone git@github.com:PrefectHQ/prefect.git if SSH is preferred
cd prefect/
git checkout orion
pip install -e ".[dev]"
```

## Checking your installation

To check that Prefect was installed correctly, you can test the CLI

<div class="termy">
```
$ prefect version
2.0a1
```
</div>

Running this command should print a familiar looking version string to your console.
