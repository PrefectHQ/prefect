from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from uuid import UUID

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow


def make_flow_resolver(
    bundle_map: dict[UUID, Any],
    deployment_flow_map: dict[UUID, Flow[Any, Any]],
    tmp_dir: Path,
    load_flow_from_flow_run: Callable[..., Awaitable[Flow[Any, Any]]],
    extract_flow_from_bundle: Callable[[Any], Flow[Any, Any]],
) -> Callable[[FlowRun], Awaitable[Flow[Any, Any]]]:
    """Return a callable that resolves the `Flow` object for a given `FlowRun`.

    Lookup order: `bundle_map` -> `deployment_flow_map` -> API (`load_flow_from_flow_run`).
    Caches successful resolutions for the closure lifetime (session scope).
    Raises `ValueError` for total miss (no `deployment_id`, not in either map).
    Propagates API exceptions as-is (not wrapped).
    """
    _session_cache: dict[UUID, Flow[Any, Any]] = {}

    async def resolve_flow(flow_run: FlowRun) -> Flow[Any, Any]:
        if flow_run.id in _session_cache:
            return _session_cache[flow_run.id]

        if flow_run.id in bundle_map:
            flow = extract_flow_from_bundle(bundle_map[flow_run.id])
            _session_cache[flow_run.id] = flow
            return flow

        if flow_run.deployment_id and deployment_flow_map.get(flow_run.deployment_id):
            flow = deployment_flow_map[flow_run.deployment_id]
            _session_cache[flow_run.id] = flow
            return flow

        if not flow_run.deployment_id:
            raise ValueError(
                f"Cannot resolve flow for flow run '{flow_run.id}': no deployment_id"
                " and flow run not found in bundle map or deployment flow map."
            )

        flow = await load_flow_from_flow_run(flow_run, storage_base_path=str(tmp_dir))
        _session_cache[flow_run.id] = flow
        return flow

    return resolve_flow
