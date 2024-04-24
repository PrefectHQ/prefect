import pytest
from prefect_github.graphql import _subset_return_fields, execute_graphql
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
