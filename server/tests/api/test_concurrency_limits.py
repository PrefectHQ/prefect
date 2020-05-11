# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio
import uuid
from typing import List

import pendulum
import pytest
from asynctest import CoroutineMock
from prefect.engine.state import Running

from prefect_server import api
from prefect_server.database import models, orm


class TestCreateFlowConcurrencyLimit:
    async def test_creates_flow_concurrency_limit(self):

        flow_concurrency_limit_name = uuid.uuid4().hex
        description = (
            "A flow concurrency limit created from Prefect Server's test suite."
        )
        limit = 5

        concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()

        concurrency_limit_id = await api.concurrency_limits.create_flow_concurrency_limit(
            flow_concurrency_limit_name, limit=limit, description=description
        )

        new_concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()
        assert (concurrency_limit_count + 1) == new_concurrency_limit_count

        concurrency_limit = await models.FlowConcurrencyLimit.where(
            where={"id": {"_eq": concurrency_limit_id}}
        ).first({"id", "name", "description", "limit"})
        assert concurrency_limit is not None
        assert concurrency_limit.id == concurrency_limit_id
        assert concurrency_limit.description == description
        assert concurrency_limit.limit == limit
        assert concurrency_limit.name == flow_concurrency_limit_name

    @pytest.mark.parametrize("limit", [0, -5])
    async def test_raises_error_on_bad_limit(self, limit: int):

        flow_concurrency_limit_name = "test concurrency limit"
        description = (
            "A flow concurrency limit created from Prefect Server's test suite."
        )

        concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()

        with pytest.raises(ValueError):
            concurrency_limit_id = await api.concurrency_limits.create_flow_concurrency_limit(
                flow_concurrency_limit_name, limit=limit, description=description
            )

        new_concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()
        # Making sure no create happened
        assert concurrency_limit_count == new_concurrency_limit_count

    async def test_conflicting_flow_concurrency_name_raises_error(self):

        flow_concurrency_limit_name = uuid.uuid4().hex
        description = (
            "A flow concurrency limit created from Prefect Server's test suite."
        )
        limit = 5

        concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()

        concurrency_limit_id = await api.concurrency_limits.create_flow_concurrency_limit(
            flow_concurrency_limit_name, limit=limit, description=description
        )

        new_concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()

        assert (concurrency_limit_count + 1) == new_concurrency_limit_count

        with pytest.raises(ValueError):
            concurrency_limit_id = await api.concurrency_limits.create_flow_concurrency_limit(
                flow_concurrency_limit_name, limit=limit, description=description
            )

        newest_concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()
        assert newest_concurrency_limit_count == new_concurrency_limit_count


class TestDeleteFlowConcurrencyLimit:
    async def test_delete_existing(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):

        concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()
        deleted = await api.concurrency_limits.delete_flow_concurrency_limit(
            flow_concurrency_limit.id
        )
        assert deleted is True

        new_concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()

        assert concurrency_limit_count == (new_concurrency_limit_count + 1)

    async def test_delete_bad_id(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):

        concurrency_limit = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()
        deleted = await api.concurrency_limits.delete_flow_concurrency_limit(
            uuid.uuid4().hex
        )
        assert deleted is False

        new_concurrency_limit_count = await orm.ModelQuery(
            model=models.FlowConcurrencyLimit
        ).count()

        assert concurrency_limit == new_concurrency_limit_count


class TestGetAvailableConcurrencyLimits:
    async def test_raises_error_without_params(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):

        with pytest.raises(TypeError):
            available_concurrency_limits = (
                await api.concurrency_limits.get_available_flow_concurrency()
            )

    @pytest.mark.parametrize(
        "labels", [["foo"], ["bar"], ["foo", "bar"], ["bar", "foo"]]
    )
    async def test_contains_partial_matches_in(
        self, labeled_flow_id: str, labels: List[str]
    ):
        """
        This test doesn't necessarily test our code, but it does test
        that our understanding of how Hasura handles filtering a JSONB
        for the existance of one or more values that should return a match
        given the structure:
        {
            environment: {labels: [foo, bar, value,3]}
        }
        These find the match because they're either a subset or exact
        match. Order doesn't matter.
        """

        res = await models.Flow.where(
            {"environment": {"_contains": {"labels": labels}}}
        ).count()
        assert res == 1

    @pytest.mark.parametrize("labels", [["foo", "bar", "baz"], ["baz"], ["foo", "baz"]])
    async def test_contains_not_full_match(
        self, labeled_flow_id: str, labels: List[str]
    ):
        """
        This test doesn't necessarily test our code, but it does test
        that our understanding of how Hasura handles filtering a JSONB
        for the existance of one or more values that should not return 
        a match given the structure:
        {
            environment: {labels: [value, value2, value,3]}
        }
        These don't find a match because the _contains filter needs
        to be an exact match or subset.

        """
        res = await models.Flow.where(
            {"environment": {"_contains": {"labels": labels}}}
        ).count()
        assert res == 0

    async def test_only_includes_running_states(
        self,
        labeled_flow_id: str,
        labeled_flow_run_id: str,
        labeled_flow_run_id_2: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests to make sure that only running states count towards
        the concurrency limit's usage.
        """

        # Setting the limit higher so we can actually observe the changes
        await models.FlowConcurrencyLimit.where(id=flow_concurrency_limit.id).update(
            set={"limit": 10}
        )

        available_concurrency_limits = await api.concurrency_limits.get_available_flow_concurrency(
            [flow_concurrency_limit.name]
        )

        assert available_concurrency_limits[flow_concurrency_limit.name] == 9

        # Now that the flow is running, it should take up a spot
        await api.states.set_flow_run_state(labeled_flow_run_id, Running())

        new_available_concurrency_limits = await api.concurrency_limits.get_available_flow_concurrency(
            [flow_concurrency_limit.name]
        )
        # We should have 1 less spot due to the new flow run
        old = available_concurrency_limits[flow_concurrency_limit.name]
        new = new_available_concurrency_limits[flow_concurrency_limit.name]
        assert old == new + 1

    async def test_only_includes_labeled_runs(
        self,
        flow_run_id: str,
        labeled_flow_id: str,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests to make sure that only flows using the environment that is tagged
        counts towards the concurrency limit's capacity.
        """

        # Setting the limit higher so we can actually observe the changes
        await models.FlowConcurrencyLimit.where(id=flow_concurrency_limit.id).update(
            set={"limit": 10}
        )

        available_concurrency_limits = await api.concurrency_limits.get_available_flow_concurrency(
            [flow_concurrency_limit.name]
        )

        assert available_concurrency_limits[flow_concurrency_limit.name] == 10

        # Marking the flow that _doesn't_ use the concurrency limit as running
        await api.states.set_flow_run_state(flow_run_id, Running())

        new_available_concurrency_limits = await api.concurrency_limits.get_available_flow_concurrency(
            [flow_concurrency_limit.name]
        )
        # No flow concurrency limit should be taken because it isn't tagged w/ the label
        assert available_concurrency_limits == new_available_concurrency_limits
