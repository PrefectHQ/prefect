import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from prefect.infrastructure.provisioners.container_instance import AzureCLI


class TestAzureCLIRunCommand:
    @pytest.fixture
    def run_process(self, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
        mock = AsyncMock(
            return_value=MagicMock(
                returncode=0, stdout=b"azure-cli 2.63.0\n", stderr=b""
            )
        )
        monkeypatch.setattr(
            "prefect.infrastructure.provisioners.container_instance.run_process", mock
        )
        return mock

    async def test_resolves_launcher_through_path(
        self, monkeypatch: pytest.MonkeyPatch, run_process: AsyncMock
    ):
        monkeypatch.setattr(
            "prefect.infrastructure.provisioners.container_instance.shutil.which",
            lambda name: (
                r"C:\Program Files\Azure CLI\wbin\az.CMD" if name == "az" else None
            ),
        )

        result = await AzureCLI(Console()).run_command("az --version")

        assert result == "azure-cli 2.63.0"
        run_process.assert_awaited_once_with(
            [r"C:\Program Files\Azure CLI\wbin\az.CMD", "--version"], check=False
        )

    async def test_unresolved_command_is_passed_through(
        self, monkeypatch: pytest.MonkeyPatch, run_process: AsyncMock
    ):
        monkeypatch.setattr(
            "prefect.infrastructure.provisioners.container_instance.shutil.which",
            lambda name: None,
        )

        await AzureCLI(Console()).run_command("az --version")

        run_process.assert_awaited_once_with(["az", "--version"], check=False)

    @pytest.mark.windows
    async def test_executes_windows_command_launcher_from_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        bin_dir = tmp_path / "Azure CLI" / "wbin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "az.cmd").write_text(
            "@echo off\necho azure-cli test launcher\n", encoding="utf-8"
        )
        monkeypatch.setenv("PATH", os.pathsep.join([str(bin_dir), os.environ["PATH"]]))

        result = await AzureCLI(Console()).run_command("az --version")

        assert result == "azure-cli test launcher"
