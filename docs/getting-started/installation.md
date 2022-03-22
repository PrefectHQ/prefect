# Installation

## Python setup

Prefect requires Python 3.7 or later.

We recommend installing Prefect 2.0 using a Python virtual environment manager such as `pipenv`, `conda` or `virtualenv`.

## Installing the latest version

Prefect is published as a Python package. To install the latest 2.0 release, run the following in a shell:

```bash
pip install --pre -U prefect
```

To install a specific version, specify the version, such as:

```bash
pip install -U "prefect==2.0b1"
```

Find the available release versions in the [Prefect 2.0 Release Notes](https://github.com/PrefectHQ/prefect/blob/orion/RELEASE-NOTES.md) or the [PyPI release history](https://pypi.org/project/prefect/#history).

## Installing the bleeding edge

If you'd like to test with the most up-to-date code, you can install directly off the `orion` branch on GitHub:

```bash
pip install git+https://github.com/PrefectHQ/prefect@orion
```

!!! warning "`orion` may not be stable"
    Please be aware that this method installs unreleased code and may not be stable.

## Installing for development

If you'd like to install a version of Prefect for development, first clone the Prefect repository, check out the `orion` branch,
and install an editable version of the Python package:

```bash
# Clone the repository and switch to the 'orion' branch
git clone https://github.com/PrefectHQ/prefect.git
git checkout orion
# Install the package with development dependencies
pip install -e ".[dev]"
# Setup pre-commit hooks for required formatting
pre-commit install
```

See our [Contributing](/contributing/overview/) guide for more details about standards and practices for contributing to Prefect.

## Checking your installation

To check that Prefect was installed correctly, you can test the Prefect CLI:

<div class="termy">
```
$ prefect version
2.0a9
```
</div>

Running this command should print a familiar looking version string to your console.

## Upgrading the database

Upgrading from Prefect version 2.0a9 or earlier requires resetting the Prefect Orion database. 

Prior to 2.0a10, Prefect did not have database migrations and required a hard reset of the database between versions. Now that migrations have been added, your database will be upgraded automatically with each version change. However, you must still perform a hard reset of the database if you are upgrading from 2.0a9 or earlier.

Resetting the database with the CLI command `prefect orion database reset` is not compatible a database from 2.0a9 or earlier. Instead, delete the database file `~/.prefect/orion.db`. Prefect automatically creates a new database on the next write.

!!! warning "Resetting the database deletes data"

    Note that resetting the database causes the loss of any existing data. 

## External requirements

While Prefect works with many of your favorite tools and Python modules, it has a few external dependencies.

### SQLite

Prefect 2.0 uses SQLite as the default backing database, but it is not packaged with the Prefect installation. Most systems will have SQLite installed already since it is typically bundled as a part of Python. Prefect requires SQLite version 3.24.0 or later.

You can check your SQLite version by executing the following command in a terminal:

```bash
$ sqlite3 --version
```