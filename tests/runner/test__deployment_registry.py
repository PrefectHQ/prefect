from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from prefect.runner._deployment_registry import _DeploymentRegistry


class TestDeploymentRegistryIDs:
    def test_register_deployment_adds_to_set(self):
        registry = _DeploymentRegistry()
        dep_id = uuid4()
        registry.register_deployment(dep_id)
        assert dep_id in registry.get_deployment_ids()

    def test_get_deployment_ids_returns_copy(self):
        registry = _DeploymentRegistry()
        dep_id = uuid4()
        registry.register_deployment(dep_id)
        result = registry.get_deployment_ids()
        result.add(uuid4())
        assert len(registry.get_deployment_ids()) == 1

    def test_get_deployment_ids_returns_empty_set_on_fresh_registry(self):
        registry = _DeploymentRegistry()
        assert registry.get_deployment_ids() == set()

    def test_multiple_deployments_registered_independently(self):
        registry = _DeploymentRegistry()
        id1 = uuid4()
        id2 = uuid4()
        id3 = uuid4()
        registry.register_deployment(id1)
        registry.register_deployment(id2)
        registry.register_deployment(id3)
        ids = registry.get_deployment_ids()
        assert ids == {id1, id2, id3}


class TestDeploymentRegistryFlows:
    def test_register_flow_and_get_flow_round_trip(self):
        registry = _DeploymentRegistry()
        dep_id = uuid4()
        flow = MagicMock()
        registry.register_flow(dep_id, flow)
        assert registry.get_flow(dep_id) is flow

    def test_get_flow_returns_none_for_unknown_uuid(self):
        registry = _DeploymentRegistry()
        assert registry.get_flow(uuid4()) is None


class TestDeploymentRegistryStorage:
    def test_register_storage_and_get_storage_round_trip(self):
        registry = _DeploymentRegistry()
        dep_id = uuid4()
        storage = MagicMock()
        registry.register_storage(dep_id, storage)
        assert registry.get_storage(dep_id) is storage

    def test_get_storage_returns_none_for_unknown_uuid(self):
        registry = _DeploymentRegistry()
        assert registry.get_storage(uuid4()) is None


class TestDeploymentRegistryCaches:
    def test_cache_deployment_and_get_cached_deployment_round_trip(self):
        registry = _DeploymentRegistry()
        dep_id = uuid4()
        deployment = MagicMock()
        registry.cache_deployment(dep_id, deployment)
        assert registry.get_cached_deployment(dep_id) is deployment

    def test_get_cached_deployment_returns_none_for_unknown_uuid(self):
        registry = _DeploymentRegistry()
        assert registry.get_cached_deployment(uuid4()) is None

    def test_cache_flow_and_get_cached_flow_round_trip(self):
        registry = _DeploymentRegistry()
        flow_id = uuid4()
        flow = MagicMock()
        registry.cache_flow(flow_id, flow)
        assert registry.get_cached_flow(flow_id) is flow

    def test_get_cached_flow_returns_none_for_unknown_uuid(self):
        registry = _DeploymentRegistry()
        assert registry.get_cached_flow(uuid4()) is None

    def test_deployment_cache_lru_eviction(self):
        registry = _DeploymentRegistry()
        registry._deployment_cache = __import__(
            "cachetools", fromlist=["LRUCache"]
        ).LRUCache(maxsize=2)
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        registry.cache_deployment(id1, MagicMock())
        registry.cache_deployment(id2, MagicMock())
        registry.cache_deployment(id3, MagicMock())
        assert registry.get_cached_deployment(id1) is None
        assert registry.get_cached_deployment(id2) is not None
        assert registry.get_cached_deployment(id3) is not None

    def test_flow_cache_lru_eviction(self):
        registry = _DeploymentRegistry()
        registry._flow_cache = __import__("cachetools", fromlist=["LRUCache"]).LRUCache(
            maxsize=2
        )
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        registry.cache_flow(id1, MagicMock())
        registry.cache_flow(id2, MagicMock())
        registry.cache_flow(id3, MagicMock())
        assert registry.get_cached_flow(id1) is None
        assert registry.get_cached_flow(id2) is not None
        assert registry.get_cached_flow(id3) is not None
