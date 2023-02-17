from uuid import uuid4

import pytest

from prefect.server import models, schemas


class TestCreateSavedSearch:
    async def test_create_saved_search_succeeds(self, session):
        filters = [
            {
                "object": "flow",
                "property": "name",
                "type": "string",
                "operation": "equals",
                "value": "foo",
            },
            {
                "object": "flow_run",
                "property": "name",
                "type": "string",
                "operation": "equals",
                "value": "bar",
            },
        ]
        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch", filters=filters
            ),
        )
        assert saved_search.name == "My SavedSearch"
        assert saved_search.filters == filters

    async def test_create_saved_search_updates_existing_saved_search(
        self,
        session,
    ):
        filters = [
            {
                "object": "flow",
                "property": "name",
                "type": "string",
                "operation": "equals",
                "value": "foo",
            },
            {
                "object": "flow_run",
                "property": "name",
                "type": "string",
                "operation": "equals",
                "value": "bar",
            },
        ]
        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch", filters=filters
            ),
        )
        assert saved_search.name == "My SavedSearch"
        assert saved_search.filters == filters

        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch",
            ),
        )
        assert saved_search.name == "My SavedSearch"
        # should be removed
        assert not saved_search.filters


class TestReadSavedSearch:
    async def test_read_saved_search_by_id(self, session):
        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch",
            ),
        )

        read_saved_search = await models.saved_searches.read_saved_search(
            session=session, saved_search_id=saved_search.id
        )
        assert read_saved_search.name == saved_search.name

    async def test_read_saved_search_by_id_returns_none_if_does_not_exist(
        self, session
    ):
        assert not await models.saved_searches.read_saved_search(
            session=session, saved_search_id=uuid4()
        )


class TestReadSavedSearches:
    @pytest.fixture
    async def saved_searches(self, session):
        saved_search_1 = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch 1",
            ),
        )
        saved_search_2 = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch 2",
            ),
        )
        await session.commit()
        return [saved_search_1, saved_search_2]

    async def test_read_saved_searches(self, saved_searches, session):
        read_saved_searches = await models.saved_searches.read_saved_searches(
            session=session
        )
        assert len(read_saved_searches) == len(saved_searches)

    async def test_read_saved_searches_applies_limit(self, saved_searches, session):
        read_saved_searches = await models.saved_searches.read_saved_searches(
            session=session, limit=1
        )
        assert {search.id for search in read_saved_searches} == {saved_searches[0].id}

    async def test_read_saved_searches_applies_offset(self, saved_searches, session):
        read_saved_searches = await models.saved_searches.read_saved_searches(
            session=session, offset=1
        )
        assert {search.id for search in read_saved_searches} == {saved_searches[1].id}

    async def test_read_saved_searches_returns_empty_list(self, session):
        read_saved_searches = await models.saved_searches.read_saved_searches(
            session=session
        )
        assert len(read_saved_searches) == 0


class TestDeleteSavedSearch:
    async def test_delete_saved_search(self, session):
        # create a saved_search to delete
        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch",
            ),
        )

        assert await models.saved_searches.delete_saved_search(
            session=session, saved_search_id=saved_search.id
        )

        # make sure the saved_search is deleted
        result = await models.saved_searches.read_saved_search(
            session=session, saved_search_id=saved_search.id
        )
        assert result is None

    async def test_delete_saved_search_returns_false_if_does_not_exist(self, session):
        result = await models.saved_searches.delete_saved_search(
            session=session, saved_search_id=str(uuid4())
        )
        assert result is False
