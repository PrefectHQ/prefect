from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import prefect.bundles as bundles_module
import prefect.bundles.execute as execute_module
import prefect.runner._starter_bundle as starter_module
from prefect import flow
from prefect.bundles import create_bundle_for_flow_run
from prefect.bundles.execute import execute_bundle, execute_bundle_from_file
from prefect.client.orchestration import PrefectClient
from prefect.logging.loggers import flow_run_logger


def _log_bundle_crashed_hook(flow: Any, flow_run: Any, state: Any) -> None:
    flow_run_logger(flow_run, flow).error("bundle crash hook ran")


async def test_execute_bundle_creates_executor_with_propose_submitting_false(
    prefect_client: PrefectClient,
):
    @flow
    def test_flow() -> str:
        return "ok"

    flow_run = await prefect_client.create_flow_run(test_flow)
    bundle: dict[str, Any] = {
        "flow_run": flow_run.model_dump(mode="json"),
    }

    captured_kwargs: dict[str, Any] = {}
    mock_submit = AsyncMock(return_value=None)

    from prefect.runner._flow_run_executor import FlowRunExecutorContext

    original_create_executor = FlowRunExecutorContext.create_executor

    def capture_create_executor(
        self_ctx: FlowRunExecutorContext, *args: Any, **kwargs: Any
    ) -> Any:
        captured_kwargs.update(kwargs)
        result = original_create_executor(self_ctx, *args, **kwargs)
        result.submit = mock_submit
        return result

    with patch.object(
        FlowRunExecutorContext,
        "create_executor",
        side_effect=capture_create_executor,
        autospec=True,
    ):
        await execute_bundle(bundle)

    assert captured_kwargs.get("propose_submitting") is False


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_execute_bundle_preserves_failed_outcome(
    prefect_client: PrefectClient,
    caplog: pytest.LogCaptureFixture,
):
    @flow(on_crashed=[_log_bundle_crashed_hook])
    def failed_flow() -> None:
        raise ValueError("application failure")

    flow_run = await prefect_client.create_flow_run(failed_flow)
    with patch.object(
        bundles_module.subprocess,
        "check_output",
        MagicMock(return_value=b""),
    ):
        bundle = create_bundle_for_flow_run(failed_flow, flow_run)["bundle"]

    processes: list[Any] = []
    original_execute_bundle_in_subprocess = starter_module.execute_bundle_in_subprocess

    def tracking_execute_bundle(*args: Any, **kwargs: Any):
        process = original_execute_bundle_in_subprocess(*args, **kwargs)
        processes.append(process)
        return process

    with patch.object(
        starter_module,
        "execute_bundle_in_subprocess",
        side_effect=tracking_execute_bundle,
    ):
        infrastructure_result = await execute_bundle(bundle)

    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert processes[0].exitcode == 0
    assert infrastructure_result is None
    assert flow_run.state is not None
    assert flow_run.state.is_failed()
    assert "bundle crash hook ran" not in caplog.text
    assert "Process exited with status code: 1" not in caplog.text


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_execute_bundle_preserves_crash_fallback(
    prefect_client: PrefectClient,
    caplog: pytest.LogCaptureFixture,
):
    @flow(on_crashed=[_log_bundle_crashed_hook])
    def crashed_flow() -> None:
        os._exit(7)

    flow_run = await prefect_client.create_flow_run(crashed_flow)
    with patch.object(
        bundles_module.subprocess,
        "check_output",
        MagicMock(return_value=b""),
    ):
        bundle = create_bundle_for_flow_run(crashed_flow, flow_run)["bundle"]

    processes: list[Any] = []
    original_execute_bundle_in_subprocess = starter_module.execute_bundle_in_subprocess

    def tracking_execute_bundle(*args: Any, **kwargs: Any):
        process = original_execute_bundle_in_subprocess(*args, **kwargs)
        processes.append(process)
        return process

    with patch.object(
        starter_module,
        "execute_bundle_in_subprocess",
        side_effect=tracking_execute_bundle,
    ):
        await execute_bundle(bundle)

    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert processes[0].exitcode == 7
    assert flow_run.state is not None
    assert flow_run.state.is_crashed()
    assert "bundle crash hook ran" in caplog.text
    assert "Process exited with status code: 7" in caplog.text


class TestExecuteBundleFromFile:
    @pytest.fixture
    def bundle_dir(self, tmp_path: Path) -> Path:
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()
        return bundle_dir

    @pytest.fixture
    def working_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        working_dir = tmp_path / "working"
        working_dir.mkdir()
        monkeypatch.chdir(working_dir)
        return working_dir

    @pytest.fixture
    def files_at_execution(
        self, working_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        """Files present in the working directory when the bundle is executed."""
        files_at_execution: list[str] = []

        async def record_files(bundle: dict[str, Any]) -> None:
            files_at_execution.extend(
                sorted(
                    path.relative_to(working_dir).as_posix()
                    for path in working_dir.rglob("*")
                    if path.is_file()
                )
            )

        monkeypatch.setattr(execute_module, "execute_bundle", record_files)
        return files_at_execution

    def _write_bundle(self, bundle_dir: Path, files_key: str | None) -> Path:
        bundle_path = bundle_dir / "bundle-key"
        bundle_path.write_text(
            json.dumps({"flow_run": {"id": "test-run"}, "files_key": files_key})
        )
        return bundle_path

    def test_extracts_included_files_before_execution(
        self, bundle_dir: Path, files_at_execution: list[str]
    ) -> None:
        sidecar_path = bundle_dir / "files" / "abc123.zip"
        sidecar_path.parent.mkdir()
        with zipfile.ZipFile(sidecar_path, "w") as zf:
            zf.writestr("config.yaml", "key: value")
            zf.writestr("data/input.csv", "a,b\n1,2")

        bundle_path = self._write_bundle(bundle_dir, "files/abc123.zip")

        execute_bundle_from_file(str(bundle_path))

        assert files_at_execution == ["config.yaml", "data/input.csv"]

    def test_extracted_file_contents_are_preserved(
        self, bundle_dir: Path, working_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sidecar_path = bundle_dir / "files" / "abc123.zip"
        sidecar_path.parent.mkdir()
        with zipfile.ZipFile(sidecar_path, "w") as zf:
            zf.writestr("data/input.csv", "a,b\n1,2")

        bundle_path = self._write_bundle(bundle_dir, "files/abc123.zip")

        monkeypatch.setattr(execute_module, "execute_bundle", AsyncMock())
        execute_bundle_from_file(str(bundle_path))

        assert (working_dir / "data" / "input.csv").read_text() == "a,b\n1,2"

    def test_raises_when_sidecar_is_missing(
        self, bundle_dir: Path, working_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle_path = self._write_bundle(bundle_dir, "files/missing.zip")

        execute = AsyncMock()
        monkeypatch.setattr(execute_module, "execute_bundle", execute)

        with pytest.raises(RuntimeError, match="files/missing.zip"):
            execute_bundle_from_file(str(bundle_path))

        execute.assert_not_awaited()

    def test_executes_bundle_without_included_files(
        self, bundle_dir: Path, files_at_execution: list[str]
    ) -> None:
        bundle_path = self._write_bundle(bundle_dir, None)

        execute_bundle_from_file(str(bundle_path))

        assert files_at_execution == []
