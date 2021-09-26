from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import SavedSearchCreate
from prefect.orion.schemas.data import DataDocument


class TestCreateSavedSearch:
    async def test_create_saved_search(
        self,
        session,
        client,
    ):

        data = SavedSearchCreate(name="My SavedSearch", filter_obj="FLOW").dict(
            json_compatible=True
        )
        response = await client.put("/saved_searches/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My SavedSearch"
        saved_search_id = response.json()["id"]

        saved_search = await models.saved_searches.read_saved_search(
            session=session, saved_search_id=saved_search_id
        )
        assert str(saved_search.id) == saved_search_id
        assert saved_search.name == "My SavedSearch"
        assert saved_search.filter_obj.value == "FLOW"

    async def test_create_saved_search_respects_name_uniqueness(self, client):
        data = SavedSearchCreate(name="My SavedSearch", filter_obj="FLOW").dict(
            json_compatible=True
        )
        response = await client.put("/saved_searches/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My SavedSearch"
        assert response.json()["filter_obj"] == "FLOW"
        saved_search_id = response.json()["id"]

        # post different data, upsert should be respected
        data = SavedSearchCreate(name="My SavedSearch", filter_obj="FLOW_RUN").dict(
            json_compatible=True
        )
        response = await client.put("/saved_searches/", json=data)
        assert response.status_code == 200
        assert response.json()["name"] == "My SavedSearch"
        assert response.json()["filter_obj"] == "FLOW_RUN"
        assert response.json()["id"] == saved_search_id

    async def test_create_saved_search_populates_and_returned_created(
        self,
        client,
    ):
        now = pendulum.now(tz="UTC")

        data = SavedSearchCreate(name="My SavedSearch", filter_obj="TASK_RUN").dict(
            json_compatible=True
        )
        response = await client.put("/saved_searches/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My SavedSearch"
        assert pendulum.parse(response.json()["created"]) >= now
        assert pendulum.parse(response.json()["updated"]) >= now


class TestReadSavedSearch:
    async def test_read_saved_search(self, client):

        # first create a saved_search to read
        data = SavedSearchCreate(name="My SavedSearch", filter_obj="FLOW").dict(
            json_compatible=True
        )
        response = await client.put("/saved_searches/", json=data)
        saved_search_id = response.json()["id"]

        # make sure we we can read the saved_search correctly
        response = await client.get(f"/saved_searches/{saved_search_id}")
        assert response.status_code == 200
        assert response.json()["id"] == saved_search_id
        assert response.json()["name"] == "My SavedSearch"
        assert response.json()["filter_obj"] == "FLOW"

    async def test_read_saved_search_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/saved_searches/{uuid4()}")
        assert response.status_code == 404


class TestReadSavedSearchs:
    @pytest.fixture
    async def saved_searches(self, session, flow, flow_function):
        await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch X", filter_obj="FLOW"
            ),
        )

        await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch Y", filter_obj="DEPLOYMENT"
            ),
        )
        await session.commit()

    async def test_read_saved_searches(self, saved_searches, client):
        response = await client.post("/saved_searches/filter/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_saved_searches_applies_limit(self, saved_searches, client):
        response = await client.post("/saved_searches/filter/", json=dict(limit=1))
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_saved_searches_offset(self, saved_searches, client, session):
        response = await client.post("/saved_searches/filter/", json=dict(offset=1))
        assert response.status_code == 200
        assert len(response.json()) == 1
        # ordered by name by default
        assert response.json()[0]["name"] == "My SavedSearch Y"

    async def test_read_saved_searches_returns_empty_list(self, client):
        response = await client.post("/saved_searches/filter/")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteSavedSearch:
    async def test_delete_saved_search(self, client):
        # first create a saved_search to delete
        data = SavedSearchCreate(name="My SavedSearch", filter_obj="FLOW").dict(
            json_compatible=True
        )
        response = await client.put("/saved_searches/", json=data)
        saved_search_id = response.json()["id"]

        # delete the saved_search
        response = await client.delete(f"/saved_searches/{saved_search_id}")
        assert response.status_code == 204

        # make sure it's deleted
        response = await client.get(f"/saved_searches/{saved_search_id}")
        assert response.status_code == 404

    async def test_delete_saved_search_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/saved_searches/{uuid4()}")
        assert response.status_code == 404
