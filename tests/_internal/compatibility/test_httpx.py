import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

RunPython = Callable[[str, str | None], subprocess.CompletedProcess[str]]


@pytest.fixture
def run_python(tmp_path: Path, hosted_api_server: str) -> RunPython:
    def run(script: str, backend: str | None) -> subprocess.CompletedProcess[str]:
        environment = {
            **os.environ,
            "PREFECT_HOME": str(tmp_path / "prefect"),
            "PREFECT_PROFILES_PATH": str(tmp_path / "profiles.toml"),
            "PREFECT_API_URL": hosted_api_server,
            "PREFECT_API_KEY": "",
            "PREFECT_PLUGINS_ENABLED": "false",
            "PREFECT_LOGGING_TO_API_ENABLED": "false",
        }
        environment.pop("PREFECT_CLIENT_HTTP_BACKEND", None)
        environment.pop("PYTHONWARNINGS", None)
        if backend is not None:
            environment["PREFECT_CLIENT_HTTP_BACKEND"] = backend
        script_path = tmp_path / "check_backend.py"
        script_path.write_text(textwrap.dedent(script))
        return subprocess.run(
            [sys.executable, str(script_path), str(tmp_path / "backend-result.txt")],
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )

    return run


@pytest.mark.parametrize("backend", [None, "httpx", "httpx2"])
def test_backend_selection_is_explicit(run_python: RunPython, backend: str | None):
    result = run_python(
        f"""
        import importlib
        import httpx2
        from prefect.client.base import PrefectHttpxSyncClient
        from prefect.exceptions import PrefectHTTPStatusError

        selected = importlib.import_module({backend or "httpx"!r})
        assert issubclass(PrefectHttpxSyncClient, selected.Client)
        assert issubclass(PrefectHTTPStatusError, selected.HTTPStatusError)
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr


def test_default_backend_does_not_import_httpx2(run_python: RunPython):
    result = run_python(
        """
        import importlib.abc
        import sys

        class BlockHTTPX2(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {"httpx2", "httpcore2"}:
                    raise ModuleNotFoundError("HTTPX2 is not installed", name=fullname)

        sys.meta_path.insert(0, BlockHTTPX2())
        from prefect import get_client
        from prefect.client.cloud import CloudClient
        from prefect.blocks.webhook import Webhook
        from prefect.exceptions import PrefectHTTPStatusError
        import httpx

        assert issubclass(PrefectHTTPStatusError, httpx.HTTPStatusError)
        assert "httpx2" not in sys.modules
        assert "httpcore2" not in sys.modules
        """,
        None,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("missing_package", ["httpx2", "httpcore2"])
def test_missing_optional_dependency_has_install_hint(
    run_python: RunPython, missing_package: str
):
    result = run_python(
        f"""
        import importlib.abc
        import sys

        class MissingDependency(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == {missing_package!r}:
                    raise ModuleNotFoundError("Package is not installed", name=fullname)

        sys.meta_path.insert(0, MissingDependency())
        from prefect import get_client
        """,
        "httpx2",
    )
    assert result.returncode != 0
    assert (
        "PREFECT_CLIENT_HTTP_BACKEND=httpx2 requires the HTTPX2 extra" in result.stderr
    )
    assert "prefect[httpx2]" in result.stderr
    assert "prefect-client[httpx2]" in result.stderr


def test_invalid_backend_has_configuration_error(run_python: RunPython):
    result = run_python("from prefect import get_client", "unsupported")
    assert result.returncode != 0
    assert "PREFECT_CLIENT_HTTP_BACKEND must be 'httpx' or 'httpx2'" in result.stderr
    assert "got 'unsupported'" in result.stderr


@pytest.mark.parametrize("backend", ["httpx", "httpx2"])
def test_backend_cannot_change_after_import(run_python: RunPython, backend: str):
    other_backend = "httpx2" if backend == "httpx" else "httpx"
    result = run_python(
        f"""
        import importlib
        import os
        from prefect.client.base import PrefectHttpxSyncClient

        os.environ["PREFECT_CLIENT_HTTP_BACKEND"] = {other_backend!r}
        from prefect.exceptions import PrefectHTTPStatusError

        selected = importlib.import_module({backend!r})
        assert issubclass(PrefectHttpxSyncClient, selected.Client)
        assert issubclass(PrefectHTTPStatusError, selected.HTTPStatusError)
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("backend", ["httpx", "httpx2"])
def test_legacy_warning_is_visible_once_per_process(
    run_python: RunPython, backend: str
):
    result = run_python(
        """
        import asyncio
        from prefect.client.base import PrefectHttpxAsyncClient, PrefectHttpxSyncClient

        async def use_clients():
            for _ in range(2):
                with PrefectHttpxSyncClient(base_url="https://example.test"):
                    pass
                async with PrefectHttpxAsyncClient(base_url="https://example.test"):
                    pass

        asyncio.run(use_clients())
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.count("PrefectHTTPXDeprecationWarning:") == (
        1 if backend == "httpx" else 0
    )
    if backend == "httpx":
        assert "six months and three minor version increases" in result.stderr
        assert "PREFECT_CLIENT_HTTP_BACKEND=httpx2" in result.stderr


@pytest.mark.parametrize("backend", ["httpx", "httpx2"])
def test_flow_subprocess_inherits_backend(
    run_python: RunPython, tmp_path: Path, backend: str
):
    result = run_python(
        f"""
        import importlib
        import sys
        from pathlib import Path

        from prefect import flow, get_client
        from prefect.exceptions import PrefectHTTPStatusError
        from prefect.flow_engine import run_flow_in_subprocess

        @flow
        def check_backend():
            selected = importlib.import_module({backend!r})
            assert issubclass(PrefectHTTPStatusError, selected.HTTPStatusError)
            with get_client(sync_client=True) as client:
                assert isinstance(client.hello(), selected.Response)
            Path(sys.argv[1]).write_text(selected.__name__)

        if __name__ == "__main__":
            process = run_flow_in_subprocess(check_backend)
            try:
                process.join(timeout=60)
                assert process.exitcode == 0, process.exitcode
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=10)
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "backend-result.txt").read_text() == backend


@pytest.mark.parametrize("backend", ["httpx", "httpx2"])
@pytest.mark.parametrize(
    "override_location", ["flow_environment", "process_environment"]
)
def test_flow_subprocess_rejects_backend_changes(
    run_python: RunPython, backend: str, override_location: str
):
    other_backend = "httpx2" if backend == "httpx" else "httpx"
    result = run_python(
        f"""
        import os
        from prefect import flow
        from prefect.flow_engine import run_flow_in_subprocess

        @flow
        def unexpected_flow():
            raise AssertionError("The flow must not run with a different HTTP backend")

        if __name__ == "__main__":
            env = {{}}
            if {override_location!r} == "process_environment":
                os.environ["PREFECT_CLIENT_HTTP_BACKEND"] = {other_backend!r}
            else:
                env["PREFECT_CLIENT_HTTP_BACKEND"] = {other_backend!r}
            try:
                process = run_flow_in_subprocess(unexpected_flow, env=env)
            except ValueError as exc:
                assert "PREFECT_CLIENT_HTTP_BACKEND must be configured before starting the worker" in str(exc)
            else:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=10)
                raise AssertionError("Changing the subprocess backend must be rejected")
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr
