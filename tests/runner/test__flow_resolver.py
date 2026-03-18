from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import HTTPStatusError, Request, Response

from prefect.runner._flow_resolver import FlowResolver


def _make_flow_run(deployment_id=None):
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.deployment_id = deployment_id
    return flow_run


class TestFlowResolver:
    async def test_resolves_from_bundle_map(self, tmp_path: Path):
        flow_run = _make_flow_run(deployment_id=uuid4())
        bundle_sentinel = MagicMock()
        expected_flow = MagicMock()
        extract_flow = MagicMock(return_value=expected_flow)
        load_flow = AsyncMock()

        resolver = FlowResolver(
            bundle_map={flow_run.id: bundle_sentinel},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )
        result = await resolver.resolve(flow_run)

        assert result is expected_flow
        extract_flow.assert_called_once_with(bundle_sentinel)
        load_flow.assert_not_awaited()

    async def test_resolves_from_deployment_flow_map(self, tmp_path: Path):
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)
        expected_flow = MagicMock()
        load_flow = AsyncMock()
        extract_flow = MagicMock()

        resolver = FlowResolver(
            bundle_map={},
            deployment_flow_map={deployment_id: expected_flow},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )
        result = await resolver.resolve(flow_run)

        assert result is expected_flow
        load_flow.assert_not_awaited()

    async def test_resolves_from_api_fallback(self, tmp_path: Path):
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)
        expected_flow = MagicMock()
        load_flow = AsyncMock(return_value=expected_flow)
        extract_flow = MagicMock()

        resolver = FlowResolver(
            bundle_map={},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )
        result = await resolver.resolve(flow_run)

        assert result is expected_flow
        load_flow.assert_awaited_once_with(flow_run, storage_base_path=str(tmp_path))

    async def test_api_exception_propagates(self, tmp_path: Path):
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)
        request = Request("GET", "http://test")
        response = Response(status_code=500, request=request)
        load_flow = AsyncMock(
            side_effect=HTTPStatusError(
                "server error", request=request, response=response
            )
        )
        extract_flow = MagicMock()

        resolver = FlowResolver(
            bundle_map={},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )

        with pytest.raises(HTTPStatusError):
            await resolver.resolve(flow_run)

    async def test_total_miss_raises_value_error(self, tmp_path: Path):
        flow_run = _make_flow_run(deployment_id=None)
        load_flow = AsyncMock()
        extract_flow = MagicMock()

        resolver = FlowResolver(
            bundle_map={},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )

        with pytest.raises(ValueError, match="Cannot resolve flow"):
            await resolver.resolve(flow_run)

        load_flow.assert_not_awaited()

    async def test_cache_hit_skips_api_call(self, tmp_path: Path):
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)
        expected_flow = MagicMock()
        load_flow = AsyncMock(return_value=expected_flow)
        extract_flow = MagicMock()

        resolver = FlowResolver(
            bundle_map={},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )

        first = await resolver.resolve(flow_run)
        second = await resolver.resolve(flow_run)

        assert first is expected_flow
        assert second is expected_flow
        assert load_flow.await_count == 1

    async def test_cache_is_instance_scoped(self, tmp_path: Path):
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)
        flow_a = MagicMock()
        flow_b = MagicMock()
        load_flow_a = AsyncMock(return_value=flow_a)
        load_flow_b = AsyncMock(return_value=flow_b)
        extract_flow = MagicMock()

        resolver_a = FlowResolver(
            bundle_map={},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow_a,
            extract_flow_from_bundle=extract_flow,
        )
        resolver_b = FlowResolver(
            bundle_map={},
            deployment_flow_map={},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow_b,
            extract_flow_from_bundle=extract_flow,
        )

        result_a = await resolver_a.resolve(flow_run)
        result_b = await resolver_b.resolve(flow_run)

        assert result_a is flow_a
        assert result_b is flow_b
        load_flow_a.assert_awaited_once()
        load_flow_b.assert_awaited_once()

    async def test_bundle_map_takes_priority_over_deployment_map(self, tmp_path: Path):
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)
        bundle_sentinel = MagicMock()
        bundle_flow = MagicMock()
        deployment_flow = MagicMock()
        extract_flow = MagicMock(return_value=bundle_flow)
        load_flow = AsyncMock()

        resolver = FlowResolver(
            bundle_map={flow_run.id: bundle_sentinel},
            deployment_flow_map={deployment_id: deployment_flow},
            tmp_dir=tmp_path,
            load_flow_from_flow_run=load_flow,
            extract_flow_from_bundle=extract_flow,
        )
        result = await resolver.resolve(flow_run)

        assert result is bundle_flow
        extract_flow.assert_called_once_with(bundle_sentinel)
        load_flow.assert_not_awaited()
