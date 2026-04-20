"""
Tests for attribution headers functionality.
"""

import os
from unittest import mock
from uuid import uuid4

import httpx
from httpx import Request, Response

from prefect._internal.compatibility.starlette import status
from prefect.client.attribution import get_attribution_headers
from prefect.client.base import PrefectHttpxAsyncClient, PrefectHttpxSyncClient

RESPONSE_200 = Response(
    status.HTTP_200_OK,
    request=Request("a test request", "fake.url/fake/route"),
)


class TestGetAttributionHeaders:
    """Tests for the get_attribution_headers function."""

    def test_returns_empty_dict_with_no_context(self):
        """When no context is available, should return empty headers."""
        env_vars = [
            "PREFECT__WORKER_ID",
            "PREFECT__WORKER_NAME",
            "PREFECT__FLOW_ID",
            "PREFECT__FLOW_NAME",
            "PREFECT__DEPLOYMENT_ID",
            "PREFECT__DEPLOYMENT_NAME",
        ]
        with mock.patch.dict(os.environ, {}, clear=True):
            for var in env_vars:
                os.environ.pop(var, None)

            headers = get_attribution_headers()

        assert "X-Prefect-Worker-Id" not in headers
        assert "X-Prefect-Worker-Name" not in headers
        assert "X-Prefect-Flow-Id" not in headers
        assert "X-Prefect-Flow-Name" not in headers

    def test_includes_worker_id_from_env(self):
        """Worker ID should be read from environment variable."""
        worker_id = str(uuid4())
        with mock.patch.dict(os.environ, {"PREFECT__WORKER_ID": worker_id}):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Worker-Id"] == worker_id

    def test_includes_worker_name_from_env(self):
        """Worker name should be read from environment variable."""
        with mock.patch.dict(os.environ, {"PREFECT__WORKER_NAME": "test-worker"}):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Worker-Name"] == "test-worker"

    def test_includes_flow_id_from_env(self):
        """Flow ID should be read from environment variable when no context."""
        flow_id = str(uuid4())
        with mock.patch.dict(os.environ, {"PREFECT__FLOW_ID": flow_id}):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Flow-Id"] == flow_id

    def test_includes_flow_name_from_env(self):
        """Flow name should be read from environment variable when no context."""
        with mock.patch.dict(os.environ, {"PREFECT__FLOW_NAME": "my-flow"}):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Flow-Name"] == "my-flow"

    def test_includes_deployment_id_from_env(self):
        """Deployment ID should be read from environment variable when no context."""
        deployment_id = str(uuid4())
        with mock.patch.dict(os.environ, {"PREFECT__DEPLOYMENT_ID": deployment_id}):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Deployment-Id"] == deployment_id

    def test_includes_deployment_name_from_env(self):
        """Deployment name should be read from environment variable when no context."""
        with mock.patch.dict(os.environ, {"PREFECT__DEPLOYMENT_NAME": "my-deployment"}):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Deployment-Name"] == "my-deployment"

    def test_includes_flow_info_from_context(self):
        """Flow info should be read from FlowRunContext when available."""
        from prefect.client.schemas import FlowRun
        from prefect.context import FlowRunContext

        flow_id = uuid4()
        deployment_id = uuid4()
        flow_run = FlowRun(
            id=uuid4(),
            name="test-flow-run",
            flow_id=flow_id,
            deployment_id=deployment_id,
        )

        mock_context = mock.MagicMock(spec=FlowRunContext)
        mock_context.flow_run = flow_run
        mock_context.flow = mock.MagicMock()
        mock_context.flow.name = "test-flow"

        with mock.patch.object(FlowRunContext, "get", return_value=mock_context):
            headers = get_attribution_headers()

        assert headers["X-Prefect-Flow-Id"] == str(flow_id)
        assert headers["X-Prefect-Flow-Name"] == "test-flow"
        assert headers["X-Prefect-Deployment-Id"] == str(deployment_id)

    def test_context_takes_precedence_over_env(self):
        """Context should take precedence over environment variables for flow info."""
        from prefect.client.schemas import FlowRun
        from prefect.context import FlowRunContext

        context_flow_id = uuid4()
        env_flow_id = str(uuid4())

        flow_run = FlowRun(
            id=uuid4(),
            name="context-flow-run",
            flow_id=context_flow_id,
        )

        mock_context = mock.MagicMock(spec=FlowRunContext)
        mock_context.flow_run = flow_run
        mock_context.flow = mock.MagicMock()
        mock_context.flow.name = "context-flow"

        with mock.patch.dict(os.environ, {"PREFECT__FLOW_ID": env_flow_id}):
            with mock.patch.object(FlowRunContext, "get", return_value=mock_context):
                headers = get_attribution_headers()

        assert headers["X-Prefect-Flow-Id"] == str(context_flow_id)
        assert headers["X-Prefect-Flow-Name"] == "context-flow"

    def test_all_headers_present_with_full_context(self):
        """All headers should be present when full context is available."""
        from prefect.client.schemas import FlowRun
        from prefect.context import FlowRunContext

        worker_id = str(uuid4())
        worker_name = "full-context-worker"
        flow_id = uuid4()
        deployment_id = uuid4()

        flow_run = FlowRun(
            id=uuid4(),
            name="full-context-flow-run",
            flow_id=flow_id,
            deployment_id=deployment_id,
        )

        mock_context = mock.MagicMock(spec=FlowRunContext)
        mock_context.flow_run = flow_run
        mock_context.flow = mock.MagicMock()
        mock_context.flow.name = "full-context-flow"

        with mock.patch.dict(
            os.environ,
            {
                "PREFECT__WORKER_ID": worker_id,
                "PREFECT__WORKER_NAME": worker_name,
                "PREFECT__DEPLOYMENT_NAME": "full-context-deployment",
            },
        ):
            with mock.patch.object(FlowRunContext, "get", return_value=mock_context):
                headers = get_attribution_headers()

        assert headers["X-Prefect-Worker-Id"] == worker_id
        assert headers["X-Prefect-Worker-Name"] == worker_name
        assert headers["X-Prefect-Flow-Id"] == str(flow_id)
        assert headers["X-Prefect-Flow-Name"] == "full-context-flow"
        assert headers["X-Prefect-Deployment-Id"] == str(deployment_id)
        assert headers["X-Prefect-Deployment-Name"] == "full-context-deployment"

    def test_deployment_name_from_env_when_in_context(self):
        """Deployment name should come from env var even when in context."""
        from prefect.client.schemas import FlowRun
        from prefect.context import FlowRunContext

        flow_run = FlowRun(
            id=uuid4(),
            name="test-flow-run",
            flow_id=uuid4(),
            deployment_id=uuid4(),
        )

        mock_context = mock.MagicMock(spec=FlowRunContext)
        mock_context.flow_run = flow_run
        mock_context.flow = mock.MagicMock()
        mock_context.flow.name = "test-flow"

        with mock.patch.dict(os.environ, {"PREFECT__DEPLOYMENT_NAME": "my-deployment"}):
            with mock.patch.object(FlowRunContext, "get", return_value=mock_context):
                headers = get_attribution_headers()

        assert headers["X-Prefect-Deployment-Name"] == "my-deployment"


class TestAsyncClientAttributionHeaders:
    """Tests that PrefectHttpxAsyncClient adds attribution headers."""

    async def test_attribution_headers_added_to_requests(self):
        """Attribution headers should be added to all requests."""
        worker_id = str(uuid4())
        worker_name = "test-worker"
        flow_id = str(uuid4())
        flow_name = "test-flow"

        with mock.patch.dict(
            os.environ,
            {
                "PREFECT__WORKER_ID": worker_id,
                "PREFECT__WORKER_NAME": worker_name,
                "PREFECT__FLOW_ID": flow_id,
                "PREFECT__FLOW_NAME": flow_name,
            },
        ):
            with mock.patch("httpx.AsyncClient.send", autospec=True) as send:
                send.return_value = RESPONSE_200
                async with PrefectHttpxAsyncClient() as client:
                    await client.get(url="fake.url/fake/route")

                request = send.call_args[0][1]
                assert isinstance(request, httpx.Request)

                assert request.headers["X-Prefect-Worker-Id"] == worker_id
                assert request.headers["X-Prefect-Worker-Name"] == worker_name
                assert request.headers["X-Prefect-Flow-Id"] == flow_id
                assert request.headers["X-Prefect-Flow-Name"] == flow_name

    async def test_missing_attribution_values_not_in_headers(self):
        """Headers should not be present when values are not available."""
        from prefect.context import FlowRunContext

        env = os.environ.copy()
        for var in [
            "PREFECT__WORKER_ID",
            "PREFECT__WORKER_NAME",
            "PREFECT__FLOW_ID",
            "PREFECT__FLOW_NAME",
            "PREFECT__DEPLOYMENT_ID",
            "PREFECT__DEPLOYMENT_NAME",
        ]:
            env.pop(var, None)

        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(FlowRunContext, "get", return_value=None):
                with mock.patch("httpx.AsyncClient.send", autospec=True) as send:
                    send.return_value = RESPONSE_200
                    async with PrefectHttpxAsyncClient() as client:
                        await client.get(url="fake.url/fake/route")

                    request = send.call_args[0][1]
                    assert isinstance(request, httpx.Request)

                    assert "X-Prefect-Worker-Id" not in request.headers
                    assert "X-Prefect-Worker-Name" not in request.headers
                    assert "X-Prefect-Flow-Id" not in request.headers
                    assert "X-Prefect-Flow-Name" not in request.headers


class TestSyncClientAttributionHeaders:
    """Tests that PrefectHttpxSyncClient adds attribution headers."""

    def test_attribution_headers_added_to_requests(self):
        """Attribution headers should be added to all requests."""
        worker_id = str(uuid4())
        worker_name = "test-sync-worker"
        flow_id = str(uuid4())
        flow_name = "test-sync-flow"

        with mock.patch.dict(
            os.environ,
            {
                "PREFECT__WORKER_ID": worker_id,
                "PREFECT__WORKER_NAME": worker_name,
                "PREFECT__FLOW_ID": flow_id,
                "PREFECT__FLOW_NAME": flow_name,
            },
        ):
            with mock.patch("httpx.Client.send", autospec=True) as send:
                send.return_value = RESPONSE_200
                with PrefectHttpxSyncClient() as client:
                    client.get(url="fake.url/fake/route")

                request = send.call_args[0][1]
                assert isinstance(request, httpx.Request)

                assert request.headers["X-Prefect-Worker-Id"] == worker_id
                assert request.headers["X-Prefect-Worker-Name"] == worker_name
                assert request.headers["X-Prefect-Flow-Id"] == flow_id
                assert request.headers["X-Prefect-Flow-Name"] == flow_name
