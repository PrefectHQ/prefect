"""
Tests for Azure DevOps credentials functionality.
"""

import base64
import pytest
from prefect_azure_devops import AzureDevOpsCredentials


class TestAzureDevOpsCredentials:
    """Test Azure DevOps credentials block functionality."""

    def test_credentials_creation(self):
        """Test creating Azure DevOps credentials."""
        creds = AzureDevOpsCredentials(token="test-token")
        assert creds.token.get_secret_value() == "test-token"
        assert creds.username == ""

    def test_credentials_creation_with_username(self):
        """Test creating Azure DevOps credentials with username."""
        creds = AzureDevOpsCredentials(token="test-token", username="testuser")
        assert creds.token.get_secret_value() == "test-token"
        assert creds.username == "testuser"

    def test_auth_header_generation(self):
        """Test generating authentication headers."""
        creds = AzureDevOpsCredentials(token="test-token", username="testuser")
        headers = creds.get_auth_header()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        
        # Decode and verify the auth string
        auth_value = headers["Authorization"].split(" ", 1)
        decoded_auth = base64.b64decode(auth_value).decode()
        assert decoded_auth == "testuser:test-token"

    def test_auth_header_generation_empty_username(self):
        """Test generating authentication headers with empty username."""
        creds = AzureDevOpsCredentials(token="test-token")
        headers = creds.get_auth_header()
        
        assert "Authorization" in headers
        auth_value = headers["Authorization"].split(" ", 1)
        decoded_auth = base64.b64decode(auth_value).decode()
        assert decoded_auth == ":test-token"

    def test_git_clone_url_generation_dev_azure_com(self):
        """Test generating git clone URLs for dev.azure.com."""
        creds = AzureDevOpsCredentials(token="test-token")
        
        original_url = "https://dev.azure.com/org/project/_git/repo.git"
        clone_url = creds.get_git_clone_url(original_url)
        
        expected_url = "https://test-token@dev.azure.com/org/project/_git/repo.git"
        assert clone_url == expected_url

    def test_git_clone_url_generation_visualstudio_com(self):
        """Test generating git clone URLs for visualstudio.com."""
        creds = AzureDevOpsCredentials(token="test-token")
        
        original_url = "https://myorg.visualstudio.com/project/_git/repo"
        clone_url = creds.get_git_clone_url(original_url)
        
        expected_url = "https://test-token@myorg.visualstudio.com/project/_git/repo"
        assert clone_url == expected_url

    def test_git_clone_url_invalid_domain(self):
        """Test error handling for invalid repository domains."""
        creds = AzureDevOpsCredentials(token="test-token")
        
        invalid_url = "https://github.com/user/repo.git"
        
        with pytest.raises(ValueError) as exc_info:
            creds.get_git_clone_url(invalid_url)
        
        assert "does not appear to be an Azure DevOps repository URL" in str(exc_info.value)

    def test_git_clone_url_non_https(self):
        """Test error handling for non-HTTPS URLs."""
        creds = AzureDevOpsCredentials(token="test-token")
        
        ssh_url = "git@ssh.dev.azure.com:v3/org/project/repo"
        
        with pytest.raises(ValueError) as exc_info:
            creds.get_git_clone_url(ssh_url)
        
        assert "Only HTTPS URLs are supported" in str(exc_info.value)

    def test_basic_auth_credentials(self):
        """Test getting basic auth credentials."""
        creds = AzureDevOpsCredentials(token="test-token", username="testuser")
        username, password = creds.get_basic_auth_credentials()
        
        assert username == "testuser"
        assert password == "test-token"

    def test_basic_auth_credentials_empty_username(self):
        """Test getting basic auth credentials with empty username."""
        creds = AzureDevOpsCredentials(token="test-token")
        username, password = creds.get_basic_auth_credentials()
        
        assert username == ""
        assert password == "test-token"

    def test_block_type_name(self):
        """Test that the block type name is correct."""
        assert AzureDevOpsCredentials._block_type_name == "Azure DevOps Credentials"

    def test_logo_url_set(self):
        """Test that logo URL is set."""
        assert AzureDevOpsCredentials._logo_url is not None
        assert "azuredevops" in AzureDevOpsCredentials._logo_url.lower()

    def test_documentation_url_set(self):
        """Test that documentation URL is set."""
        assert AzureDevOpsCredentials._documentation_url is not None
        assert "azure" in AzureDevOpsCredentials._documentation_url.lower()
