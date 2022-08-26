# Installation

The first step to getting started with Prefect is installing the Prefect Python package. 

## Set up Python
<a href="https://pypi.python.org/pypi/prefect/" alt="PyPI version">
    <img src="https://img.shields.io/pypi/pyversions/prefect.svg" /></a>

Prefect requires Python 3.7 or later.


We recommend installing Prefect 2.0 using a Python virtual environment manager such as `pipenv`, `conda`, or `virtualenv`/`venv`.

## Install Prefect 

<a href="https://pypi.python.org/pypi/prefect/" alt="PyPI version">
    <img src="https://badge.fury.io/py/prefect.svg" /></a>

The following sections describe how to install Prefect in your development or execution environment.

!!! success "Upgrading from Prefect 1.0 to Prefect 2.0"
    If you're upgrading from Prefect 1.0 to Prefect 2.0, we recommend creating a new environment. Should you encounter any issues when upgrading, this ensures being able to roll back to a known working state easily.

### Installing the latest version

Prefect is published as a Python package. To install the latest 2.0 release, run the following in a shell or terminal session:

<div class="terminal">
```bash
pip install -U prefect
```
</div>

To install a specific version, specify the version, such as:

<div class="terminal">
```bash
pip install -U "prefect==2.0"
```
</div>

Find the available release versions in the [Prefect 2.0 Release Notes](https://github.com/PrefectHQ/prefect/blob/orion/RELEASE-NOTES.md) or the [PyPI release history](https://pypi.org/project/prefect/#history).

### Installing the bleeding edge

If you'd like to test with the most up-to-date code, you can install directly off the `main` branch on GitHub:

<div class="terminal">
```bash
pip install -U git+https://github.com/PrefectHQ/prefect
```
</div>

!!! warning "The `main` branch may not be stable"
    Please be aware that this method installs unreleased code and may not be stable.

### Installing for development

If you'd like to install a version of Prefect for development:

1. Clone the [Prefect repository](https://github.com/PrefectHQ/prefect).
2. Install an editable version of the Python package with `pip install -e`.
3. Install pre-commit hooks.

<div class="terminal">
```bash
$ git clone https://github.com/PrefectHQ/prefect.git
$ pip install -e ".[dev]"
$ pre-commit install
```
</div>

See our [Contributing](/contributing/overview/) guide for more details about standards and practices for contributing to Prefect.

### Checking your installation

To check that Prefect was installed correctly, use the Prefect CLI command `prefect version`. Running this command should print version and environment details to your console.

<div class="terminal">
```
$ prefect version
Version:             2.0
API version:         0.7.0
Python version:      3.9.10
Git commit:          6379bc53
Built:               Tue, Jul 19, 2022 12:33 PM
OS/Arch:             darwin/x86_64
Profile:             default
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    3.32.3
```
</div>

## Windows installation notes

Support for running Prefect flows on Windows became available with Prefect 2.0b6. 

You can install and run Prefect as described above via Windows PowerShell, the Windows Command Prompt, or [`conda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html). Note that, after installation, you may need to manually add the Python local packages `Scripts` folder to your `Path` environment variable. 

The `Scripts` folder path looks something like this (the username and Python version may be different on your system):

```bash
C:\Users\Terry\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.9_qbz5n2kfra8p0\LocalCache\local-packages\Python39\Scripts
```

Watch the `pip install` installation output messages for the `Scripts` folder path on your system.

If using Windows Subsystem for Linux (WSL), see [Linux installation notes](#linux-installation-notes).

!!! note "Windows support is under development"
    Support for Prefect on Windows is a work in progress. 
    
    Right now, we're focused on your ability to develop and run flows and tasks on Windows, along with running the API server, orchestration engine, and UI. 
    
    If you encounter unexpected issues, please let us know via a [GitHub issue](https://github.com/PrefectHQ/prefect/issues), [Prefect Discourse](https://discourse.prefect.io/) discussion groups, or the [Prefect Community Slack](https://www.prefect.io/slack/).

## Linux installation notes

Currently, Prefect 2.0 requires SQLite 3.24 or newer.

When installing Prefect 2.0 and using a SQLite backend on Linux, make sure your environment is using a compatible SQLite version. Some versions of Linux package a version of SQLite that cannot be used with Prefect 2.0.

Known compatible releases include:

- Ubuntu 20.04 LTS

You can also: 

- Use the `conda` virtual environment manager, which enables configuring a compatible SQLite version.
- [Configure a PostgeSQL database](/concepts/database/#configuring_a_postgresql_database) as the Prefect backend database.
- Use [Prefect Cloud](/ui/cloud/) as your API server and orchestration engine.

## Upgrading to 2.0b6

In Prefect 2.0b6 we added breaking changes with respect to the [Blocks API](/api-ref/prefect/blocks/storage/). This API is an important abstraction you may have used already to create default [Storage](/concepts/storage/) or specifying `flow_storage` as part of a [`DeploymentSpec`](/concepts/deployments/#deployment-specifications). As a result, the backend API in 2.0b6 is incompatible with previous Prefect client versions.

After the upgrade, your data will remain intact, but you will need to upgrade to 2.0b6 to continue using the Cloud 2.0 API.

Actions needed on your end to upgrade, especially as a Cloud 2.0 user:

- Upgrade Prefect 2.0 Python package: `pip install -U "prefect>=2.0b6"`
- Restart any agent processes.
- If you are using an agent running on Kubernetes, update the Prefect image version to 2.0b6 in your Kubernetes manifest and re-apply the deployment.

You don't need to recreate any deployments or pause your schedules - stopping your agent process to perform an upgrade may result in some late runs, but those will be picked up once you restart your agent, so Don't Panic!

## Upgrading to 2.0a10

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

<div class="terminal">
```bash
$ sqlite3 --version
```
</div>

Or use the Prefect CLI command `prefect version`, which prints version and environment details to your console, including the server database and version.

<div class="terminal">
```
$ prefect version
Version:             2.0
API version:         0.8.0
Python version:      3.9.10
Git commit:          6379bc53
Built:               Tue, Jul 19, 2022 12:33 PM
OS/Arch:             darwin/x86_64
Profile:             default
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    3.32.3
```
</div>
