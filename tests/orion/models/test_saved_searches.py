from uuid import uuid4

import pytest

from prefect.orion import models, schemas
from prefect.orion.schemas import filters


class TestCreateSavedSearch:
    async def test_create_saved_search_succeeds(self, session):
        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch",
            ),
        )
        assert saved_search.name == "My SavedSearch"

    async def test_create_saved_search_updates_existing_saved_search(
        self,
        session,
    ):
        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch",
                flow_filter_criteria=dict(
                    flow_filter=filters.FlowFilter(
                        id=filters.FlowFilterId(any_=[uuid4()])
                    )
                ),
            ),
        )
        assert saved_search.name == "My SavedSearch"
        assert saved_search.flow_filter_criteria.flow_filter.id.any_

        saved_search = await models.saved_searches.create_saved_search(
            session=session,
            saved_search=schemas.core.SavedSearch(
                name="My SavedSearch",
            ),
        )
        assert saved_search.name == "My SavedSearch"
        # should be removed
        assert not saved_search.flow_filter_criteria.flow_filter.id


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


class TestReadSavedSearchs:
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
