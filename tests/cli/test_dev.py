from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import watchfiles

import prefect
import prefect.cli.dev
from prefect.testing.cli import invoke_and_assert


def _setup_ui_build_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    development_base_path = tmp_path / "repo"
    development_base_path.mkdir()
    (development_base_path / "pyproject.toml").write_text("", encoding="utf-8")

    for ui_dir in ("ui", "ui-v2"):
        dist_dir = development_base_path / ui_dir / "dist"
        dist_dir.mkdir(parents=True)
        (dist_dir / "index.html").write_text(ui_dir, encoding="utf-8")

    ui_static_path = tmp_path / "package" / "server" / "ui"
    ui_v2_static_path = tmp_path / "package" / "server" / "ui-v2"

    monkeypatch.setattr(prefect, "__development_base_path__", development_base_path)
    monkeypatch.setattr(prefect, "__ui_static_path__", ui_static_path)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", ui_v2_static_path)

    return ui_static_path, ui_v2_static_path


def test_dev_build_ui_builds_v1_bundle_by_default(monkeypatch, tmp_path):
    ui_static_path, ui_v2_static_path = _setup_ui_build_paths(monkeypatch, tmp_path)
    calls = []

    def mock_check_output(command, **kwargs):
        calls.append((Path.cwd().name, command, "env" in kwargs))

    monkeypatch.setattr(prefect.cli.dev.subprocess, "check_output", mock_check_output)

    invoke_and_assert(["dev", "build-ui"], expected_code=0)

    assert calls == [
        ("ui", ["npm", "ci"], False),
        ("ui", ["npm", "run", "build"], True),
    ]
    assert (ui_static_path / "index.html").read_text(encoding="utf-8") == "ui"
    assert not ui_v2_static_path.exists()


def test_dev_build_ui_include_v2_builds_both_bundles_without_install(
    monkeypatch, tmp_path
):
    ui_static_path, ui_v2_static_path = _setup_ui_build_paths(monkeypatch, tmp_path)
    calls = []

    def mock_check_output(command, **kwargs):
        calls.append((Path.cwd().name, command, "env" in kwargs))

    monkeypatch.setattr(prefect.cli.dev.subprocess, "check_output", mock_check_output)

    invoke_and_assert(
        ["dev", "build-ui", "--include-v2", "--no-install"], expected_code=0
    )

    assert calls == [
        ("ui", ["npm", "run", "build"], True),
        ("ui-v2", ["npm", "run", "build"], True),
    ]
    assert (ui_static_path / "index.html").read_text(encoding="utf-8") == "ui"
    assert (ui_v2_static_path / "index.html").read_text(encoding="utf-8") == "ui-v2"


def test_dev_start_runs_all_services(monkeypatch):
    """
    Test that `prefect dev start` runs all services. This test mocks out the
    `run_process` function along with the `watchfiles.arun_process` function
    so the test doesn't actually start any processes; instead, it verifies that
    the command attempts to start all services correctly.
    """

    # Mock run_process for UI and API start
    mock_run_process = AsyncMock()

    # Call task_status.started() if run_process was triggered by an
    # anyio task group `start` call.
    def mock_run_process_call(*args, **kwargs):
        if "task_status" in kwargs:
            kwargs["task_status"].started()

    mock_run_process.side_effect = mock_run_process_call
    monkeypatch.setattr(prefect.cli.dev, "run_process", mock_run_process)

    # mock `os.kill` since we're not actually running the processes
    mock_kill = MagicMock()
    monkeypatch.setattr(prefect.cli.dev.os, "kill", mock_kill)

    # mock watchfiles.awatch
    mock_awatch = MagicMock()

    # mock_awatch needs to return an async generator
    async def async_generator():
        yield None

    mock_awatch.return_value = async_generator()
    monkeypatch.setattr(watchfiles, "awatch", mock_awatch)

    invoke_and_assert(["dev", "start"], expected_code=0)

    # ensure one of the calls to run_process was for the UI server
    mock_run_process.assert_any_call(
        command=["npm", "run", "serve"], stream_output=True
    )

    # ensure run_process was called for the API server by checking that
    # the 'command' passed to one of the calls was an array with "uvicorn" included
    uvicorn_called = False
    for call in mock_run_process.call_args_list:
        if "command" in call.kwargs and "uvicorn" in call.kwargs["command"]:
            uvicorn_called = True
            break

    assert uvicorn_called
