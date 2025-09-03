from __future__ import annotations
import base64
import os
import tempfile
import textwrap
from contextlib import contextmanager
from typing import Dict, Optional

from pydantic import Field, SecretStr
from prefect.blocks.abstract import CredentialsBlock


class AzureDevOpsCredentials(CredentialsBlock):
    """
    Block for storing an Azure DevOps Personal Access Token (PAT).

    Fields
    ------
    token: SecretStr - the PAT
    username: str - username to pair with PAT in basic auth (commonly 'pat' or '')
    base_url: str - base host (defaults to dev.azure.com)
    """

    _block_type_name = "Azure DevOps Credentials"
    _logo_url = "https://learn.microsoft.com/favicon.ico"
    _documentation_url = "https://learn.microsoft.com/en-us/azure/devops/"

    token: Optional[SecretStr] = Field(
        default=None, description="Azure DevOps Personal Access Token (PAT)."
    )
    username: str = Field(
        default="pat",
        description="Username to pair with the PAT for Basic auth. Azure accepts any non-empty string.",
    )
    base_url: str = Field(
        default="https://dev.azure.com",
        description="Azure DevOps base URL (override for on-prem ADO Server).",
    )

    def _encode_basic(self) -> str:
        if not self.token:
            raise ValueError("AzureDevOpsCredentials: token is not set.")
        raw = f"{self.username}:{self.token.get_secret_value()}".encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")

    def get_auth_header(self) -> Dict[str, str]:
        """
        Returns Authorization header dict for REST API calls:
        {"Authorization": "Basic <base64(username:PAT)>"}
        """
        return {"Authorization": f"Basic {self._encode_basic()}"}

    def get_http_extra_header(self) -> str:
        """
        Returns the header string usable with git's http.extraHeader:
        'Authorization: Basic <...>'
        """
        return f"Authorization: Basic {self._encode_basic()}"

    @contextmanager
    def git_askpass_env(self) -> Dict[str, str]:
        """
        Context manager that writes a temporary GIT_ASKPASS script and yields
        environment variables that instruct git to use it for credentials.

        Example:
            with creds.git_askpass_env() as env:
                subprocess.run([...], env={**os.environ, **env})

        The script answers git's username/password prompts:
        - if asked for username -> echoes configured username
        - if asked for password -> echoes the PAT
        """
        if not self.token:
            raise ValueError("AzureDevOpsCredentials: token is not set.")

        script = textwrap.dedent(
            f"""\ 
            #!/usr/bin/env bash
            case "$1" in
                *sername*) echo "{self.username}" ;;
                *assword*) echo "{self.token.get_secret_value()}" ;;
            esac
            """
        )

        fd, path = tempfile.mkstemp(prefix="prefect_ado_askpass_", text=True)
        try:
            os.write(fd, script.encode("utf-8"))
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
        os.chmod(path, 0o700)

        env = {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": path,
        }
        try:
            yield env
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def get_client(self):
        """
        Return a simple requests.Session configured with the Authorization header.

        Satisfies the abstract CredentialsBlock.get_client requirement and
        is suitable for Azure DevOps REST calls.
        """
        try:
            import requests
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'requests' package is required to use AzureDevOpsCredentials.get_client(). "
                "Install it with `pip install requests`."
            ) from exc

        session = requests.Session()
        session.headers.update(self.get_auth_header())
        return session
