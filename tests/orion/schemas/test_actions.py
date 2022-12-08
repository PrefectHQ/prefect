from uuid import uuid4

import pytest

from prefect.orion.schemas.actions import (
    MAX_FLOW_DESCRIPTION_LENGTH,
    FlowCreate,
    FlowRunCreate,
)


@pytest.mark.parametrize(
    "test_flow, expected_dict",
    [
        (
            {"name": "valid_flow", "description": "short_valid_description"},
            {"name": "valid_flow", "description": "short_valid_description"},
        ),
        pytest.param(
            {
                "name": "invalid_flow",
                "description": "long invalid description" * MAX_FLOW_DESCRIPTION_LENGTH,
            },
            None,
            marks=pytest.mark.xfail,
        ),
    ],
)
class TestFlowCreate:
    def test_flow_create_validates_description(self, test_flow, expected_dict):
        fc = FlowCreate(name=test_flow["name"], description=test_flow["description"])
        assert fc.name == test_flow["name"]
        assert fc.description == test_flow["description"]


@pytest.mark.parametrize(
    "test_params,expected_dict",
    [
        ({"param": 1}, {"param": 1}),
        ({"param": "1"}, {"param": "1"}),
        ({"param": {1: 2}}, {"param": {"1": 2}}),
        (
            {"df": {"col": {0: "1"}}},
            {"df": {"col": {"0": "1"}}},
        ),  # Example of serialzied dataframe parameter with int key
    ],
)
class TestFlowRunCreate:
    def test_dict_json_compatible_succeeds_with_parameters(
        self, test_params, expected_dict
    ):
        frc = FlowRunCreate(flow_id=uuid4(), flow_version="0.1", parameters=test_params)
        res = frc.dict(json_compatible=True)
        assert res["parameters"] == expected_dict
