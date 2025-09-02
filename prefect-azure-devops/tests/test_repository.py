"""
Tests for Azure DevOps repository storage functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from prefect_azure_devops import AzureDevOpsCredentials
from prefect_azure_devops.repository import AzureDevOpsRepository


class TestAzureDevOpsRepository:
    """Test Azure DevOps repository storage block."""

    def test_repository_creation_without_credentials(self):
        """Test creating repository block without credentials."""
        repo = AzureDevOpsRepository(
            repository_url="https://dev.azure.com/org/project/_git/repo.git"
        )
        assert repo.repository_url == "https://dev.azure.com/org/project/_git/repo.git"
        assert repo.credentials is None
        assert repo.reference is None

    def test_repository_creation_with_credentials(self, sample_azure_devops_credentials):
        """Test creating repository block with credentials."""
        repo = AzureDevOpsRepository(
            repository_url="https://dev.azure.com/org/project/_git/repo.git",
            credentials=sample_azure_devops_credentials,
            reference="main"
        )
        assert repo.repository_url == "https://dev.azure.com/org/project/_git/repo.git"
        assert repo.credentials == sample_azure_devops_credentials
        assert repo.reference == "main"

    def test_invalid_repository_url(self):
        """Test validation of repository URLs."""
        with pytest.raises(ValueError) as exc_info:
            AzureDevOpsRepository(
                repository_url="https://github.com/user/repo.git"
            )
        
        assert "must be an Azure DevOps repository URL" in str(exc_info.value)

    def test_credentials_with_non_https_url(self, sample_azure_devops_credentials):
        """Test validation when using credentials with non-HTTPS URLs."""
        with pytest.raises(ValueError) as exc_info:
            AzureDevOpsRepository(
                repository_url="git@ssh.dev.azure.com:v3/org/project/repo",
                credentials=sample_azure_devops_credentials
            )
        
        assert "Credentials can only be used with" in str(exc_info.value)

    def test_create_repo_url_without_credentials(self):
        """Test creating repository URL without credentials."""
        repo = AzureDevOpsRepository(
            repository_url="https://dev.azure.com/org/project/_git/repo.git"
        )
        
        url = repo._create_repo_url()
        assert url == "https://dev.azure.com/org/project/_git/repo.git"

    def test_create_repo_url_with_credentials(self, sample_azure_devops_credentials):
        """Test creating repository URL with credentials."""
        repo = AzureDevOpsRepository(
            repository_url="https://dev.azure.com/org/project/_git/repo.git",
            credentials=sample_azure_devops_credentials
        )
        
        url = repo._create_repo_url()
        expected = "https://test-pat-token-12345@dev.azure.com/org/project/_git/repo.git"
        assert url == expected

    @pytest.mark.asyncio
    async def test_get_directory_success(self, sample_azure_devops_credentials, mock_git_process):
        """Test successful directory cloning."""
        repo = AzureDevOpsRepository(
            repository_url="https://dev.azure.com/org/project/_git/repo.git",
            credentials=sample_azure_devops_credentials
        )
        
        with patch("prefect_azure_devops.repository.run_process", return_value=mock_git_process), \
             patch("shutil.copytree") as mock_copytree, \
             patch("pathlib.Path.exists", return_value=True):
            
            await repo.get_directory()
            
            # Verify that copytree was called (indicating successful clone)
            mock_copytree.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_directory_git_failure(self, sample_azure_devops_credentials):
        """Test handling of git clone failures."""
        repo = AzureDevOpsRepository(
            repository_url="https://dev.azure.com/org/project/_git/repo.git",
            credentials=sample_azure_devops_credentials
        )
        
        # Mock a failed git process
        failed_process = Mock()
        failed_process.returncode = 1
        
        with patch("prefect_azure_devops.repository.run_process", return_value=failed_process), \
             patch("io.StringIO") as mock_stringio:
            
            # Mock the error stream
            error_stream = Mock()
            error_stream.read.return_value = "Authentication failed"
            mock_stringio.return_value = error_stream
            
            with pytest.raises(RuntimeError) as exc_info:
                await repo.get_directory()
            
            assert "Failed to clone Azure DevOps repository" in str(exc_info.value)

    def test_block_type_name(self):
        """Test that the block type name is correct."""
        assert AzureDevOpsRepository._block_type_name == "Azure DevOps Repository"

    def test_logo_url_set(self):
        """Test that logo URL is set."""
        assert AzureDevOpsRepository._logo_url is not None
        assert "azuredevops" in AzureDevOpsRepository._logo_url.lower()

    def test_documentation_url_set(self):
        """Test that documentation URL is set."""
        assert AzureDevOpsRepository._documentation_url is not None
        assert "azure" in AzureDevOpsRepository._documentation_url.lower()
