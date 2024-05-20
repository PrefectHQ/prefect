---
description: Install Prefect
tags:
    - install
    - pip install
    - development
    - Linux
    - Windows
    - upgrade
search:
  boost: 2
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

## Windows installation notes

You can install and run Prefect via Windows PowerShell, the Windows Command Prompt, or [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html). After installation, you may need to manually add the Python local packages `Scripts` folder to your `Path` environment variable.

The `Scripts` folder path looks something like (the username and Python version may be different on your system):

```bash
C:\Users\MyUserNameHere\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts
```

Review the `pip install` output messages for the `Scripts` folder path on your system.

## Minimal Prefect installation

The `prefect-client` library is a minimal installation of Prefect designed for interacting with Prefect Cloud or a remote self-hosted server instance.

`prefect-client` enables a subset of Prefect's functionality with a smaller installation size, making it ideal for use in lightweight, resource-constrained, or ephemeral environments.
It omits all CLI and server components found in the `prefect` library.

To install the latest release of `prefect-client`, run:

<div class="terminal">
```bash
pip install -U prefect-client
```
</div>

## Next steps

Now that you have Prefect installed, run through the [quickstart](/getting-started/quickstart/) to try it out.
