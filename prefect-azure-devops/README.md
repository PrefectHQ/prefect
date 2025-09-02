# prefect-azure-devops

<p align="center">
    <img src="https://user-images.githubusercontent.com/15331990/214789718-1bac8265-bc3a-4909-895e-d2c6c1bbfc56.svg"  height="350" style="max-height: 350px;">
    <br>
    <a href="https://pypi.python.org/pypi/prefect-azure-devops/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-azure-devops?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/PrefectHQ/prefect-azure-devops/" alt="Stars">
        <img src="https://img.shields.io/github/stars/PrefectHQ/prefect-azure-devops?color=0052FF&labelColor=090422" /></a>
    <a href="https://pypistats.org/packages/prefect-azure-devops/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-azure-devops?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/PrefectHQ/prefect-azure-devops/pulse" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/PrefectHQ/prefect-azure-devops?color=0052FF&labelColor=090422" /></a>
    <br>
    <a href="https://prefect-community.slack.com" alt="Slack">
        <img src="https://img.shields.io/badge/slack-join_community-red.svg?color=0052FF&labelColor=090422&logo=slack" /></a>
    <a href="https://discourse.prefect.io/" alt="Discourse">
        <img src="https://img.shields.io/badge/discourse-browse_forum-red.svg?color=0052FF&labelColor=090422&logo=discourse" /></a>
</p>

## Welcome!

Prefect integrations for working with Azure DevOps repositories and services.

## Getting Started

### Python setup

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2.0. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Installation

Install `prefect-azure-devops` with `pip`:

```bash
pip install prefect-azure-devops

A quick example of how to use prefect-azure-devops:

from prefect import flow
from prefect_azure_devops import AzureDevOpsCredentials

@flow
def example_azure_devops_flow():
    azure_devops_credentials = AzureDevOpsCredentials(
        token="your-personal-access-token"
    )
    azure_devops_credentials.save("my-azure-devops-block")

example_azure_devops_flow()


Resources
If you encounter any bugs while using prefect-azure-devops, feel free to open an issue in the prefect-azure-devops repository.

If you have any questions or issues while using prefect-azure-devops, you can find help in either the Prefect Discourse forum or the Prefect Slack community.

Development
If you'd like to install a version of prefect-azure-devops for development, clone the repository and perform an editable install with pip:

git clone https://github.com/PrefectHQ/prefect-azure-devops.git

cd prefect-azure-devops/

pip install -e ".[dev]"

# Install pre-commit to enable quality checks
pre-commit install

Contributing
If you'd like to help contribute to fix an issue or add a feature to prefect-azure-devops, please propose changes through a pull request from a fork of the repository.

Here are the steps:

1)Fork the repository

2) Clone the forked repository

3) Install the repository and its dependencies:

pip install -e ".[dev]"

4) Make desired changes

5)Add tests

6)Insert an entry to CHANGELOG.md

7) Install pre-commit to perform quality checks prior to commit: pre-commit install

8) git commit, git push, and create a pull request
