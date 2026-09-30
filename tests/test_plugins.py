from importlib.metadata import EntryPoints
from unittest.mock import Mock, patch

import pytest

import prefect._internal.plugins.collections as collections_module
from prefect.plugins import load_prefect_collections, safe_load_entrypoints
from prefect.settings import PREFECT_DEBUG_MODE, temporary_settings


@pytest.fixture(autouse=True)
def reset_collections():
    collections_module._collections = None
    yield
    collections_module._collections = None


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


@patch("prefect._internal.plugins.collections.entry_points")
@patch("prefect._internal.plugins.collections.safe_load_entrypoints")
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


@patch("prefect._internal.plugins.collections.entry_points")
@patch("prefect._internal.plugins.collections.safe_load_entrypoints")
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


@patch("prefect._internal.plugins.collections.entry_points")
@patch("prefect._internal.plugins.collections.safe_load_entrypoints")
def test_load_prefect_collections_caches_result(mock_safe_load, mock_entry_points):
    mock_entry_points.return_value = "mock_entrypoints"

    mock_safe_load.return_value = {"collection1": "module1"}

    result1 = load_prefect_collections()
    result2 = load_prefect_collections()

    assert result1 == result2
    mock_entry_points.assert_called_once()
    mock_safe_load.assert_called_once()


@patch("prefect._internal.plugins.collections.entry_points")
@patch("prefect._internal.plugins.collections.safe_load_entrypoints")
def test_load_prefect_collections_reload_picks_up_new_entrypoints(
    mock_safe_load, mock_entry_points
):
    first = Mock()
    first.name = "collection1"
    second = Mock()
    second.name = "collection2"
    mock_entry_points.side_effect = [
        EntryPoints([first]),
        EntryPoints([first, second]),
    ]
    mock_safe_load.side_effect = [
        {"collection1": "module1"},
        {"collection2": "module2"},
    ]

    load_prefect_collections()
    result = load_prefect_collections(reload=True)

    assert result == {"collection1": "module1", "collection2": "module2"}
    assert [ep.name for ep in mock_safe_load.call_args_list[1].args[0]] == [
        "collection2"
    ]


@patch("prefect._internal.plugins.collections.entry_points")
@patch("prefect._internal.plugins.collections.safe_load_entrypoints")
def test_load_prefect_collections_reload_retries_failed_entrypoints(
    mock_safe_load, mock_entry_points
):
    loaded = Mock()
    loaded.name = "collection1"
    broken = Mock()
    broken.name = "collection2"
    mock_entry_points.return_value = EntryPoints([loaded, broken])
    mock_safe_load.side_effect = [
        {"collection1": "module1", "collection2": ImportError("missing")},
        {"collection2": "module2"},
    ]

    load_prefect_collections()
    result = load_prefect_collections(reload=True)

    assert result == {"collection1": "module1", "collection2": "module2"}
    assert [ep.name for ep in mock_safe_load.call_args_list[1].args[0]] == [
        "collection2"
    ]


async def test_install_package_reloads_collections_after_install():
    from prefect.cli import _worker_utils

    calls = []
    with (
        patch(
            "prefect._internal.installation.ainstall_packages",
            side_effect=lambda *args, **kwargs: calls.append("install"),
        ),
        patch.object(
            _worker_utils,
            "load_prefect_collections",
            side_effect=lambda **kwargs: calls.append(("load", kwargs)),
        ),
    ):
        await _worker_utils._install_package(Mock(), "prefect-kubernetes")

    assert calls == ["install", ("load", {"reload": True})]
