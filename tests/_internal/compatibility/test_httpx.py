import importlib.util
import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

RunPython = Callable[[str, str | None], subprocess.CompletedProcess[str]]

HTTP_BACKENDS = [
    "httpx",
    pytest.param(
        "httpx2",
        marks=pytest.mark.skipif(
            importlib.util.find_spec("httpx2") is None,
            reason=(
                "Requires 'httpx2[http2]>=2.13.0,<3.0.0'; "
                "exercised by the HTTPX2 CI job"
            ),
        ),
    ),
]


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


@pytest.mark.parametrize("backend", [None, *HTTP_BACKENDS])
def test_backend_selection_is_explicit(run_python: RunPython, backend: str | None):
    result = run_python(
        f"""
        import importlib.util
        if importlib.util.find_spec("httpx2") is not None:
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
    assert "PREFECT_CLIENT_HTTP_BACKEND=httpx2 requires" in result.stderr
    assert "httpx2[http2]>=2.13.0,<3.0.0" in result.stderr


def test_invalid_backend_has_configuration_error(run_python: RunPython):
    result = run_python("from prefect import get_client", "unsupported")
    assert result.returncode != 0
    assert "PREFECT_CLIENT_HTTP_BACKEND must be 'httpx' or 'httpx2'" in result.stderr
    assert "got 'unsupported'" in result.stderr


@pytest.mark.parametrize("backend", HTTP_BACKENDS)
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


@pytest.mark.parametrize("backend", HTTP_BACKENDS)
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
        assert "httpx2[http2]>=2.13.0,<3.0.0" in result.stderr
        assert "PREFECT_CLIENT_HTTP_BACKEND=httpx2" in result.stderr


@pytest.mark.parametrize("backend", HTTP_BACKENDS)
@pytest.mark.parametrize("entrypoint", ["webhook", "notify", "anotify"])
def test_standalone_http_blocks_share_legacy_warning(
    run_python: RunPython, backend: str, entrypoint: str
):
    result = run_python(
        f"""
        import asyncio
        import warnings
        from unittest.mock import patch

        from prefect._internal.compatibility.httpx import (
            PrefectHTTPXDeprecationWarning, httpx,
        )
        from prefect.blocks.notifications import CustomWebhookNotificationBlock
        from prefect.blocks.webhook import Webhook
        from prefect.client.base import PrefectHttpxAsyncClient, PrefectHttpxSyncClient

        def respond(client, method, url, **kwargs):
            assert isinstance(client, (httpx.Client, httpx.AsyncClient))
            return httpx.Response(200, request=httpx.Request(method, url))

        async def respond_async(client, method, url, **kwargs):
            return respond(client, method, url, **kwargs)

        def use_block():
            if {entrypoint!r} == "webhook":
                block = Webhook(url="https://example.test/")
                response = asyncio.run(block.call(payload="test"))
                assert type(response) is httpx.Response
            else:
                block = CustomWebhookNotificationBlock(
                    name="test", url="https://example.test/",
                )
                if {entrypoint!r} == "notify":
                    block.notify("test")
                else:
                    asyncio.run(block.anotify("test"))

        async def use_async_client():
            async with PrefectHttpxAsyncClient():
                pass

        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter("always", PrefectHTTPXDeprecationWarning)
            with patch.object(httpx.Client, "request", respond), patch.object(
                httpx.AsyncClient, "request", respond_async
            ):
                for _ in range(2):
                    use_block()
                    assert sum(
                        issubclass(notice.category, PrefectHTTPXDeprecationWarning)
                        for notice in notices
                    ) == {1 if backend == "httpx" else 0}, notices

            with PrefectHttpxSyncClient():
                pass
            asyncio.run(use_async_client())
            assert sum(
                issubclass(notice.category, PrefectHTTPXDeprecationWarning)
                for notice in notices
            ) == {1 if backend == "httpx" else 0}, notices
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("backend", HTTP_BACKENDS)
@pytest.mark.parametrize("subscriber_type", ["events", "logs"])
@pytest.mark.parametrize("version_check", ["enabled", "disabled", "cloud"])
def test_standalone_subscribers_warn_only_when_using_http(
    run_python: RunPython, backend: str, subscriber_type: str, version_check: str
):
    result = run_python(
        f"""
        import asyncio
        import warnings
        from unittest.mock import AsyncMock, patch

        import prefect
        from prefect._internal.compatibility.httpx import (
            PrefectHTTPXDeprecationWarning, httpx,
        )
        from prefect.events.clients import PrefectEventSubscriber
        from prefect.logging.clients import PrefectLogsSubscriber
        from prefect.settings import (
            PREFECT_CLIENT_SERVER_VERSION_CHECK_ENABLED,
            PREFECT_CLOUD_API_URL,
            temporary_settings,
        )

        subscriber_class = (
            PrefectEventSubscriber if {subscriber_type!r} == "events"
            else PrefectLogsSubscriber
        )
        module = "prefect.events.clients" if {subscriber_type!r} == "events" else "prefect.logging.clients"
        api_url = (
            str(PREFECT_CLOUD_API_URL.value()) + "/accounts/test/workspaces/test"
            if {version_check!r} == "cloud" else "https://example.test/api"
        )
        requests = []

        async def get_version(client, url, **kwargs):
            assert isinstance(client, httpx.AsyncClient)
            requests.append(url)
            return httpx.Response(
                200, request=httpx.Request("GET", url), json=prefect.__version__,
            )

        async def connect_subscriber():
            websocket = AsyncMock()
            pong = asyncio.get_running_loop().create_future()
            pong.set_result(None)
            websocket.ping.return_value = pong
            websocket.recv.return_value = '{{"type": "auth_success"}}'
            connection = AsyncMock()
            connection.__aenter__.return_value = websocket
            with patch(module + ".websocket_connect", return_value=connection):
                async with subscriber_class(api_url=api_url):
                    pass
            websocket.send.assert_awaited()

        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter("always", PrefectHTTPXDeprecationWarning)
            with temporary_settings({{
                PREFECT_CLIENT_SERVER_VERSION_CHECK_ENABLED: {version_check != "disabled"!r},
            }}), patch.object(httpx.AsyncClient, "get", get_version):
                for _ in range(2):
                    asyncio.run(connect_subscriber())
                    assert sum(
                        issubclass(notice.category, PrefectHTTPXDeprecationWarning)
                        for notice in notices
                    ) == {int(backend == "httpx" and version_check == "enabled")}, notices
                    assert len(requests) == {int(version_check == "enabled")}, requests
        """,
        backend,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("backend", HTTP_BACKENDS)
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


@pytest.mark.parametrize("backend", HTTP_BACKENDS)
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
