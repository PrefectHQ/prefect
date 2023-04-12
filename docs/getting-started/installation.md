---
description: Installing Prefect and configuring on supported environments.
tags:
    - installation
    - pip install
    - development
    - Linux
    - Windows
    - SQLite
    - upgrading
---


# Installation

Prefect requires Python 3.7 or later.

<p align="left">
    <a href="https://pypi.python.org/pypi/prefect/" alt="Python Versions">
        <img src="https://img.shields.io/pypi/pyversions/prefect?color=0052FF&labelColor=090422" /></a>
    <a href="https://pypi.python.org/pypi/prefect/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect?color=0052FF&labelColor=090422"></a>
</p>

We recommend installing Prefect using a Python virtual environment manager such as `pipenv`, `conda`, or `virtualenv`/`venv`.

!!! success "Upgrading from Prefect 1 to Prefect 2"
    If you're upgrading from Prefect 1 to Prefect 2, we recommend creating a new environment. Should you encounter any issues when upgrading, this ensures being able to roll back to a known working state easily.

!!! warning "Windows and Linux requirements"
    See [Windows installation notes](#windows-installation-notes) and [Linux installation notes](#linux-installation-notes) for details on additional installation requirements and considerations.

## Install Prefect

The following sections describe how to install Prefect in your development or execution environment.

### Installing the latest version

Prefect is published as a Python package. To install the latest Prefect release, run the following in a shell or terminal session:

<div class="terminal">
```bash
pip install -U prefect
```
</div>

To install a specific version, specify the version, such as:

<div class="terminal">
```bash
pip install -U "prefect==2.8.6"
```
</div>

Find the available release versions in the [Prefect Release Notes](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md) or the [PyPI release history](https://pypi.org/project/prefect/#history).

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
$ cd prefect
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
Version:             2.8.6
API version:         0.8.4
Python version:      3.11.0
Git commit:          d0f14f17
Built:               Tue, Jan 3, 2023 8:46 AM
OS/Arch:             darwin/arm64
Profile:             default
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    3.40.0
```
</div>

## Windows installation notes

Prefect supports running Prefect flows on Windows.

!!! note "Prefect on Windows requires Python 3.8 or later"
    Make sure to use Python 3.8 or higher when running a Prefect agent on Windows.

You can install and run Prefect as described above via Windows PowerShell, the Windows Command Prompt, or [`conda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html). Note that, after installation, you may need to manually add the Python local packages `Scripts` folder to your `Path` environment variable.

The `Scripts` folder path looks something like this (the username and Python version may be different on your system):

```bash
C:\Users\Terry\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.9_qbz5n2kfra8p0\LocalCache\local-packages\Python39\Scripts
```

Watch the `pip install` installation output messages for the `Scripts` folder path on your system.

If using Windows Subsystem for Linux (WSL), see [Linux installation notes](#linux-installation-notes).

## Linux installation notes

Currently, Prefect requires SQLite 3.24 or newer.

When installing Prefect and using a SQLite backend on Linux, make sure your environment is using a compatible SQLite version. Some versions of Linux package a version of SQLite that cannot be used with Prefect.

Known compatible releases include:

- Ubuntu 22.04 LTS
- Ubuntu 20.04 LTS

You can also:

- Use [Prefect Cloud](/ui/cloud/) as your API server and orchestration engine.
- Use the `conda` virtual environment manager, which enables configuring a compatible SQLite version.
- [Configure a PostgeSQL database](/concepts/database/#configuring_a_postgresql_database) as the Prefect backend database.
- [Install SQLite on Red Hat Enterprise Linux (RHEL)](#install-sqlite-on-rhel).
- Use [Prefect Cloud](/ui/cloud/) as your API server and orchestration engine.


## Using Self-Signed SSL Certificates

If you're using a self-signed SSL certificate, you need to configure your
environment to trust the certificate. This is usually done by adding the
certificate to your system bundle and pointing your tools to use that bundle
by configuring the `SSL_CERT_FILE` environment variable.

If the certificate is not part of your system bundle you can set the
`PREFECT_API_TLS_INSECURE_SKIP_VERIFY` to `True` to disable certificate
verification altogether.

***Note:*** This is not secure and so is recommended only for testing!


## Proxies

Prefect supports communicating via proxies through environment variables. Simply set `HTTPS_PROXY` and `SSL_CERT_FILE` in your environment, and the underlying network libraries will route Prefect’s requests appropriately. You can read more about this in the article [Using Prefect Cloud with proxies](https://discourse.prefect.io/t/using-prefect-cloud-with-proxies/1696).

## External requirements

While Prefect works with many of your favorite tools and Python modules, it has a few external dependencies.

### SQLite

Prefect uses SQLite as the default backing database, but it is not packaged with the Prefect installation. Most systems will have SQLite installed already since it is typically bundled as a part of Python. Prefect requires SQLite version 3.24.0 or later.

You can check your SQLite version by executing the following command in a terminal:

<div class="terminal">
```bash
$ sqlite3 --version
```
</div>

Or use the Prefect CLI command `prefect version`, which prints version and environment details to your console, including the server database and version. For example:

<div class="terminal">
```
$ prefect version
Version:             2.8.6
API version:         0.8.4
Python version:      3.11.0
Git commit:          d0f14f17
Built:               Tue, Jan 3, 2023 8:46 AM
OS/Arch:             darwin/arm64
Profile:             default
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    3.40.0
```
</div>

### Install SQLite on RHEL

The following steps are needed to install an appropriate version of SQLite on Red Hat Enterprise Linux (RHEL).

Note that some RHEL instances have no C compiler, so you may need to check for and install `gcc` first:

<div class="terminal">
```bash
yum install gcc
```
</div>

Download and extract the tarball for SQLite.

<div class="terminal">
```bash
wget https://www.sqlite.org/2022/sqlite-autoconf-3390200.tar.gz
tar -xzf sqlite-autoconf-3390200.tar.gz
```
</div>

Change to the extracted SQLite folder, then build and install SQLite.

<div class="terminal">
```bash
cd sqlite-autoconf-3390200/
./configure
make
make install
```
</div>

Add `LD_LIBRARY_PATH` to your profile.

<div class="terminal">
```bash
echo 'export LD_LIBRARY_PATH="/usr/local/lib"' >> /etc/profile
```
</div>

Restart your shell to register these changes.

Now you can install Prefect using `pip`.

<div class="terminal">
```bash
pip3 install prefect
```
</div>

## Using Prefect in an environment with HTTP proxies

If you are using Prefect Cloud or hosting your own Prefect server instance, the Prefect library
will connect to the API via any proxies you have listed in the `HTTP_PROXY`,
`HTTPS_PROXY`, or `ALL_PROXY` environment variables.  You may also use the `NO_PROXY`
environment variable to specify which hosts should not be sent through the proxy.

For more information about these environment variables, see the [cURL
documentation](https://everything.curl.dev/usingcurl/proxies/env).

## Upgrading from Prefect beta

The following sections provide important notes for users upgrading from Prefect 2 beta releases.

### Upgrading to 2.0b6

In Prefect 2.0b6 we added breaking changes with respect to the [Blocks API](/api-ref/prefect/blocks/storage/). This API is an important abstraction you may have used already to create default [Storage](/concepts/storage/) or specifying `flow_storage` as part of a [`DeploymentSpec`](/concepts/deployments/#deployment-specifications). As a result, the backend API in 2.0b6 is incompatible with previous Prefect client versions.

After the upgrade, your data will remain intact, but you will need to upgrade to 2.0b6 to continue using the Cloud 2 API.

Actions needed to upgrade:

- Upgrade Prefect Python package: `pip install -U "prefect>=2.0b6"`
- Restart any agent processes.
- If you are using an agent running on Kubernetes, update the Prefect image version to 2.0b6 in your Kubernetes manifest and re-apply the deployment.

You don't need to recreate any deployments or pause your schedules &mdash; stopping your agent process to perform an upgrade may result in some late runs, but those will be picked up once you restart your agent, so Don't Panic!

### Upgrading to 2.0a10

Upgrading from Prefect version 2.0a9 or earlier requires resetting the Prefect database.

Prior to 2.0a10, Prefect did not have database migrations and required a hard reset of the database between versions. Now that migrations have been added, your database will be upgraded automatically with each version change. However, you must still perform a hard reset of the database if you are upgrading from 2.0a9 or earlier.

Resetting the database with the CLI command `prefect server database reset` is not compatible a database from 2.0a9 or earlier. Instead, delete the database file `~/.prefect/prefect.db`. Prefect automatically creates a new database on the next write.

!!! warning "Resetting the database deletes data"
    Note that resetting the database causes the loss of any existing data.
