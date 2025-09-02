"""
This module provides the AzureDevOpsCredentials block for authenticating
with Azure DevOps repositories using Personal Access Tokens (PATs).
"""

import base64
from typing import Optional

from prefect.blocks.abstract import CredentialsBlock
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretStr
else:
    from pydantic import Field, SecretStr


class AzureDevOpsCredentials(CredentialsBlock):
    """
    Block used to manage Azure DevOps authentication using Personal Access Tokens (PAT).
    
    Azure DevOps supports PAT authentication to private repositories using basic authentication
    with the PAT placed in the password field and any username (or empty string).
    
    For more information about Azure DevOps PATs, see:
    https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate
    
    Attributes:
        token: Personal Access Token (PAT) for Azure DevOps authentication.
        username: Optional username for Azure DevOps (defaults to empty string for PAT auth).
        
    Examples:
        Load stored Azure DevOps credentials:
        ```python
        from prefect_azure_devops import AzureDevOpsCredentials
        azure_devops_credentials_block = AzureDevOpsCredentials.load("BLOCK_NAME")
        ```
        
        Create new Azure DevOps credentials:
        ```python
        from prefect_azure_devops import AzureDevOpsCredentials
        
        azure_devops_credentials = AzureDevOpsCredentials(
            token="your-personal-access-token"
        )
        azure_devops_credentials.save("my-azure-devops-credentials")
        ```
        
        Use with prefect.yaml:
        ```yaml
        pull:
          - prefect.deployments.steps.git_clone:
              repository: "https://dev.azure.com/org/project/_git/repo.git"
              credentials: "{{ prefect.blocks.azure-devops-credentials.my-creds }}"
        ```
    """
    
    _block_type_name = "Azure DevOps Credentials"
    _logo_url = "https://cdn.jsdelivr.net/npm/simple-icons@v9/icons/azuredevops.svg"
    _documentation_url = "https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate"

    token: SecretStr = Field(
        description="Personal Access Token (PAT) for Azure DevOps authentication. "
                   "Generate this from your Azure DevOps User Settings > Personal access tokens."
    )
    username: str = Field(
        default="",
        description="Username for Azure DevOps. Can be empty string for PAT authentication. "
                   "When using PAT, this is typically left empty or set to any value."
    )

    def get_auth_header(self) -> dict:
        """
        Generate the Authorization header for Azure DevOps API requests.
        
        Returns:
            Dictionary containing the Authorization header for HTTP requests.
            
        Examples:
            Use with requests:
            ```python
            import requests
            from prefect_azure_devops import AzureDevOpsCredentials
            
            azure_creds = AzureDevOpsCredentials.load("my-creds")
            headers = azure_creds.get_auth_header()
            
            response = requests.get(
                "https://dev.azure.com/org/project/_apis/git/repositories",
                headers=headers
            )
            ```
        """
        # Azure DevOps uses Basic auth with username:PAT encoded in base64
        auth_string = f"{self.username}:{self.token.get_secret_value()}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        return {"Authorization": f"Basic {encoded_auth}"}

    def get_git_clone_url(self, repo_url: str) -> str:
        """
        Generate a git clone URL with embedded credentials for Azure DevOps.
        
        Args:
            repo_url: The Azure DevOps repository URL
            
        Returns:
            Repository URL with embedded PAT for authentication.
            
        Raises:
            ValueError: If the URL is not a valid Azure DevOps repository URL
                       or not using HTTPS protocol.
            
        Examples:
            Generate clone URL:
            ```python
            from prefect_azure_devops import AzureDevOpsCredentials
            
            azure_creds = AzureDevOpsCredentials.load("my-creds")
            clone_url = azure_creds.get_git_clone_url(
                "https://dev.azure.com/org/project/_git/repo"
            )
            # Result: https://PAT@dev.azure.com/org/project/_git/repo
            ```
        """
        if not (
            "dev.azure.com" in repo_url 
            or "visualstudio.com" in repo_url 
            or ".visualstudio.com" in repo_url
        ):
            raise ValueError(
                "URL does not appear to be an Azure DevOps repository URL. "
                "Expected URLs containing 'dev.azure.com' or 'visualstudio.com'."
            )
            
        if not repo_url.startswith("https://"):
            raise ValueError(
                "Only HTTPS URLs are supported for Azure DevOps PAT authentication. "
                "SSH URLs are not supported with PAT tokens."
            )
            
        # Insert PAT into the URL for authentication
        return repo_url.replace("https://", f"https://{self.token.get_secret_value()}@")

    def get_basic_auth_credentials(self) -> tuple:
        """
        Get basic authentication credentials for use with requests library.
        
        Returns:
            Tuple of (username, token) for use with requests.auth.HTTPBasicAuth
            
        Examples:
            Use with requests HTTPBasicAuth:
            ```python
            import requests
            from requests.auth import HTTPBasicAuth
            from prefect_azure_devops import AzureDevOpsCredentials
            
            azure_creds = AzureDevOpsCredentials.load("my-creds")
            username, password = azure_creds.get_basic_auth_credentials()
            
            response = requests.get(
                "https://dev.azure.com/org/project/_apis/git/repositories",
                auth=HTTPBasicAuth(username, password)
            )
            ```
        """
        return (self.username, self.token.get_secret_value())
