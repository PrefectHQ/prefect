---
description: Install Prefect
tags:
    - install
    - pip install
    - development
    - Linux
    - Windows
    - SQLite
    - upgrade
search:
  boost: 2

Notes: 
- change to "Install"
- page doesn't really discuss configuration
- we should move DB content to the self-hosted page (makes this page simpler and encourages "just use Cloud")
- removing esoteric content; can be placed elsewhere if it's necessary
- point to quickstart after this instead of the tutorial
---

# Install Prefect

Prefect is published as a Python package, which requires Python 3.9 or newer. We recommend installing Prefect in a Python virtual environment. 

You also need an API server, either

* [Prefect Cloud](/ui/cloud/), a managed solution that provides strong scaling, performance, and security (view [pricing](https://www.prefect.io/pricing))

or 

* Your own hosted [Prefect server instance](/host/)

## Install with pip

To install the latest release or upgrade an existing Prefect install, run:

<div class="terminal">
```bash
pip install -U prefect
```
</div>

This command also upgrades existing Python dependencies.

To install a specific Prefect version, specify the version number:

<div class="terminal">
```bash
pip install -U "prefect==2.17.1"
```
</div>

See available release versions in the [Prefect Release Notes](https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md).

See our [Contributing guide](/contributing/overview/) for instructions on installing Prefect for development.

## Check your installation

To confirm that Prefect was installed correctly, run:

<div class="terminal">
```bash
prefect version
```
</div>

You should see output similar to:

<div class="terminal">
```bash
Version:             2.17.1
API version:         0.8.4
Python version:      3.12.2
Git commit:          d6bdb075
Built:               Thu, Apr 11, 2024 6:58 PM
OS/Arch:             darwin/arm64
Profile:              local
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    3.45.2
```
</div>

## Operating system-specific notes

### Windows

You can install and run Prefect via Windows PowerShell, the Windows Command Prompt, or [`conda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html). After installation, you may need to manually add the Python local packages `Scripts` folder to your `Path` environment variable.

The `Scripts` folder path looks something like this (the username and Python version may be different on your system):

```bash
C:\Users\MyUserNameHere\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts
```

Watch the `pip install` output messages for the `Scripts` folder path on your system.

If you're using Windows Subsystem for Linux (WSL), see [Linux installation notes](#linux-installation-notes).

### Linux installation notes

Linux is a popular operating system for running Prefect.
If you are hosting your own Prefect server instance with a SQLite database, note that certain Linux versions of SQLite can be problematic.
Compatible versions include Ubuntu 22.04 LTS and Ubuntu 20.04 LTS.

Alternatively, you can [install SQLite on Red Hat Custom Linux (RHEL)](#install-sqlite-on-rhel) or use the `conda` virtual environment manager and configure a compatible SQLite version.


## `prefect-client` library

The `prefect-client` library is a minimal installation of Prefect designed for interacting with Prefect Cloud or a remote self-hosted server instance.

`prefect-client` enables a subset of Prefect's functionality with a smaller installation size, making it ideal for use in lightweight, resource-constrained, or ephemeral environments.
It omits all CLI and server components found in the `prefect` library.

Install the latest version with:

<div class="terminal">
```bash
pip install -U prefect-client
```
</div>


## Next steps

Now that you have Prefect installed, run through the [quickstart](/getting-started/quickstart/) to try it out.
