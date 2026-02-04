"""
End-to-end integration tests for include_files feature.

These tests verify the complete flow from @ecs(include_files=[...]) decorator
through bundle creation, upload, download, extraction, and flow execution.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestIncludeFilesIntegration:
    """End-to-end tests for include_files feature."""

    @pytest.fixture
    def project_dir(self, tmp_path: Path) -> Path:
        """Create a project directory with sample files."""
        # Create config file
        (tmp_path / "config.yaml").write_text("database: localhost\nport: 5432")

        # Create data directory with files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "input.csv").write_text("id,name\n1,Alice\n2,Bob")
        (data_dir / "lookup.json").write_text('{"key": "value"}')

        # Create nested structure
        templates_dir = tmp_path / "templates" / "emails"
        templates_dir.mkdir(parents=True)
        (templates_dir / "welcome.html").write_text("<h1>Welcome!</h1>")

        return tmp_path

    @pytest.fixture
    def mock_flow_file(self, project_dir: Path) -> Path:
        """Create a mock flow file in the project directory."""
        flow_file = project_dir / "flows" / "my_flow.py"
        flow_file.parent.mkdir(exist_ok=True)
        flow_file.write_text("# Flow definition here")
        return flow_file
