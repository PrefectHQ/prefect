"""Test for YAML linting standards in prefect.yaml generation."""
import pytest
import yaml
from pathlib import Path
from prefect.deployments.base import create_default_prefect_yaml


class TestPrefectYamlLinting:
    """Tests that generated prefect.yaml files conform to common linting standards."""

    async def test_prefect_yaml_has_document_start(self, tmp_path):
        """Test that generated prefect.yaml includes document start marker ---"""
        create_default_prefect_yaml(tmp_path, name="test-project")
        
        prefect_file = tmp_path / "prefect.yaml"
        content = prefect_file.read_text()
        
        assert "---" in content, "YAML document should have --- document start marker"

    async def test_prefect_yaml_line_length(self, tmp_path):
        """Test that no lines in generated prefect.yaml exceed 80 characters"""
        create_default_prefect_yaml(tmp_path, name="test-project")
        
        prefect_file = tmp_path / "prefect.yaml"
        lines = prefect_file.read_text().split("\n")
        
        for i, line in enumerate(lines, 1):
            assert len(line) <= 80, f"Line {i} exceeds 80 chars: {line[:50]}..."

    async def test_prefect_yaml_valid_yaml(self, tmp_path):
        """Test that generated prefect.yaml is valid YAML"""
        create_default_prefect_yaml(tmp_path, name="test-project")
        
        prefect_file = tmp_path / "prefect.yaml"
        content = prefect_file.read_text()
        
        # Should parse without errors
        parsed = yaml.safe_load(content)
        assert parsed is not None, "YAML should parse successfully"
        assert "name" in parsed, "YAML should have 'name' key"
        assert "prefect-version" in parsed, "YAML should have 'prefect-version' key"

    async def test_prefect_yaml_list_indentation(self, tmp_path):
        """Test that lists in generated prefect.yaml have proper indentation"""
        # Use a recipe that includes lists (like git)
        from prefect.deployments.base import configure_project_by_recipe
        
        config = configure_project_by_recipe("git", repository="test/repo", branch="main")
        create_default_prefect_yaml(tmp_path, name="test-project", contents=config)
        
        prefect_file = tmp_path / "prefect.yaml"
        content = prefect_file.read_text()
        lines = content.split("\n")
        
        # Check list items are indented properly
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("- ") and not line.startswith("#"):
                # List items should have 2-space indentation
                assert line.startswith("  -"), f"Line {i} should have 2-space indent: {line}"
