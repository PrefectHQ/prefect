"""
Shared test configuration and fixtures for prefect-azure-devops tests.
"""

import pytest
from unittest.mock import Mock

@pytest.fixture
def sample_azure_devops_credentials():
    """Fixture providing sample Azure DevOps credentials for testing."""
    from prefect_azure_devops import AzureDevOpsCredentials
    
    return AzureDevOpsCredentials(
        token="test-pat-token-12345",
        username="testuser"
    )

@pytest.fixture
def sample_repo_url():
    """Fixture providing a sample Azure DevOps repository URL."""
    return "https://dev.azure.com/testorg/testproject/_git/testrepo.git"

@pytest.fixture
def mock_git_process():
    """Fixture providing a mock git process for testing git operations."""
    mock = Mock()
    mock.returncode = 0
    return mock
