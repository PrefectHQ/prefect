import pytest
import respx
from httpx import Response


@pytest.fixture(scope="function", autouse=True)
def reset_cache():
    from prefect.server.api.collections import GLOBAL_COLLECTIONS_VIEW_CACHE

    GLOBAL_COLLECTIONS_VIEW_CACHE.clear()


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

    @respx.mock
    @pytest.fixture
    def mock_get_view(
        self,
        respx_mock,
        mock_flow_response,
        mock_block_response,
        mock_collection_response,
    ):
        respx_mock.get(self.collection_view_url("flow")).mock(
            return_value=Response(200, json=mock_flow_response)
        )
        respx_mock.get(self.collection_view_url("block")).mock(
            return_value=Response(200, json=mock_block_response)
        )
        respx_mock.get(self.collection_view_url("collection")).mock(
            return_value=Response(404, json=mock_collection_response)
        )

        return respx_mock

    @pytest.mark.parametrize(
        "view", ["aggregate-flow-metadata", "aggregate-block-metadata"]
    )
    async def test_read_view(self, client, view, mock_get_view):
        res = await client.get(f"/collections/views/{view}")

        assert res.status_code == 200
        assert isinstance(res.json(), dict)

    async def test_read_collection_view_when_missing(self, client, mock_get_view):
        res = await client.get("/collections/views/aggregate-collection-metadata")
        detail = res.json()["detail"]

        assert res.status_code == 404
        assert (
            detail == "Requested content missing for view aggregate-collection-metadata"
        )

    async def test_read_collection_view_invalid(self, client):
        res = await client.get("/collections/views/invalid")
        detail = res.json()["detail"]

        assert res.status_code == 404
        assert detail == "Requested content missing for view invalid"

    @pytest.mark.parametrize(
        "view", ["aggregate-flow-metadata", "aggregate-block-metadata"]
    )
    async def test_collection_view_cached(self, client, mock_get_view, view):
        res1 = await client.get(f"/collections/views/{view}")

        assert res1.status_code == 200
        assert isinstance(res1.json(), dict)

        res2 = await client.get(f"/collections/views/{view}")

        assert res2.status_code == 200
        assert isinstance(res2.json(), dict)

        assert res1.json() == res2.json()
        mock_get_view.calls.assert_called_once()
