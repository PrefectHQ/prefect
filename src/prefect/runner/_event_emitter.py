from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from cachetools import TTLCache

from prefect.events.related import tags_as_related_resources
from prefect.events.schemas.events import Event, RelatedResource, Resource
from prefect.logging import get_logger
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import Flow as APIFlow
    from prefect.client.schemas.objects import FlowRun
    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.events.clients import EventsClient


def _default_get_events_client() -> "EventsClient":
    from prefect.events.clients import get_events_client

    return get_events_client(checkpoint_every=1)


class EventEmitter:
    """Owns EventsClient lifecycle, TTL-based deployment/flow cache, and event emission.

    Lifecycle-owning service -- implements `__aenter__`/`__aexit__`.
    Dependencies injected via keyword-only constructor arguments.
    """

    def __init__(
        self,
        *,
        runner_name: str,
        client: "PrefectClient",
        get_events_client: "Callable[[], EventsClient]" = _default_get_events_client,
        cache_ttl: float = 300.0,
    ) -> None:
        self._runner_name = runner_name
        self._client = client
        self._get_events_client = get_events_client
        self._cache_ttl = cache_ttl
        self._logger = get_logger("runner.event_emitter")
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=200, ttl=cache_ttl)
        self._events_client: "EventsClient | None" = None

    async def __aenter__(self) -> "EventEmitter":
        self._events_client = self._get_events_client()
        await self._events_client.__aenter__()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._events_client is not None:
            await self._events_client.__aexit__(*exc_info)
            self._events_client = None

    def _event_resource(self) -> dict[str, str]:
        from prefect import __version__

        return {
            "prefect.resource.id": f"prefect.runner.{slugify(self._runner_name)}",
            "prefect.resource.name": self._runner_name,
            "prefect.version": __version__,
        }

    async def get_flow_and_deployment(
        self, flow_run: "FlowRun"
    ) -> "tuple[APIFlow | None, DeploymentResponse | None]":
        """Resolve and cache deployment + flow for a flow run.

        Uses TTLCache with composite keys. On API failure, logs WARNING and
        returns (None, None). Returns (None, None) if `flow_run` has no `deployment_id`.
        """
        if not flow_run.deployment_id:
            return None, None

        deployment_key = f"deployment:{flow_run.deployment_id}"
        flow_key = f"flow:{flow_run.flow_id}"

        cached_deployment = self._cache.get(deployment_key)
        cached_flow = self._cache.get(flow_key)
        if cached_deployment is not None and cached_flow is not None:
            return cached_flow, cached_deployment

        try:
            deployment = await self._client.read_deployment(flow_run.deployment_id)
            flow = await self._client.read_flow(deployment.flow_id)
            self._cache[deployment_key] = deployment
            self._cache[f"flow:{flow_run.flow_id}"] = flow
            return flow, deployment
        except Exception:
            self._logger.warning(
                "Failed to fetch deployment/flow for flow run '%s';"
                " emitting event without deployment/flow context.",
                flow_run.id,
                exc_info=True,
            )
            return None, None

    async def emit_flow_run_cancelled(
        self,
        flow_run: "FlowRun",
        flow: "APIFlow | None",
        deployment: "DeploymentResponse | None",
    ) -> None:
        """Emit the cancelled-flow-run event.

        Receives (flow_run, flow, deployment) per-call to construct related resources
        and tags.
        """
        related: list[RelatedResource] = []
        tags: list[str] = []

        if deployment is not None:
            related.append(deployment.as_related_resource())
            tags.extend(deployment.tags)

        if flow is not None:
            related.append(
                RelatedResource(
                    {
                        "prefect.resource.id": f"prefect.flow.{flow.id}",
                        "prefect.resource.role": "flow",
                        "prefect.resource.name": flow.name,
                    }
                )
            )

        related.append(
            RelatedResource(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": flow_run.name,
                }
            )
        )
        tags.extend(flow_run.tags)

        related = [RelatedResource.model_validate(r) for r in related]
        related += tags_as_related_resources(set(tags))

        assert self._events_client is not None, (
            "EventEmitter must be used as an async context manager before emitting events"
        )
        await self._events_client.emit(
            Event(
                event="prefect.runner.cancelled-flow-run",
                resource=Resource(self._event_resource()),
                related=related,
            )
        )
        self._logger.debug(
            "Emitted cancelled-flow-run event for flow run '%s'", flow_run.id
        )
