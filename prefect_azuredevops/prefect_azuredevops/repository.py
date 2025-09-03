"""
Lightweight repository helper for Azure DevOps that uses AzureDevOpsCredentials
to perform a git clone without leaking the PAT.

This file intentionally avoids heavy extra dependencies and uses subprocess to run git.
"""

from __future__ import annotations
import os
import subprocess
from typing import Optional

from pydantic import Field
from prefect.blocks.core import Block

from .credentials import AzureDevOpsCredentials


class AzureDevOpsRepository(Block):
    """
    A small helper block to represent an Azure DevOps repository and clone it.

    Fields:
        organization (str) - Azure DevOps org name
        project (Optional[str]) - Azure DevOps project (optional)
        repository (str) - repository name
        base_url (str) - base URL, defaults to https://dev.azure.com
        credentials (AzureDevOpsCredentials) - credentials block instance
    """

    _block_type_name = "Azure DevOps Repository"

    organization: str = Field(..., description="Azure DevOps organization")
    project: Optional[str] = Field(default=None, description="Project (optional)")
    repository: str = Field(..., description="Repository name")
    base_url: str = Field(default="https://dev.azure.com", description="Base URL")
    credentials: AzureDevOpsCredentials = Field(..., description="Credentials block")
    depth: Optional[int] = Field(default=None, description="Shallow clone depth")

    def https_url(self) -> str:
        if self.project:
            return f"{self.base_url}/{self.organization}/{self.project}/_git/{self.repository}"
        else:
            return f"{self.base_url}/{self.organization}/_git/{self.repository}"

    def clone(self, dest: str = ".", checkout_branch: Optional[str] = None) -> str:
        """
        Clone the repo into dest/<repository>. Uses GIT_ASKPASS to avoid secrets in the command line.

        Returns the absolute path to the cloned repo.
        """
        repo_url = self.https_url()
        target_dir = os.path.join(dest, self.repository)
        os.makedirs(dest, exist_ok=True)

        with self.credentials.git_askpass_env() as env:
            cmd = ["git", "clone", repo_url, target_dir]
            if self.depth:
                cmd += ["--depth", str(self.depth)]
            subprocess.run(cmd, check=True, env={**os.environ, **env})

            if checkout_branch:
                subprocess.run(
                    ["git", "-C", target_dir, "checkout", checkout_branch],
                    check=True,
                    env={**os.environ, **env},
                )

        return os.path.abspath(target_dir)
