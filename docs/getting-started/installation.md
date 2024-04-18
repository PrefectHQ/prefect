---
description: Installing Prefect and configuring your environment
tags:
    - installation
    - pip install
    - development
    - Linux
    - Windows
    - SQLite
    - upgrading
search:
  boost: 2
---


# Installation

Prefect requires Python 3.8 or newer.

<p align="left">
    <a href="https://pypi.python.org/pypi/prefect/" alt="Python Versions">
        <img src="https://img.shields.io/pypi/pyversions/prefect?color=0052FF&labelColor=090422" /></a>
    <a href="https://pypi.python.org/pypi/prefect/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect?color=0052FF&labelColor=090422"></a>
</p>

We recommend installing Prefect using a Python virtual environment manager such as `pipenv`, `conda`, or `virtualenv`/`venv`.

!!! info "Windows and Linux requirements"
    See [Windows installation notes](#windows-installation-notes) and [Linux installation notes](#linux-installation-notes) for details on additional installation requirements and considerations.

## Install Prefect

The following sections describe how to install Prefect in your development or execution environment.

### Installing the latest version

Prefect is published as a Python package. To install the latest release or upgrade an existing Prefect install, run the following command in your terminal:

<div class="terminal">
```bash
pip install -U prefect
```
</div>

To install a specific version, specify the version number, like this:

<div class="terminal">
```bash
pip install -U "prefect==2.16.2"
```
</div>

See available release versions in the [Release Notes](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md).

### Checking your installation

To confirm that Prefect was installed correctly, run the command `prefect version` to print the version and environment details to your console.

<div class="terminal">
```
$ prefect version

Version:             2.10.21
API version:         0.8.4
Python version:      3.10.12
Git commit:          da816542
Built:               Thu, Jul 13, 2023 2:05 PM
OS/Arch:             darwin/arm64
Profile:              local
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    3.42.0

```
</div>

### Windows installation

You can install and run Prefect via Windows PowerShell, the Windows Command Prompt, or [`conda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html). After installation, you may need to manually add the Python local packages `Scripts` folder to your `Path` environment variable.

The `Scripts` folder path looks something like this (the username and Python version may be different on your system):

```bash
C:\Users\MyUserNameHere\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts
```

Watch the `pip install` output messages for the `Scripts` folder path on your system.

If you're using Windows Subsystem for Linux (WSL), see [Linux installation notes](#linux-installation-notes).

### Linux installation

Linux is a popular operating system for running Prefect. You can use [Prefect Cloud](/ui/cloud/) as your API server, or [host your own Prefect server](/host/) backed by [PostgreSQL](/concepts/database/#configuring_a_postgresql_database).

For development, you can use [SQLite](/concepts/database/#configuring_a_sqlite_database) 2.24 or newer as your database. Note that certain Linux versions of SQLite can be problematic. Compatible versions include Ubuntu 22.04 LTS and Ubuntu 20.04 LTS.

Alternatively, you can [install SQLite on Red Hat Custom Linux (RHEL)](#install-sqlite-on-rhel) or use the `conda` virtual environment manager and configure a compatible SQLite version.

## Using a self-signed SSL certificate

If you're using a self-signed SSL certificate, you need to configure your
environment to trust the certificate. You can add the
certificate to your system bundle and pointing your tools to use that bundle by configuring the `SSL_CERT_FILE` environment variable.

If the certificate is not part of your system bundle, you can set the
`PREFECT_API_TLS_INSECURE_SKIP_VERIFY` to `True` to disable certificate verification altogether.

***Note:*** Disabling certificate validation is insecure and only suggested as an option for testing!

## Installing for development

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

See the [Contributing](/contributing/overview/) guide for more details about standards and practices for contributing to Prefect.

## SQLite

You can use [Prefect Cloud](/ui/cloud/) as your API server, or [host your own Prefect server](/host/). By default, a local Prefect server instance uses SQLite as the backing database. SQLite is not packaged with the Prefect installation, but most Python environments will already have SQLite installed.

The Prefect CLI command `prefect version` prints environment details to your console, including the server type. For example:

<div class="terminal">
```
$ prefect version
Version:             2.10.21
API version:         0.8.4
Python version:      3.10.12
Git commit:          a46cbebb
Built:               Sat, Jul 15, 2023 7:59 AM
OS/Arch:             darwin/arm64
Profile:              default
Server type:         cloud
```
</div>

### Install SQLite on RHEL

The following steps are needed to install an appropriate version of SQLite on Red Hat Custom Linux (RHEL). Note that some RHEL instances have no C compiler, so you may need to check for and install `gcc` first:

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

Move to the extracted SQLite directory, then build and install SQLite.

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

## HTTP Proxies

If you are using Prefect Cloud or hosting your own Prefect server instance, the Prefect library
will connect to the API via any proxies you have listed in the `HTTP_PROXY`,
`HTTPS_PROXY`, or `ALL_PROXY` environment variables.  You may also use the `NO_PROXY`
environment variable to specify which hosts should not be sent through the proxy.

For more information about these environment variables, see the [cURL
documentation](https://everything.curl.dev/usingcurl/proxies/env). Read more about using Prefect Cloud with proxies [here](https://discourse.prefect.io/t/using-prefect-cloud-with-proxies/1696).

## Next steps

Now that you have Prefect installed and your environment configured, check out the [Tutorial](/tutorial/) to get more familiar with Prefect.
