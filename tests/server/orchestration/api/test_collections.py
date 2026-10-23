from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, AsyncGenerator, Callable

import pytest
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from prefect.client.base import app_lifespan_context
from prefect.server.api import collections

pytestmark = pytest.mark.clear_db


class TestReadCollectionViews:
    def collection_view_url(self, view):
        return (
            "https://raw.githubusercontent.com/"
            "PrefectHQ/prefect-collection-registry/main/"
            f"views/aggregate-{view}-metadata.json"
        )

    @pytest.fixture
    def mock_flow_response(self):
        return {
            "collection-name": {
                "flow-name": {
                    "name": "flow-name",
                },
            }
        }

    @pytest.fixture
    def mock_block_response(self):
        return {
            "collection-name": {
                "block_types": {
                    "block-name": {
                        "name": "block-name",
                    },
                },
            }
        }

    @pytest.fixture
    def mock_collection_response(self):
        return {
            "collection-name": {
                "name": "collection-name",
            },
        }

    @pytest.fixture
    def mock_worker_response(self):
        return {
            "prefect": {
                "prefect-agent": {},
                "process": {},
            }
        }

    @pytest.fixture
    def mock_get_view(
        self,
        mock_flow_response,
        mock_block_response,
        mock_worker_response,
    ):
        with respx.mock(
            using="httpx", assert_all_mocked=False, assert_all_called=False
        ) as respx_mock:
            flow_route = respx_mock.get(self.collection_view_url("flow")).mock(
                return_value=Response(200, json=mock_flow_response)
            )
            block_route = respx_mock.get(self.collection_view_url("block")).mock(
                return_value=Response(200, json=mock_block_response)
            )
            worker_route = respx_mock.get(self.collection_view_url("worker")).mock(
                return_value=Response(200, json=mock_worker_response)
            )
            respx_mock.route(host="test").pass_through()

            yield respx_mock, flow_route, block_route, worker_route

    @pytest.fixture
    def mock_get_missing_view(
        self,
        mock_flow_response,
        mock_block_response,
        mock_collection_response,
    ):
        with respx.mock(
            using="httpx",
            assert_all_mocked=False,
            assert_all_called=False,
            base_url="https://raw.githubusercontent.com",
        ) as respx_mock:
            respx_mock.get(self.collection_view_url("flow")).mock(
                return_value=Response(404, json=mock_flow_response)
            )
            respx_mock.get(self.collection_view_url("block")).mock(
                return_value=Response(404, json=mock_block_response)
            )
            respx_mock.get(self.collection_view_url("worker")).mock(
                return_value=Response(404, json=mock_collection_response)
            )
            respx_mock.route(host="test").pass_through()

            yield respx_mock

    @pytest.mark.parametrize(
        "view", ["aggregate-flow-metadata", "aggregate-block-metadata"]
    )
    async def test_read_view(self, client, view, mock_get_view):
        res = await client.get(f"/collections/views/{view}")

        assert res.status_code == 200
        assert isinstance(res.json(), dict)

    async def test_read_collection_view_when_missing(
        self, client, mock_get_missing_view
    ):
        res = await client.get("/collections/views/aggregate-flow-metadata")
        detail = res.json()["detail"]

        assert res.status_code == 404
        assert detail == "Requested content missing for view aggregate-flow-metadata"

    async def test_read_collection_view_invalid(self, client):
        res = await client.get("/collections/views/invalid")
        detail = res.json()["detail"]

        assert res.status_code == 404
        assert detail == "View invalid not found in registry"

    @pytest.mark.parametrize(
        "view", ["aggregate-flow-metadata", "aggregate-block-metadata"]
    )
    async def test_collection_view_cached(self, client, mock_get_view, view):
        respx_mock, flow_route, block_route, worker_route = mock_get_view
        res1 = await client.get(f"/collections/views/{view}")

        assert res1.status_code == 200
        assert isinstance(res1.json(), dict)

        res2 = await client.get(f"/collections/views/{view}")

        assert res2.status_code == 200
        assert isinstance(res2.json(), dict)

        assert res1.json() == res2.json()
        if view == "aggregate-flow-metadata":
            flow_route.calls.assert_called_once()
        elif view == "aggregate-block-metadata":
            block_route.calls.assert_called_once()

    async def test_read_worker_view_failed_fetch(self, client, mock_get_missing_view):
        res = await client.get("/collections/views/aggregate-worker-metadata")

        assert res.status_code == 200
        # check for expected key to ensure it isn't an error
        assert isinstance(res.json()["prefect"], dict)

    async def test_prefect_agent_excluded_from_worker_metadata(
        self, client, mock_get_view
    ):
        res = await client.get("/collections/views/aggregate-worker-metadata")

        assert res.status_code == 200
        assert "prefect-agent" not in res.json()["prefect"]

    @pytest.fixture
    def started_server(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> Callable[..., AbstractAsyncContextManager[AsyncClient]]:
        """Starts the server, running its lifespan, with the given builder of
        local worker metadata, and yields a client for its API."""

        @asynccontextmanager
        async def start(
            build: Callable[[], dict[str, Any]],
        ) -> AsyncGenerator[AsyncClient, None]:
            monkeypatch.setattr(
                collections, "get_locally_installed_worker_metadata", build
            )
            async with app_lifespan_context(app):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="https://test/api"
                ) as client:
                    yield client

        return start

    async def test_locally_installed_workers_added_to_worker_metadata(
        self, started_server, mock_get_view
    ):
        """Workers installed alongside the server but absent from the registry
        (an unreleased or private collection) are still offered to the UI."""
        local_metadata = {
            "prefect-armada": {
                "armada": {
                    "type": "armada",
                    "display_name": "Armada",
                    "description": "Execute flow runs within Armada jobs.",
                    "logo_url": "",
                    "documentation_url": "",
                    "install_command": "pip install prefect-armada",
                    "default_base_job_configuration": {},
                    "is_beta": False,
                }
            }
        }

        async with started_server(lambda: local_metadata) as client:
            res = await client.get("/collections/views/aggregate-worker-metadata")

        assert res.status_code == 200
        assert res.json()["prefect-armada"]["armada"]["display_name"] == "Armada"

    async def test_registry_worker_metadata_wins_over_local(
        self, started_server, mock_get_view
    ):
        local_metadata = {"prefect": {"process": {"type": "process", "local": True}}}

        async with started_server(lambda: local_metadata) as client:
            res = await client.get("/collections/views/aggregate-worker-metadata")

        assert res.status_code == 200
        assert res.json()["prefect"]["process"] == {}

    async def test_local_worker_metadata_is_built_once_at_startup(
        self, started_server, mock_get_view
    ):
        """
        Building it imports every installed integration, which must not happen
        while serving requests, and installed packages do not change while the
        server runs.
        """
        builds = 0

        def build():
            nonlocal builds
            builds += 1
            return {"prefect-armada": {"armada": {"type": "armada"}}}

        async with started_server(build) as client:
            assert builds == 1
            for _ in range(2):
                res = await client.get("/collections/views/aggregate-worker-metadata")
                assert res.json()["prefect-armada"]["armada"] == {"type": "armada"}
                # The registry view's cache expires, unlike the local metadata
                collections.GLOBAL_COLLECTIONS_VIEW_CACHE.clear()

        assert builds == 1

    async def test_cached_views_do_not_share_the_local_worker_metadata(
        self, started_server, mock_get_view
    ):
        """The metadata built at startup outlives every cached view, so a change
        to one view must not reach it, or any later view."""
        local_metadata = {"prefect-armada": {"armada": {"type": "armada"}}}

        async with started_server(lambda: local_metadata) as client:
            view = await collections.get_collection_view(
                "aggregate-worker-metadata", local_worker_metadata=local_metadata
            )
            view["prefect-armada"]["armada"]["type"] = "changed"
            collections.GLOBAL_COLLECTIONS_VIEW_CACHE.clear()

            res = await client.get("/collections/views/aggregate-worker-metadata")

        assert local_metadata == {"prefect-armada": {"armada": {"type": "armada"}}}
        assert res.json()["prefect-armada"]["armada"] == {"type": "armada"}

    async def test_registry_view_is_cached_without_local_workers(self, mock_get_view):
        """The view cache is shared by every app in the process, so the workers
        installed alongside one app must not be served by another."""
        _, _, _, worker_route = mock_get_view
        local_metadata = {"prefect-armada": {"armada": {"type": "armada"}}}

        with_local = await collections.get_collection_view(
            "aggregate-worker-metadata", local_worker_metadata=local_metadata
        )
        without_local = await collections.get_collection_view(
            "aggregate-worker-metadata"
        )

        assert with_local["prefect-armada"]["armada"] == {"type": "armada"}
        assert without_local == {"prefect": {"process": {}}}
        worker_route.calls.assert_called_once()

    async def test_local_workers_merged_into_a_registry_collection(self, mock_get_view):
        """A local worker from a collection the registry already lists is added
        to the served view, not to the cached one."""
        local_metadata = {"prefect": {"local": {"type": "local"}}}

        with_local = await collections.get_collection_view(
            "aggregate-worker-metadata", local_worker_metadata=local_metadata
        )
        without_local = await collections.get_collection_view(
            "aggregate-worker-metadata"
        )

        assert with_local["prefect"] == {"process": {}, "local": {"type": "local"}}
        assert without_local["prefect"] == {"process": {}}

    async def test_malformed_registry_collection_does_not_fail_the_view(self):
        """A registry entry that is not a collection of workers is left as it
        is, and the other local workers are still merged."""
        registry_view = {"prefect": {"process": {}}, "prefect-armada": None}
        local_metadata = {
            "prefect-armada": {"armada": {"type": "armada"}},
            "prefect-other": {"other": {"type": "other"}},
        }

        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(self.collection_view_url("worker")).mock(
                return_value=Response(200, json=registry_view)
            )
            view = await collections.get_collection_view(
                "aggregate-worker-metadata", local_worker_metadata=local_metadata
            )

        assert view["prefect-armada"] is None
        assert view["prefect-other"] == {"other": {"type": "other"}}

    async def test_worker_metadata_survives_local_registry_failure(
        self, started_server, mock_get_view, caplog
    ):
        def boom():
            raise RuntimeError("could not load collections")

        async with started_server(boom) as client:
            res = await client.get("/collections/views/aggregate-worker-metadata")

        assert res.status_code == 200
        assert list(res.json()) == ["prefect"]
        assert "Unable to read worker metadata" in caplog.text

    async def test_worker_metadata_without_a_server_lifespan(
        self, client, mock_get_view
    ):
        """An app served without its lifespan has no local worker metadata, and
        serves the registry's workers alone."""
        res = await client.get("/collections/views/aggregate-worker-metadata")

        assert res.status_code == 200
        assert res.json() == {"prefect": {"process": {}}}
