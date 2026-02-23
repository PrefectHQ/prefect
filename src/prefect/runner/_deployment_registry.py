from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from cachetools import LRUCache

from prefect.logging import get_logger

if TYPE_CHECKING:
    from prefect.client.schemas.objects import Flow as APIFlow
    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.flows import Flow
    from prefect.runner.storage import RunnerStorage

logger = get_logger("runner.deployment_registry")


class DeploymentRegistry:
    """Pure synchronous data store for deployment-related data structures.

    Extracts five deployment-related data structures from `Runner` into a
    standalone registry with typed accessor methods and LRU caching.
    """

    def __init__(self) -> None:
        self._deployment_ids: set[UUID] = set()
        self._deployment_flow_map: dict[UUID, Flow[Any, Any]] = {}
        self._deployment_storage_map: dict[UUID, RunnerStorage] = {}
        self._deployment_cache: LRUCache[UUID, DeploymentResponse] = LRUCache(
            maxsize=100
        )
        self._flow_cache: LRUCache[UUID, APIFlow] = LRUCache(maxsize=100)

    def register_deployment(self, deployment_id: UUID) -> None:
        """Register a deployment ID."""
        self._deployment_ids.add(deployment_id)

    def get_deployment_ids(self) -> set[UUID]:
        """Return a copy of the registered deployment IDs."""
        return set(self._deployment_ids)

    def register_flow(self, deployment_id: UUID, flow: Flow[Any, Any]) -> None:
        """Associate a flow with a deployment ID."""
        self._deployment_flow_map[deployment_id] = flow

    def get_flow(self, deployment_id: UUID) -> Flow[Any, Any] | None:
        """Return the flow for a deployment ID, or `None` if not found."""
        return self._deployment_flow_map.get(deployment_id)

    def register_storage(self, deployment_id: UUID, storage: RunnerStorage) -> None:
        """Associate storage with a deployment ID."""
        self._deployment_storage_map[deployment_id] = storage

    def get_storage(self, deployment_id: UUID) -> RunnerStorage | None:
        """Return the storage for a deployment ID, or `None` if not found."""
        return self._deployment_storage_map.get(deployment_id)

    def cache_deployment(
        self, deployment_id: UUID, deployment: DeploymentResponse
    ) -> None:
        """Cache a deployment response by deployment ID."""
        self._deployment_cache[deployment_id] = deployment

    def get_cached_deployment(self, deployment_id: UUID) -> DeploymentResponse | None:
        """Return a cached deployment response, or `None` if not cached."""
        return self._deployment_cache.get(deployment_id)

    def cache_flow(self, flow_id: UUID, flow: APIFlow) -> None:
        """Cache an API flow object by flow ID."""
        self._flow_cache[flow_id] = flow

    def get_cached_flow(self, flow_id: UUID) -> APIFlow | None:
        """Return a cached API flow object, or `None` if not cached."""
        return self._flow_cache.get(flow_id)
