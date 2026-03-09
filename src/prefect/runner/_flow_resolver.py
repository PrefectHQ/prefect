from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from uuid import UUID

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow


class FlowResolver:
    """Resolves the `Flow` object for a given `FlowRun`.

    Lookup order: `bundle_map` -> `deployment_flow_map` -> API (`load_flow_from_flow_run`).
    Caches successful resolutions for the instance lifetime (session scope).
    Raises `ValueError` for total miss (no `deployment_id`, not in either map).
    Propagates API exceptions as-is (not wrapped).
    """

    def __init__(
        self,
        *,
        bundle_map: dict[UUID, Any],
        deployment_flow_map: dict[UUID, Flow[Any, Any]],
        tmp_dir: Path,
        load_flow_from_flow_run: Callable[..., Awaitable[Flow[Any, Any]]],
        extract_flow_from_bundle: Callable[[Any], Flow[Any, Any]],
    ) -> None:
        self._bundle_map = bundle_map
        self._deployment_flow_map = deployment_flow_map
        self._tmp_dir = tmp_dir
        self._load_flow_from_flow_run = load_flow_from_flow_run
        self._extract_flow_from_bundle = extract_flow_from_bundle
        self._session_cache: dict[UUID, Flow[Any, Any]] = {}

    async def resolve(self, flow_run: FlowRun) -> Flow[Any, Any]:
        """Resolve the `Flow` for the given `FlowRun`."""
        if flow_run.id in self._session_cache:
            return self._session_cache[flow_run.id]

        if flow_run.id in self._bundle_map:
            flow = self._extract_flow_from_bundle(self._bundle_map[flow_run.id])
            self._session_cache[flow_run.id] = flow
            return flow

        if flow_run.deployment_id and self._deployment_flow_map.get(
            flow_run.deployment_id
        ):
            flow = self._deployment_flow_map[flow_run.deployment_id]
            self._session_cache[flow_run.id] = flow
            return flow

        if not flow_run.deployment_id:
            raise ValueError(
                f"Cannot resolve flow for flow run '{flow_run.id}': no deployment_id"
                " and flow run not found in bundle map or deployment flow map."
            )

        flow = await self._load_flow_from_flow_run(
            flow_run, storage_base_path=str(self._tmp_dir)
        )
        self._session_cache[flow_run.id] = flow
        return flow
