from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from prefect.testing.cli import invoke_and_assert


class TestProjectInit:
    def test_project_init(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "project init --name test_project", temp_dir=str(tempdir)
            )
            assert result.exit_code == 0
            for file in ["prefect.yaml", "deployment.yaml", ".prefectignore"]:
                # temp_dir creates a *new* nested temporary directory within tempdir
                assert any(Path(tempdir).rglob(file))
