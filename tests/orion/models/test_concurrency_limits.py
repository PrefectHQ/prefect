import time
from uuid import uuid4

from prefect.orion import models, schemas


class TestCreatingConcurrencyLimits:
    async def test_creating_concurrency_limits(self, session):
        concurrency_limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="this bad boy", concurrency_limit=100
            ),
        )
        assert concurrency_limit.tag == "this bad boy"
        assert concurrency_limit.concurrency_limit == 100

    async def test_create_concurrency_limit_updates_on_conflict(self, session):
        concurrency_limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="fits this many concurrent runs", concurrency_limit=100
            ),
        )

        assert concurrency_limit.tag == "fits this many concurrent runs"
        assert concurrency_limit.concurrency_limit == 100
        creation_time = concurrency_limit.updated

        time.sleep(0.1)

        updated_limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="fits this many concurrent runs", concurrency_limit=200
            ),
        )

        assert updated_limit.tag == "fits this many concurrent runs"
        assert updated_limit.concurrency_limit == 200
        assert updated_limit.updated > creation_time


class TestReadingSingleConcurrencyLimits:
    async def test_reading_concurrency_limits_by_id(self, session):
        concurrency_limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="hide and seek", concurrency_limit=4242
            ),
        )

        cl_id = concurrency_limit.id

        fetched_limit = await models.concurrency_limits.read_concurrency_limit(
            session, cl_id
        )

        assert fetched_limit.tag == "hide and seek"
        assert fetched_limit.concurrency_limit == 4242

    async def test_reading_concurrency_limits_returns_none_if_missing(self, session):
        fetched_limit = await models.concurrency_limits.read_concurrency_limit(
            session, str(uuid4())
        )

        assert fetched_limit is None

    async def test_reading_concurrency_limits_by_tag(self, session):
        concurrency_limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="a searchable tag", concurrency_limit=424242
            ),
        )

        fetched_limit = await models.concurrency_limits.read_concurrency_limit_by_tag(
            session, "a searchable tag"
        )

        assert fetched_limit.tag == "a searchable tag"
        assert fetched_limit.concurrency_limit == 424242

    async def test_reading_concurrency_limits_by_tag_returns_none_if_missing(
        self, session
    ):
        fetched_limit = await models.concurrency_limits.read_concurrency_limit_by_tag(
            session, "a nonexistent tag"
        )

        assert fetched_limit is None


class TestReadingMultipleConcurrencyLimits:
    async def test_reading_concurrency_limits(self, session):
        cl_data = {"tag 1": 42, "tag 2": 4242, "tag 3": 424242}
        for tag, limit in cl_data.items():
            await models.concurrency_limits.create_concurrency_limit(
                session=session,
                concurrency_limit=schemas.core.ConcurrencyLimit(
                    tag=tag, concurrency_limit=limit
                ),
            )

        limits = await models.concurrency_limits.read_concurrency_limits(session)
        assert len(limits) == 3

        for cl in limits:
            assert cl.concurrency_limit == cl_data[cl.tag]

    async def test_filtering_concurrency_limits_for_orchestration(self, session):
        cl_data = {"tag 1": 42, "tag 2": 4242, "tag 3": 424242}
        for tag, limit in cl_data.items():
            await models.concurrency_limits.create_concurrency_limit(
                session=session,
                concurrency_limit=schemas.core.ConcurrencyLimit(
                    tag=tag, concurrency_limit=limit
                ),
            )

        limits = (
            await models.concurrency_limits.filter_concurrency_limits_for_orchestration(
                session, ["tag 1", "tag 2", "tag 4"]
            )
        )
        assert len(limits) == 2
        for cl in limits:
            assert cl.concurrency_limit == cl_data[cl.tag]
