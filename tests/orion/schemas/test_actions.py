from uuid import uuid4

import pytest

from prefect.orion.schemas.actions import DeploymentCreate, FlowRunCreate


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


class TestDeployeCreate:
    def test_create_with_worker_pool_queue_id_warns(self):
        with pytest.warns(
            UserWarning,
            match="`worker_pool_queue_id` is no longer supported for creating. "
            "deployments. Please use `worker_pool_name` and "
            "`worker_pool_queue_name` instead.",
        ):
            deployment_create = DeploymentCreate(
                **dict(name="test-deployment", worker_pool_queue_id=uuid4())
            )

        assert getattr(deployment_create, "worker_pool_queue_id", 0) == 0
