from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from prefect.runner._event_emitter import _EventEmitter

from prefect.client.schemas.objects import Flow as APIFlow
from prefect.client.schemas.responses import DeploymentResponse
from prefect.events.clients import AssertingEventsClient


def _make_flow_run(
    deployment_id=None,
    tags: list[str] | None = None,
) -> MagicMock:
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.name = "test-flow-run"
    flow_run.flow_id = uuid4()
    flow_run.deployment_id = deployment_id
    flow_run.tags = tags or []
    return flow_run


def _make_deployment(tags: list[str] | None = None) -> MagicMock:
    deployment = MagicMock(spec=DeploymentResponse)
    deployment.id = uuid4()
    deployment.name = "test-deployment"
    deployment.flow_id = uuid4()
    deployment.tags = tags or []
    from prefect.events.schemas.events import RelatedResource

    deployment.as_related_resource.return_value = RelatedResource(
        {
            "prefect.resource.id": f"prefect.deployment.{deployment.id}",
            "prefect.resource.role": "deployment",
            "prefect.resource.name": deployment.name,
        }
    )
    return deployment


def _make_flow() -> MagicMock:
    flow = MagicMock(spec=APIFlow)
    flow.id = uuid4()
    flow.name = "test-flow"
    return flow


class TestEventEmitterLifecycle:
    async def test_aenter_enters_events_client(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )

        async with emitter:
            assert emitter._events_client is asserting_client

    async def test_aexit_exits_events_client(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )

        async with emitter:
            pass

        assert emitter._events_client is None

    async def test_emit_outside_context_raises(self):
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: AssertingEventsClient(),
        )
        flow_run = _make_flow_run()

        with pytest.raises(AssertionError):
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=None
            )


class TestEventEmitterEmitFlowRunCancelled:
    async def test_emits_cancelled_event(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        flow_run = _make_flow_run()

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=None
            )

        assert len(asserting_client.events) == 1
        assert asserting_client.events[0].event == "prefect.runner.cancelled-flow-run"

    async def test_related_resources_order_with_all_present(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment(tags=["a"])
        flow = _make_flow()
        flow_run = _make_flow_run(deployment_id=deployment.id, tags=["b"])

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=flow, deployment=deployment
            )

        event = asserting_client.events[0]
        related = event.related
        non_tag = [r for r in related if r.root.get("prefect.resource.role") != "tag"]
        assert non_tag[0].root["prefect.resource.role"] == "deployment"
        assert non_tag[1].root["prefect.resource.role"] == "flow"
        assert non_tag[2].root["prefect.resource.role"] == "flow-run"

    async def test_related_resources_deployment_role(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment()
        flow_run = _make_flow_run(deployment_id=deployment.id)

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=deployment
            )

        event = asserting_client.events[0]
        assert event.related[0].root["prefect.resource.role"] == "deployment"

    async def test_related_resources_flow_role(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment()
        flow = _make_flow()
        flow_run = _make_flow_run(deployment_id=deployment.id)

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=flow, deployment=deployment
            )

        event = asserting_client.events[0]
        assert event.related[1].root["prefect.resource.role"] == "flow"

    async def test_related_resources_flow_run_role(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment()
        flow = _make_flow()
        flow_run = _make_flow_run(deployment_id=deployment.id)

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=flow, deployment=deployment
            )

        event = asserting_client.events[0]
        non_tag = [
            r for r in event.related if r.root.get("prefect.resource.role") != "tag"
        ]
        assert non_tag[-1].root["prefect.resource.role"] == "flow-run"

    async def test_tags_combined_from_deployment_and_flow_run(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment(tags=["a", "c"])
        flow_run = _make_flow_run(deployment_id=deployment.id, tags=["b", "c"])

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=deployment
            )

        event = asserting_client.events[0]
        tag_resources = [
            r for r in event.related if r.root.get("prefect.resource.role") == "tag"
        ]
        tag_ids = {r.root["prefect.resource.id"] for r in tag_resources}
        assert tag_ids == {
            "prefect.tag.a",
            "prefect.tag.b",
            "prefect.tag.c",
        }

    async def test_tags_sorted_alphabetically(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment(tags=["z", "a"])
        flow_run = _make_flow_run(deployment_id=deployment.id, tags=["m"])

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=deployment
            )

        event = asserting_client.events[0]
        tag_resources = [
            r for r in event.related if r.root.get("prefect.resource.role") == "tag"
        ]
        tag_ids = [r.root["prefect.resource.id"] for r in tag_resources]
        assert tag_ids == ["prefect.tag.a", "prefect.tag.m", "prefect.tag.z"]

    async def test_emit_without_deployment(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        flow = _make_flow()
        flow_run = _make_flow_run(tags=["x"])

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=flow, deployment=None
            )

        event = asserting_client.events[0]
        roles = [r.root.get("prefect.resource.role") for r in event.related]
        assert "deployment" not in roles
        tag_ids = {
            r.root["prefect.resource.id"]
            for r in event.related
            if r.root.get("prefect.resource.role") == "tag"
        }
        assert tag_ids == {"prefect.tag.x"}

    async def test_emit_without_flow(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        deployment = _make_deployment()
        flow_run = _make_flow_run(deployment_id=deployment.id)

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=deployment
            )

        event = asserting_client.events[0]
        roles = [r.root.get("prefect.resource.role") for r in event.related]
        assert "flow" not in roles
        assert "flow-run" in roles

    async def test_emit_without_flow_and_deployment(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="test-runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        flow_run = _make_flow_run(tags=["only-tag"])

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=None
            )

        event = asserting_client.events[0]
        non_tag = [
            r for r in event.related if r.root.get("prefect.resource.role") != "tag"
        ]
        assert len(non_tag) == 1
        assert non_tag[0].root["prefect.resource.role"] == "flow-run"
        tag_resources = [
            r for r in event.related if r.root.get("prefect.resource.role") == "tag"
        ]
        assert len(tag_resources) == 1
        assert tag_resources[0].root["prefect.resource.id"] == "prefect.tag.only-tag"

    async def test_event_resource_contains_runner_name(self):
        asserting_client = AssertingEventsClient()
        emitter = _EventEmitter(
            runner_name="My Test Runner",
            client=AsyncMock(),
            get_events_client=lambda: asserting_client,
        )
        flow_run = _make_flow_run()

        async with emitter:
            await emitter.emit_flow_run_cancelled(
                flow_run=flow_run, flow=None, deployment=None
            )

        event = asserting_client.events[0]
        assert "my-test-runner" in event.resource["prefect.resource.id"]


class TestEventEmitterGetFlowAndDeployment:
    async def test_cache_hit_skips_api(self):
        client = AsyncMock()
        deployment = _make_deployment()
        flow = _make_flow()
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)

        emitter = _EventEmitter(
            runner_name="test-runner",
            client=client,
            get_events_client=lambda: AssertingEventsClient(),
        )
        emitter._cache[f"deployment:{deployment_id}"] = deployment
        emitter._cache[f"flow:{deployment_id}"] = flow

        result_flow, result_deployment = await emitter.get_flow_and_deployment(flow_run)

        assert result_flow is flow
        assert result_deployment is deployment
        client.read_deployment.assert_not_awaited()
        client.read_flow.assert_not_awaited()

    async def test_cache_miss_calls_api(self):
        client = AsyncMock()
        deployment = _make_deployment()
        flow = _make_flow()
        client.read_deployment.return_value = deployment
        client.read_flow.return_value = flow
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)

        emitter = _EventEmitter(
            runner_name="test-runner",
            client=client,
            get_events_client=lambda: AssertingEventsClient(),
        )

        result_flow, result_deployment = await emitter.get_flow_and_deployment(flow_run)

        assert result_flow is flow
        assert result_deployment is deployment
        client.read_deployment.assert_awaited_once_with(deployment_id)
        client.read_flow.assert_awaited_once_with(deployment.flow_id)
        assert emitter._cache[f"deployment:{deployment_id}"] is deployment
        assert emitter._cache[f"flow:{deployment_id}"] is flow

    async def test_cache_expired_api_failure_uses_stale_and_warns(self, caplog):
        client = AsyncMock()
        deployment = _make_deployment()
        flow = _make_flow()
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)

        emitter = _EventEmitter(
            runner_name="test-runner",
            client=client,
            get_events_client=lambda: AssertingEventsClient(),
            cache_ttl=0.01,
        )
        emitter._cache[f"deployment:{deployment_id}"] = deployment
        emitter._cache[f"flow:{deployment_id}"] = flow

        await asyncio.sleep(0.02)

        client.read_deployment.side_effect = RuntimeError("API down")

        with caplog.at_level(logging.WARNING, logger="prefect.runner.event_emitter"):
            result_flow, result_deployment = await emitter.get_flow_and_deployment(
                flow_run
            )

        assert result_flow is None
        assert result_deployment is None

    async def test_cache_key_composite(self):
        client = AsyncMock()
        deployment = _make_deployment()
        flow = _make_flow()
        client.read_deployment.return_value = deployment
        client.read_flow.return_value = flow
        deployment_id = uuid4()
        flow_run = _make_flow_run(deployment_id=deployment_id)

        emitter = _EventEmitter(
            runner_name="test-runner",
            client=client,
            get_events_client=lambda: AssertingEventsClient(),
        )

        await emitter.get_flow_and_deployment(flow_run)

        assert f"deployment:{deployment_id}" in emitter._cache
        assert f"flow:{deployment_id}" in emitter._cache
        assert str(deployment_id) not in emitter._cache

    async def test_no_deployment_id_returns_none_none(self):
        client = AsyncMock()
        flow_run = _make_flow_run(deployment_id=None)

        emitter = _EventEmitter(
            runner_name="test-runner",
            client=client,
            get_events_client=lambda: AssertingEventsClient(),
        )

        result_flow, result_deployment = await emitter.get_flow_and_deployment(flow_run)

        assert result_flow is None
        assert result_deployment is None
        client.read_deployment.assert_not_awaited()
        client.read_flow.assert_not_awaited()
