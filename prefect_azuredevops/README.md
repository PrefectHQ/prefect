# Prefect Azure DevOps integration (local dev package)

This local package provides an `AzureDevOpsCredentials` Prefect block and a small
`AzureDevOpsRepository` helper to securely clone Azure DevOps Git repositories
(using PAT authentication) and to be registered as a Prefect Block.

## Files added
- `prefect_azuredevops/credentials.py` — CredentialsBlock storing PAT + helpers
- `prefect_azuredevops/repository.py` — small repository clone helper using GIT_ASKPASS
- `tests/` — pytest unit tests
- `setup.py`, `requirements.txt`

## Quick dev install
From the root of your repo (the folder containing `prefect/` and this new `prefect_azuredevops/` folder):

```bash
# ensure your venv is activated
pip install -e ./prefect_azuredevops
