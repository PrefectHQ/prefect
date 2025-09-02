"""
This collection provides credential blocks for authenticating with Azure DevOps
repositories using Personal Access Tokens (PAT), following the same patterns
as existing Prefect integrations (GitHub, GitLab, BitBucket).
"""

from .credentials import AzureDevOpsCredentials
from .repository import AzureDevOpsRepository

__version__ = "0.1.0"
__all__ = ["AzureDevOpsCredentials", "AzureDevOpsRepository"]
