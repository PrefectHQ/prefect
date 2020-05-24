# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import pytest

import prefect
import prefect_server
from prefect.utilities.graphql import EnumValue, with_args
from prefect_server.database import hasura, models


# FIXME this will be in Prefect Core
def LiteralSetValue(value: list) -> str:
    return "{" + ", ".join(v for v in value) + "}"


@pytest.fixture(autouse=True)
async def flow_id():
    r"""
    1 -> 2 -> 3 -> 4 -> 5
            \              /
             7 -> 8 -> 9 -> 10
           /
        6
    """

    t1 = prefect.Task("t1", slug="t1")
    t2 = prefect.Task("t2", slug="t2")
    t3 = prefect.Task("t3", slug="t3")
    t4 = prefect.Task("t4", slug="t4")
    t5 = prefect.Task("t5", slug="t5")
    t6 = prefect.Task("t6", slug="t6")
    t7 = prefect.Task("t7", slug="t7")
    t8 = prefect.Task("t8", slug="t8")
    t9 = prefect.Task("t9", slug="t9")
    t10 = prefect.Task("t10", slug="t10")

    f = prefect.Flow("traversal flow")
    f.chain(t1, t2, t3, t4, t5)
    f.chain(t6, t7, t8, t9, t10)
    f.chain(t2, t7)
    f.chain(t9, t5)
    return await prefect_server.api.flows.create_flow(serialized_flow=f.serialize())


async def query_downstream(*ids,):
    return await hasura.HasuraClient().execute(
        {
            "query": {
                with_args(
                    "utility_downstream_tasks",
                    {
                        "args": {"start_task_ids": LiteralSetValue([*ids])},
                        "order_by": {
                            "depth": EnumValue("asc"),
                            "task": {"slug": EnumValue("asc")},
                        },
                    },
                ): {"task": {"slug"}, "depth": True}
            }
        }
    )


async def query_upstream(*ids,):
    return await hasura.HasuraClient().execute(
        {
            "query": {
                with_args(
                    "utility_upstream_tasks",
                    {
                        "args": {"start_task_ids": LiteralSetValue([*ids])},
                        "order_by": {
                            "depth": EnumValue("asc"),
                            "task": {"slug": EnumValue("asc")},
                        },
                    },
                ): {"task": {"slug"}, "depth": True}
            }
        }
    )


class TestDownstreamTraversal:
    async def test_traverse_downstream_from_t1(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t1"}}
        ).first({"id"})

        result = await query_downstream(task.id)

        assert result.data.utility_downstream_tasks == [
            {"task": {"slug": "t1"}, "depth": 0},
            {"task": {"slug": "t2"}, "depth": 1},
            {"task": {"slug": "t3"}, "depth": 2},
            {"task": {"slug": "t7"}, "depth": 2},
            {"task": {"slug": "t4"}, "depth": 3},
            {"task": {"slug": "t8"}, "depth": 3},
            {"task": {"slug": "t9"}, "depth": 4},
            {"task": {"slug": "t10"}, "depth": 5},
            {"task": {"slug": "t5"}, "depth": 5},
        ]

    async def test_traverse_downstream_with_limit(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t1"}}
        ).first({"id"})
        result = await hasura.HasuraClient().execute(
            {
                "query": {
                    with_args(
                        "utility_downstream_tasks",
                        {
                            "args": {
                                "start_task_ids": LiteralSetValue([task.id]),
                                "depth_limit": 2,
                            },
                            "order_by": {
                                "depth": EnumValue("asc"),
                                "task": {"slug": EnumValue("asc")},
                            },
                        },
                    ): {"task": {"slug"}, "depth": True}
                }
            }
        )

        assert result.data.utility_downstream_tasks == [
            {"task": {"slug": "t1"}, "depth": 0},
            {"task": {"slug": "t2"}, "depth": 1},
            {"task": {"slug": "t3"}, "depth": 2},
            {"task": {"slug": "t7"}, "depth": 2},
        ]

    async def test_traverse_downstream_with_where_clause(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t1"}}
        ).first({"id"})
        result = await hasura.HasuraClient().execute(
            {
                "query": {
                    with_args(
                        "utility_downstream_tasks",
                        {
                            "args": {"start_task_ids": LiteralSetValue([task.id])},
                            "order_by": {
                                "depth": EnumValue("asc"),
                                "task": {"slug": EnumValue("asc")},
                            },
                            "where": {
                                "task": {"slug": {"_neq": "t2"}},
                                "depth": {"_neq": 3},
                            },
                        },
                    ): {"task": {"slug"}, "depth": True}
                }
            }
        )

        assert result.data.utility_downstream_tasks == [
            {"task": {"slug": "t1"}, "depth": 0},
            {"task": {"slug": "t3"}, "depth": 2},
            {"task": {"slug": "t7"}, "depth": 2},
            {"task": {"slug": "t9"}, "depth": 4},
            {"task": {"slug": "t10"}, "depth": 5},
            {"task": {"slug": "t5"}, "depth": 5},
        ]

    async def test_traverse_downstream_from_t4(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t4"}}
        ).first({"id"})

        result = await query_downstream(task.id)

        assert result.data.utility_downstream_tasks == [
            {"task": {"slug": "t4"}, "depth": 0},
            {"task": {"slug": "t5"}, "depth": 1},
        ]

    async def test_traverse_downstream_from_t6_and_t9_includes_t5_at_max_depth(
        self, flow_id
    ):
        t6 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t6"}}
        ).first({"id"})

        t9 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t9"}}
        ).first({"id"})

        result = await query_downstream(t6.id, t9.id)

        assert any(
            t == {"task": {"slug": "t5"}, "depth": 4}
            for t in result.data.utility_downstream_tasks
        )

    async def test_traverse_downstream_from_t8_and_t6_includes_t7(self, flow_id):
        t6 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t6"}}
        ).first({"id"})

        t8 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t8"}}
        ).first({"id"})

        result = await query_downstream(t6.id, t8.id)

        assert any(
            t == {"task": {"slug": "t7"}, "depth": 1}
            for t in result.data.utility_downstream_tasks
        )


class TestUpstreamTraversal:
    r"""
    1 -> 2 -> 3 -> 4 -> 5
            \              /
             7 -> 8 -> 9 -> 10
           /
        6
    """

    async def test_traverse_upstream_from_t5(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t5"}}
        ).first({"id"})

        result = await query_upstream(task.id)

        assert result.data.utility_upstream_tasks == [
            {"task": {"slug": "t5"}, "depth": 0},
            {"task": {"slug": "t4"}, "depth": 1},
            {"task": {"slug": "t9"}, "depth": 1},
            {"task": {"slug": "t3"}, "depth": 2},
            {"task": {"slug": "t8"}, "depth": 2},
            {"task": {"slug": "t7"}, "depth": 3},
            {"task": {"slug": "t2"}, "depth": 4},
            {"task": {"slug": "t6"}, "depth": 4},
            {"task": {"slug": "t1"}, "depth": 5},
        ]

    async def test_traverse_upstream_with_limit(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t5"}}
        ).first({"id"})
        result = await hasura.HasuraClient().execute(
            {
                "query": {
                    with_args(
                        "utility_upstream_tasks",
                        {
                            "args": {
                                "start_task_ids": LiteralSetValue([task.id]),
                                "depth_limit": 2,
                            },
                            "order_by": {
                                "depth": EnumValue("asc"),
                                "task": {"slug": EnumValue("asc")},
                            },
                        },
                    ): {"task": {"slug"}, "depth": True}
                }
            }
        )

        assert result.data.utility_upstream_tasks == [
            {"task": {"slug": "t5"}, "depth": 0},
            {"task": {"slug": "t4"}, "depth": 1},
            {"task": {"slug": "t9"}, "depth": 1},
            {"task": {"slug": "t3"}, "depth": 2},
            {"task": {"slug": "t8"}, "depth": 2},
        ]

    async def test_traverse_upstream_with_where_clause(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t5"}}
        ).first({"id"})
        result = await hasura.HasuraClient().execute(
            {
                "query": {
                    with_args(
                        "utility_upstream_tasks",
                        {
                            "args": {"start_task_ids": LiteralSetValue([task.id])},
                            "order_by": {
                                "depth": EnumValue("asc"),
                                "task": {"slug": EnumValue("asc")},
                            },
                            "where": {
                                "task": {"slug": {"_neq": "t4"}},
                                "depth": {"_neq": 4},
                            },
                        },
                    ): {"task": {"slug"}, "depth": True}
                }
            }
        )

        assert result.data.utility_upstream_tasks == [
            {"task": {"slug": "t5"}, "depth": 0},
            {"task": {"slug": "t9"}, "depth": 1},
            {"task": {"slug": "t3"}, "depth": 2},
            {"task": {"slug": "t8"}, "depth": 2},
            {"task": {"slug": "t7"}, "depth": 3},
            {"task": {"slug": "t1"}, "depth": 5},
        ]

    async def test_traverse_upstream_from_t7(self, flow_id):
        task = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t7"}}
        ).first({"id"})

        result = await query_upstream(task.id)

        assert result.data.utility_upstream_tasks == [
            {"task": {"slug": "t7"}, "depth": 0},
            {"task": {"slug": "t2"}, "depth": 1},
            {"task": {"slug": "t6"}, "depth": 1},
            {"task": {"slug": "t1"}, "depth": 2},
        ]

    async def test_traverse_upstream_from_t3_and_t10_includes_t1_at_max_depth(
        self, flow_id
    ):
        t3 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t3"}}
        ).first({"id"})

        t10 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t10"}}
        ).first({"id"})

        result = await query_upstream(t3.id, t10.id)

        assert any(
            t == {"task": {"slug": "t1"}, "depth": 5}
            for t in result.data.utility_upstream_tasks
        )

    async def test_traverse_upstream_from_t8_and_t6_includes_t7(self, flow_id):
        t6 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t6"}}
        ).first({"id"})

        t8 = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "slug": {"_eq": "t8"}}
        ).first({"id"})

        result = await query_upstream(t6.id, t8.id)

        assert any(
            t == {"task": {"slug": "t7"}, "depth": 1}
            for t in result.data.utility_upstream_tasks
        )
