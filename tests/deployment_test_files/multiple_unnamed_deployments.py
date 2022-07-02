import pathlib
from datetime import timedelta

from prefect.deployments import DeploymentSpec
from prefect.flow_runners import KubernetesFlowRunner
from prefect.orion.schemas.schedules import IntervalSchedule

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    flow_runner=KubernetesFlowRunner(),
    schedule=IntervalSchedule(interval=timedelta(days=1)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"],
)

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    flow_runner=KubernetesFlowRunner(),
    schedule=IntervalSchedule(interval=timedelta(days=1)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"],
)
