from typing import Coroutine

import pytest
from prefect_github.graphql import (
    _subset_return_fields,
    aexecute_graphql,
    execute_graphql,
)
from prefect_github.schemas import graphql_schema
from sgqlc.operation import Operation, Selector

from prefect import flow


@pytest.mark.parametrize(
    "return_fields_key", ["return_fields", "return_fields_defaults"]
)
def test_subset_return_fields(return_fields_key):
    op = Operation(graphql_schema.Query)
    op_stack = graphql_schema.Query.__field_names__[:1]
    op_selection = getattr(op, op_stack[0])
    subset_kwargs = {"return_fields": [], "return_fields_defaults": {}}
    return_fields = ["id"]
    if return_fields_key == "return_fields":
        subset_kwargs[return_fields_key] = return_fields
    else:
        subset_kwargs[return_fields_key] = {op_stack: return_fields}
    op_selection = _subset_return_fields(op_selection, op_stack, **subset_kwargs)
    assert isinstance(op_selection, Selector)


class MockCredentials:
    def __init__(self, error_key=None):
        self.result = (
            {error_key: "Errors encountered:"} if error_key else {"data": "success"}
        )

    def get_endpoint(self):
        return lambda op, vars: self.result

    def get_client(self):
        return lambda op, vars: self.result


@pytest.mark.parametrize("error_key", ["errors", False])
def test_execute_graphql(error_key):
    mock_credentials = MockCredentials(error_key=error_key)

    @flow
    def test_flow():
        return execute_graphql("op", mock_credentials)

    if error_key:
        with pytest.raises(RuntimeError, match="Errors encountered:"):
            test_flow()
    else:
        assert test_flow() == "success"


class TestExecuteGraphqlAsyncDispatch:
    """Tests for execute_graphql migrated from @sync_compatible to @async_dispatch.

    These tests verify the critical behavior from issue #15008 where
    @sync_compatible would incorrectly return coroutines in sync context.
    """

    def test_execute_graphql_sync_context_returns_value_not_coroutine(self):
        """execute_graphql must return value (not coroutine) in sync context.

        This is the critical regression test for issues #14712 and #14625.
        """
        mock_credentials = MockCredentials(error_key=False)

        @flow
        def test_flow():
            result = execute_graphql("op", mock_credentials)
            # the result inside the flow should be the actual value, not a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        assert test_flow() == "success"

    async def test_execute_graphql_async_context_works(self):
        """execute_graphql should work correctly in async context."""
        mock_credentials = MockCredentials(error_key=False)

        @flow
        async def test_flow():
            # when decorated with @task, the task machinery handles execution
            # so we get a result directly, not a coroutine
            result = execute_graphql("op", mock_credentials)
            return result

        assert await test_flow() == "success"

    def test_aexecute_graphql_is_exported(self):
        """aexecute_graphql should be available for direct async usage."""
        # just verify it's importable and is a task
        assert callable(aexecute_graphql)

    def test_task_identity_preserved(self):
        """Both execute_graphql and aexecute_graphql should have Task identity.

        This verifies decorator order is correct (@task must be outermost).
        See PR #20300 for the dbt decorator ordering fix.
        """
        # .with_options() is only available on proper Task objects
        assert hasattr(execute_graphql, "with_options"), (
            "execute_graphql missing .with_options() - check decorator order"
        )
        assert hasattr(aexecute_graphql, "with_options"), (
            "aexecute_graphql missing .with_options() - check decorator order"
        )

        # verify we can actually call with_options
        configured = execute_graphql.with_options(retries=3)
        assert configured is not None
