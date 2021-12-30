# Installation

## Python setup

Prefect requires Python 3.7+

We recommend installing Orion using a Python virtual environment manager such as `pipenv`, `conda` or `virtualenv`.

## Installing the latest version

Prefect is published as a Python package. To install the latest 2.0 release, run the following in a shell, using the pre-release version of Orion you want to test:

```bash
pip install -U "prefect>=<version>"
```

For example, to install the latest 2.0a6 version:

```bash
pip install -U "prefect>=2.0a6"
```

Find the available release versions in the [Orion Release Notes](https://github.com/PrefectHQ/prefect/blob/orion/RELEASE-NOTES.md) or the [PyPI release history](https://pypi.org/project/prefect/#history).


## Installing the bleeding edge

If you'd like to test with the most up-to-date code, you can install directly off the `orion` branch on GitHub:

```bash
pip install git+https://github.com/PrefectHQ/prefect@orion
```

!!! warning "`orion` may not be stable"
    Please be aware that this method installs unreleased code and may not be stable.

## Installing for development

If you'd like to install a version of Prefect for development, first clone the Prefect repository
and then install in editable mode with `pip`:

```bash
git clone https://github.com/PrefectHQ/prefect.git 
# or git clone git@github.com:PrefectHQ/prefect.git if SSH is preferred
cd prefect/
git checkout orion
pip install -e ".[dev]"
```

## Checking your installation

To check that Prefect was installed correctly, you can test the Prefect CLI:

<div class="termy">
```
$ prefect version
2.0a6
```
</div>

Running this command should print a familiar looking version string to your console.


## External requirements

While Prefect Orion works with many of your favorite tools and Python modules, Orion has a few external dependencies.

### SQLite

Prefect Orion uses SQLite3 as the default backing database, but it is not packaged with the Orion installation. Most systems will have SQLite installed already since it's part of the Python standard library. Orion requires SQLite version 3.24.0 or later.

You can check your SQLite version by executing the following command in a terminal:

```bash
$ sqlite3 --version
```