"""Tests for SerializedBundle TypedDict with files_key field."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest

import prefect.bundles as bundles_module
from prefect.bundles import create_bundle_for_flow_run
from prefect.bundles._path_resolver import PathValidationError
from prefect.flows import flow


class TestSerializedBundleFilesKey:
    """Tests for SerializedBundle files_key field."""

    def test_serialized_bundle_accepts_files_key_none(self):
        """SerializedBundle should accept files_key=None for bundles without files."""
        from prefect.bundles import SerializedBundle

        bundle: SerializedBundle = {
            "function": "serialized_function_data",
            "context": "serialized_context_data",
            "flow_run": {"id": "test-flow-run-id"},
            "dependencies": "prefect>=3.0.0",
            "files_key": None,
        }

        assert bundle["files_key"] is None
        assert bundle["function"] == "serialized_function_data"

    def test_serialized_bundle_accepts_files_key_string(self):
        """SerializedBundle should accept files_key with a storage key path."""
        from prefect.bundles import SerializedBundle

        bundle: SerializedBundle = {
            "function": "serialized_function_data",
            "context": "serialized_context_data",
            "flow_run": {"id": "test-flow-run-id"},
            "dependencies": "prefect>=3.0.0",
            "files_key": "files/a1b2c3d4e5f6.zip",
        }

        assert bundle["files_key"] == "files/a1b2c3d4e5f6.zip"

    def test_serialized_bundle_without_files_key_is_valid(self):
        """Existing bundles without files_key field should remain valid (backward compat)."""
        from prefect.bundles import SerializedBundle

        # This should be valid - no files_key field at all
        bundle: SerializedBundle = {
            "function": "serialized_function_data",
            "context": "serialized_context_data",
            "flow_run": {"id": "test-flow-run-id"},
            "dependencies": "prefect>=3.0.0",
        }

        assert bundle["function"] == "serialized_function_data"
        # files_key is not present
        assert "files_key" not in bundle

    def test_serialized_bundle_files_key_full_storage_path(self):
        """files_key should store full storage key path like 'files/abc123.zip'."""
        from prefect.bundles import SerializedBundle

        # Full SHA256-based storage key
        full_key = (
            "files/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2.zip"
        )
        bundle: SerializedBundle = {
            "function": "serialized_function_data",
            "context": "serialized_context_data",
            "flow_run": {"id": "test-flow-run-id"},
            "dependencies": "prefect>=3.0.0",
            "files_key": full_key,
        }

        assert bundle["files_key"] == full_key
        assert bundle["files_key"].startswith("files/")
        assert bundle["files_key"].endswith(".zip")


class TestCreateBundleForFlowRunFilesKey:
    """Tests for create_bundle_for_flow_run with files_key field."""

    def test_create_bundle_returns_bundle_with_files_key(self, monkeypatch):
        """create_bundle_for_flow_run should return BundleCreationResult with bundle containing files_key."""
        import prefect.bundles as bundles_module
        from prefect.bundles import create_bundle_for_flow_run
        from prefect.flows import flow

        # Mock subprocess to avoid actual uv pip freeze
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def my_flow():
            return "hello"

        # Create a mock flow run
        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)

        # Result should have bundle and zip_path keys
        assert "bundle" in result
        assert "zip_path" in result

        # Bundle should have files_key field
        assert "files_key" in result["bundle"]
        # Default should be None (no files included yet)
        assert result["bundle"]["files_key"] is None
        assert result["zip_path"] is None

    def test_create_bundle_files_key_defaults_to_none(self, monkeypatch):
        """create_bundle_for_flow_run should default files_key to None."""
        import prefect.bundles as bundles_module
        from prefect.bundles import create_bundle_for_flow_run
        from prefect.flows import flow

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"",
        )

        @flow
        def simple_flow():
            pass

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "run-123"}

        result = create_bundle_for_flow_run(simple_flow, mock_flow_run)

        assert result["bundle"].get("files_key") is None
        assert result["zip_path"] is None


class TestCreateBundleForFlowRunLauncher:
    """Tests for create_bundle_for_flow_run launcher-aware behavior."""

    def test_create_bundle_skips_uv_freeze_when_execution_launcher_set(
        self, monkeypatch
    ):
        """When the flow has an execution launcher override, `uv pip freeze` should not be called."""

        def fake_check_output(*args, **kwargs):
            raise AssertionError(
                "uv pip freeze should not be called when an execution launcher is set"
            )

        monkeypatch.setattr(
            bundles_module.subprocess, "check_output", fake_check_output
        )

        @flow
        def my_flow():
            return "hello"

        my_flow.launcher = {"upload": ["python"], "execution": ["python"]}

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)

        assert result["bundle"]["dependencies"] == ""

    def test_create_bundle_survives_missing_uv_when_execution_launcher_set(
        self, monkeypatch
    ):
        """Bundle creation should succeed when `uv` is unavailable if an execution launcher is set."""

        def raising_check_output(*args, **kwargs):
            raise PermissionError(13, "Permission denied", "uv")

        monkeypatch.setattr(
            bundles_module.subprocess, "check_output", raising_check_output
        )

        @flow
        def my_flow():
            return "hello"

        my_flow.launcher = ["python"]

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)

        assert result["bundle"]["dependencies"] == ""

    def test_create_bundle_runs_uv_freeze_for_upload_only_launcher(self, monkeypatch):
        """Upload-only launcher overrides still run `uv run` at execution, so freeze must still run."""
        calls: list[list[str]] = []

        def fake_check_output(cmd, *args, **kwargs):
            calls.append(list(cmd) if isinstance(cmd, (list, tuple)) else [cmd])
            return b"prefect>=3.0.0\n"

        monkeypatch.setattr(
            bundles_module.subprocess, "check_output", fake_check_output
        )

        @flow
        def my_flow():
            return "hello"

        my_flow.launcher = {"upload": ["python"]}

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)

        assert len(calls) == 1
        assert "freeze" in calls[0]
        assert result["bundle"]["dependencies"] == "prefect>=3.0.0"

    def test_create_bundle_runs_uv_freeze_without_launcher(self, monkeypatch):
        """Without a launcher, the current `uv pip freeze` behavior is preserved."""
        calls: list[list[str]] = []

        def fake_check_output(cmd, *args, **kwargs):
            calls.append(list(cmd) if isinstance(cmd, (list, tuple)) else [cmd])
            return b"prefect>=3.0.0\n"

        monkeypatch.setattr(
            bundles_module.subprocess, "check_output", fake_check_output
        )

        @flow
        def my_flow():
            return "hello"

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)

        assert len(calls) == 1
        assert "freeze" in calls[0]
        assert result["bundle"]["dependencies"] == "prefect>=3.0.0"


class TestCreateBundleForFlowRunIncludeFiles:
    """Tests for include_files integration in create_bundle_for_flow_run."""

    @pytest.fixture
    def project_with_files(self, tmp_path: Path) -> Path:
        """Create a project directory with files and a flow."""
        # Create files to include
        (tmp_path / "config.yaml").write_text("key: value")
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "input.csv").write_text("a,b\n1,2")

        # Create flow file
        flow_file = tmp_path / "my_flow.py"
        flow_file.write_text(
            """
from prefect import flow

@flow
def my_flow():
    pass
"""
        )
        return tmp_path

    def test_files_key_populated_when_include_files_set(
        self, project_with_files: Path, monkeypatch
    ) -> None:
        """files_key is populated when flow has include_files."""
        import prefect.bundles as bundles_module
        from prefect.bundles import create_bundle_for_flow_run
        from prefect.flows import Flow

        # Mock subprocess to avoid actual uv pip freeze
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        # Create a flow with include_files
        @Flow
        def test_flow():
            pass

        # Set include_files attribute (as @ecs decorator would)
        test_flow.include_files = ["config.yaml", "data/"]

        # Mock inspect.getfile to return our flow file path
        flow_file = project_with_files / "my_flow.py"

        with patch("prefect.bundles.inspect.getfile", return_value=str(flow_file)):
            flow_run = MagicMock()
            flow_run.model_dump.return_value = {"id": "test-123"}

            result = create_bundle_for_flow_run(
                flow=test_flow,
                flow_run=flow_run,
            )

        # Verify files_key is populated
        assert result["bundle"]["files_key"] is not None
        assert result["bundle"]["files_key"].startswith("files/")
        assert result["bundle"]["files_key"].endswith(".zip")

        # Verify zip_path is returned
        assert result["zip_path"] is not None
        assert result["zip_path"].exists()

        # Cleanup
        if result["zip_path"]:
            result["zip_path"].unlink(missing_ok=True)
            result["zip_path"].parent.rmdir()

    def test_include_files_base_dir_sets_the_collection_and_archive_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / ".prefectignore").write_text("assets/ignored.txt\n")
        custom_base_dir = tmp_path / "assets"
        custom_base_dir.mkdir()
        (custom_base_dir / "config.yaml").write_text("source: custom")
        (custom_base_dir / "ignored.txt").write_text("ignored")
        nested_dir = custom_base_dir / "data"
        nested_dir.mkdir()
        (nested_dir / "input.csv").write_text("a,b\n1,2")

        flow_dir = tmp_path / "flows"
        flow_dir.mkdir()
        flow_file = flow_dir / "my_flow.py"
        flow_file.write_text("from prefect import flow")
        (flow_dir / "config.yaml").write_text("source: flow")

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def test_flow():
            pass

        test_flow.include_files = [  # type: ignore[attr-defined]
            "config.yaml",
            "ignored.txt",
            "data/input.csv",
        ]
        test_flow.include_files_base_dir = custom_base_dir  # type: ignore[attr-defined]

        with patch("prefect.bundles.inspect.getfile", return_value=str(flow_file)):
            flow_run = MagicMock()
            flow_run.model_dump.return_value = {"id": "test-123"}
            result = create_bundle_for_flow_run(test_flow, flow_run)

        zip_path = result["zip_path"]
        assert zip_path is not None

        try:
            with ZipFile(zip_path) as archive:
                assert set(archive.namelist()) == {"config.yaml", "data/input.csv"}
                assert archive.read("config.yaml") == b"source: custom"
        finally:
            zip_path.unlink(missing_ok=True)
            zip_path.parent.rmdir()

    def test_relative_include_files_base_dir_resolves_from_bundle_creation_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "config.yaml").write_text("source: cwd")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def test_flow():
            pass

        test_flow.include_files = ["config.yaml"]  # type: ignore[attr-defined]
        test_flow.include_files_base_dir = Path("assets")  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}
        result = create_bundle_for_flow_run(test_flow, flow_run)

        zip_path = result["zip_path"]
        assert zip_path is not None

        try:
            with ZipFile(zip_path) as archive:
                assert archive.read("config.yaml") == b"source: cwd"
        finally:
            zip_path.unlink(missing_ok=True)
            zip_path.parent.rmdir()

    def test_include_files_base_dir_expands_user_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "config.yaml").write_text("source: home")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def test_flow():
            pass

        test_flow.include_files = ["config.yaml"]  # type: ignore[attr-defined]
        test_flow.include_files_base_dir = Path("~/assets")  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}
        result = create_bundle_for_flow_run(test_flow, flow_run)

        zip_path = result["zip_path"]
        assert zip_path is not None

        try:
            with ZipFile(zip_path) as archive:
                assert archive.read("config.yaml") == b"source: home"
        finally:
            zip_path.unlink(missing_ok=True)
            zip_path.parent.rmdir()

    @pytest.mark.parametrize("base_dir_kind", ["missing", "file"])
    def test_invalid_include_files_base_dir_fails_bundle_creation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        base_dir_kind: str,
    ) -> None:
        base_dir = tmp_path / base_dir_kind
        if base_dir_kind == "file":
            base_dir.write_text("not a directory")

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def test_flow():
            pass

        test_flow.include_files = ["config.yaml"]  # type: ignore[attr-defined]
        test_flow.include_files_base_dir = base_dir  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}

        with pytest.raises(ValueError, match="include_files_base_dir"):
            create_bundle_for_flow_run(test_flow, flow_run)

    def test_unknown_user_in_include_files_base_dir_fails_bundle_creation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )
        original_expanduser = Path.expanduser

        def expanduser(path: Path) -> Path:
            if str(path) == "~unknown-user/assets":
                raise RuntimeError("Could not determine home directory")
            return original_expanduser(path)

        monkeypatch.setattr(Path, "expanduser", expanduser)

        @flow
        def test_flow():
            pass

        test_flow.include_files = ["config.yaml"]  # type: ignore[attr-defined]
        test_flow.include_files_base_dir = Path("~unknown-user/assets")  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}

        with pytest.raises(ValueError, match="include_files_base_dir"):
            create_bundle_for_flow_run(test_flow, flow_run)

    def test_unreadable_include_files_base_dir_fails_bundle_creation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base_dir = tmp_path / "assets"
        base_dir.mkdir()
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )
        original_scandir = bundles_module.os.scandir

        def scandir(path: Path):
            if Path(path) == base_dir:
                raise PermissionError("permission denied")
            return original_scandir(path)

        monkeypatch.setattr(bundles_module.os, "scandir", scandir)

        @flow
        def test_flow():
            pass

        test_flow.include_files = ["config.yaml"]  # type: ignore[attr-defined]
        test_flow.include_files_base_dir = base_dir  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}

        with pytest.raises(PermissionError, match="permission denied"):
            create_bundle_for_flow_run(test_flow, flow_run)

    def test_include_files_cannot_escape_custom_base_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base_dir = tmp_path / "assets"
        base_dir.mkdir()
        (tmp_path / "secret.txt").write_text("secret")
        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def test_flow():
            pass

        test_flow.include_files = ["../secret.txt"]  # type: ignore[attr-defined]
        test_flow.include_files_base_dir = base_dir  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}

        with pytest.raises(PathValidationError, match="traversal"):
            create_bundle_for_flow_run(test_flow, flow_run)

    def test_files_key_none_when_no_include_files(self, monkeypatch) -> None:
        """files_key is None when flow has no include_files."""
        import prefect.bundles as bundles_module
        from prefect.bundles import create_bundle_for_flow_run
        from prefect.flows import Flow

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"",
        )

        @Flow
        def test_flow():
            pass

        # No include_files attribute
        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}

        result = create_bundle_for_flow_run(
            flow=test_flow,
            flow_run=flow_run,
        )

        assert result["bundle"]["files_key"] is None
        assert result["zip_path"] is None

    def test_files_key_none_when_include_files_empty(self, monkeypatch) -> None:
        """files_key is None when include_files is empty list."""
        import prefect.bundles as bundles_module
        from prefect.bundles import create_bundle_for_flow_run
        from prefect.flows import Flow

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"",
        )

        @Flow
        def test_flow():
            pass

        test_flow.include_files = []
        test_flow.include_files_base_dir = Path("does-not-exist")  # type: ignore[attr-defined]

        flow_run = MagicMock()
        flow_run.model_dump.return_value = {"id": "test-123"}

        result = create_bundle_for_flow_run(
            flow=test_flow,
            flow_run=flow_run,
        )

        assert result["bundle"]["files_key"] is None
        assert result["zip_path"] is None
