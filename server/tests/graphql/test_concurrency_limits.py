# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import time
import uuid
from unittest.mock import MagicMock

import pendulum
import prefect
import pytest
from prefect.engine.state import Running, Scheduled, Submitted

from prefect_server import api, config
from prefect_server.database import models
from prefect_server.utilities.exceptions import Unauthenticated, Unauthorized
from prefect_server.utilities.tests import set_temporary_config


class TestUpdateFlowConcurrencyLimit:
    mutation = """
        mutation($input: update_flow_concurrency_limit_input!) {
            update_flow_concurrency_limit(input: $input) {
                id
            }
        }
    """

    async def test_creates_limit_if_not_exists(self, run_query):
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(name="spark", limit=10))
        )
        limit_id = result.data.update_flow_concurrency_limit.id
        assert limit_id is not None
        limit = await models.FlowConcurrencyLimit.where(id=limit_id).first(
            {"id", "name", "limit"}
        )
        assert limit.id == limit_id
        assert limit.name == "spark"
        assert limit.limit == 10

    async def test_updates_existing_limit(self, run_query, flow_concurrency_limit):
        # Making sure the fixture didn't change so we can properly
        # assert the mutation actually does something

        assert flow_concurrency_limit.limit != 10

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(name=flow_concurrency_limit.name, limit=10)),
        )
        limit_id = result.data.update_flow_concurrency_limit.id
        # Operating on existing item instead of creating a new one
        assert limit_id == flow_concurrency_limit.id

        limit = await models.FlowConcurrencyLimit.where(id=limit_id).first(
            {"id", "name", "limit"}
        )
        assert limit.id == limit_id
        assert limit.name == flow_concurrency_limit.name
        assert limit.limit == 10

    async def test_raises_error_on_bad_limit(self, run_query):
        limit_name = "spark"
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(name=limit_name, limit=-5))
        )
        assert result.errors
        assert limit_name in result.errors[0]["message"]
        assert "limit runs" in result.errors[0]["message"]

        assert await models.FlowConcurrencyLimit.where().count() == 0


class TestDeleteFlowConcurrencyLimit:
    mutation = """
        mutation($input: delete_flow_concurrency_limit_input!) {
            delete_flow_concurrency_limit(input: $input) {
                success
            }
        }
    """

    async def test_delete_limit_bad_id(self, run_query):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_concurrency_limit_id=str(uuid.uuid4()))),
        )

        assert not result.data.delete_flow_concurrency_limit.success

    async def test_deletes_concurrency_limit(self, run_query, flow_concurrency_limit):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(flow_concurrency_limit_id=flow_concurrency_limit.id)
            ),
        )
        assert result.data.delete_flow_concurrency_limit.success
        assert not await models.FlowConcurrencyLimit.exists(flow_concurrency_limit.id)
