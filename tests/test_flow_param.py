from prefect import flow
from prefect.deployments import Deployment
from prefect.runtime.flow_run import parameters


@flow
def dummy_flow(
    param1: str = "param1 default value",
    param2: str = "param2 default value",
):
    pass


def test_param_assert():
    Deployment.build_from_flow(
        flow=dummy_flow,
        name="dummy",
        apply=True,
        parameters={"param1": "param1 deployment value"},
    )

    assert parameters.get("param1") == "param1 deployment value"
    assert parameters.get("param2") == "param2 default value"
