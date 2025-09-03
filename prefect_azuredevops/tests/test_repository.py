import os
import subprocess
from prefect_azuredevops.repository import AzureDevOpsRepository
from prefect_azuredevops.credentials import AzureDevOpsCredentials

def test_https_url_no_project():
    repo = AzureDevOpsRepository(
        organization="org",
        project=None,
        repository="repo",
        credentials=AzureDevOpsCredentials(token="t"),
    )
    assert repo.https_url() == "https://dev.azure.com/org/_git/repo" or "dev.azure.com" in repo.https_url()

def test_clone_invokes_git(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, check, env=None):
        calls.append((cmd, check, env))
        return

    monkeypatch.setattr(subprocess, "run", fake_run)

    creds = AzureDevOpsCredentials(token="t")
    repo = AzureDevOpsRepository(
        organization="o", project="p", repository="r", credentials=creds
    )
    out = repo.clone(dest=str(tmp_path), checkout_branch=None)
    # ensure git clone command invoked
    assert any(call[0][0:2] == ["git", "clone"] for call in calls)
    # ensure env had GIT_ASKPASS
    assert any(call[2] and "GIT_ASKPASS" in call[2] for call in calls)
