# Installation

## Python setup

Prefect requires Python 3.7 or later.

We recommend installing Orion using a Python virtual environment manager such as `pipenv`, `conda` or `virtualenv`.

## Installing the latest version

Prefect is published as a Python package. To install the latest 2.0 alpha release, run the following in a shell:

```bash
pip install -U "prefect>=2.0a"
```

To install a specific version, specify the version, such as:

```bash
pip install -U "prefect=2.0a9"
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

If you'd like to install a version of Prefect for development, first clone the Prefect repository, check out the `orion` branch,
then install in editable mode with `pip`:

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
2.0a9
```
</div>

Running this command should print a familiar looking version string to your console.

## Upgrading the database

Upgrading from Prefect version 2.0a9 or earlier requires resetting the Prefect Orion database. 

With the additions of migrations to Prefect Orion, if you if install a version later than 2.0a9, but had an existing db from before, you'll need to do one of the following processes:

* Delete and rebuild the database
* Stamp and reset the database

### Delete the database file

Delete the database file `~/.prefect/orion.db`.

Prefect Orion automatically creates a new database on the next write. 

### Reset the database manually

Use the Prefect CLI to stamp the database revision table:

```bash
prefect orion database stamp
```

Using the CLI, reset the database:

```bash
prefect orion database reset
```

## External requirements

While Prefect Orion works with many of your favorite tools and Python modules, Orion has a few external dependencies.

### SQLite

Prefect Orion uses SQLite as the default backing database, but it is not packaged with the Orion installation. Most systems will have SQLite installed already since it is typically bundled as a part of Python. Orion requires SQLite version 3.24.0 or later.

You can check your SQLite version by executing the following command in a terminal:

```bash
$ sqlite3 --version
```