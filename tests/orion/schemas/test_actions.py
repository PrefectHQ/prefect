from uuid import uuid4

import pytest

from prefect.orion.schemas.actions import FlowRunCreate


@pytest.mark.parametrize(
    "test_params,expected_serialization",
    [
        ({"param": 1}, '"parameters":{"param":1}'),
        ({"param": "1"}, '"parameters":{"param":"1"}'),
        ({"param": {1: 2}}, '"parameters":{"param":{"1":2}}'),
        (
            {"df": {"col": {0: "1"}}},
            '"parameters":{"df":{"col":{"0":"1"}}}',
        ),  # Example of serialzied dataframe parameter with int key
    ],
)
class TestFlowRunCreate:
    def test_dict_succeeds_with_parameters(self, test_params, expected_serialization):
        frc = FlowRunCreate(flow_id=uuid4(), flow_version="0.1", parameters=test_params)
        res = frc.dict()
        assert expected_serialization in res
