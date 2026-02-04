"""Tests for SerializedBundle TypedDict with files_key field."""

from unittest.mock import MagicMock


class TestSerializedBundleFilesKey:
    """Tests for SerializedBundle files_key field."""

    def test_serialized_bundle_accepts_files_key_none(self):
        """SerializedBundle should accept files_key=None for bundles without files."""
        from prefect._experimental.bundles import SerializedBundle

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
        from prefect._experimental.bundles import SerializedBundle

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
        from prefect._experimental.bundles import SerializedBundle

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
        from prefect._experimental.bundles import SerializedBundle

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
        import prefect._experimental.bundles as bundles_module
        from prefect._experimental.bundles import create_bundle_for_flow_run
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
        import prefect._experimental.bundles as bundles_module
        from prefect._experimental.bundles import create_bundle_for_flow_run
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
