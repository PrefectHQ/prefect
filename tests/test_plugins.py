from unittest.mock import Mock, patch

import pytest

import prefect.plugins
from prefect.plugins import load_prefect_collections, safe_load_entrypoints
from prefect.settings import PREFECT_DEBUG_MODE, temporary_settings
from prefect.utilities.compat import EntryPoints


@pytest.fixture(autouse=True)
def reset_collections():
    prefect.plugins.COLLECTIONS = None
    yield
    prefect.plugins.COLLECTIONS = None


def test_safe_load_entrypoints_returns_modules_and_exceptions():
    mock_entrypoint1 = Mock()
    mock_entrypoint1.name = "test1"
    mock_entrypoint1.load.return_value = "module1"

    mock_entrypoint2 = Mock()
    mock_entrypoint2.name = "test2"
    mock_entrypoint2.load.side_effect = ImportError("Module not found")

    mock_entrypoints = EntryPoints([mock_entrypoint1, mock_entrypoint2])

    result = safe_load_entrypoints(mock_entrypoints)

    assert "test1" in result
    assert result["test1"] == "module1"
    assert "test2" in result
    assert isinstance(result["test2"], ImportError)


@patch("prefect.plugins.entry_points")
@patch("prefect.plugins.safe_load_entrypoints")
def test_load_prefect_collections_returns_modules_and_exceptions(
    mock_safe_load, mock_entry_points
):
    mock_entry_points.return_value = "mock_entrypoints"

    mock_safe_load.return_value = {
        "collection1": "module1",
        "collection2": ImportError("Failed to load"),
    }

    result = load_prefect_collections()

    mock_entry_points.assert_called_once_with(group="prefect.collections")
    mock_safe_load.assert_called_once_with("mock_entrypoints")

    # Convert ImportError to string for comparison
    expected = {
        "collection1": "module1",
        "collection2": str(ImportError("Failed to load")),
    }
    assert {
        k: str(v) if isinstance(v, ImportError) else v for k, v in result.items()
    } == expected


@patch("prefect.plugins.entry_points")
@patch("prefect.plugins.safe_load_entrypoints")
@pytest.mark.parametrize("debug_mode", [True, False])
def test_load_prefect_collections_debug_mode_behavior(
    mock_safe_load, mock_entry_points, capsys, debug_mode
):
    mock_entry_points.return_value = "mock_entrypoints"

    mock_safe_load.return_value = {
        "collection1": "module1",
        "collection2": ImportError("Failed to load"),
    }

    with temporary_settings({PREFECT_DEBUG_MODE: debug_mode}):
        load_prefect_collections()

    assert mock_entry_points.call_count == 1
    captured = capsys.readouterr()

    if debug_mode:
        assert "Loaded collection 'collection1'." in captured.out
        assert "Warning!  Failed to load collection 'collection2'" in captured.out
    else:
        assert "Loaded collection 'collection1'." not in captured.out
        assert "Warning!  Failed to load collection 'collection2'" in captured.out


@patch("prefect.plugins.entry_points")
@patch("prefect.plugins.safe_load_entrypoints")
def test_load_prefect_collections_caches_result(mock_safe_load, mock_entry_points):
    mock_entry_points.return_value = "mock_entrypoints"

    mock_safe_load.return_value = {"collection1": "module1"}

    result1 = load_prefect_collections()
    result2 = load_prefect_collections()

    assert result1 == result2
    mock_entry_points.assert_called_once()
    mock_safe_load.assert_called_once()
