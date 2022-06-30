import pathlib
from datetime import timedelta

from prefect.deployments import DeploymentSpec
from prefect.flow_runners import KubernetesFlowRunner, SubprocessFlowRunner
from prefect.orion.schemas.schedules import IntervalSchedule

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    flow_runner=KubernetesFlowRunner(),
    name="hello-world-daily",
    schedule=IntervalSchedule(interval=timedelta(days=1)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"],
)

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    flow_runner=KubernetesFlowRunner(),
    name="hello-world-weekly",
    schedule=IntervalSchedule(interval=timedelta(days=7)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"],
)

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    flow_runner=KubernetesFlowRunner(
        customizations=[
            {
                "op": "add",
                "path": "/metadata/labels/custom-label",
                "value": "hi",
            },
            {
                "op": "add",
                "path": "/spec/template/spec/containers/0/env/-",
                "value": {"name": "MY_ENV_VAR", "value": "sweet!"},
            },
        ]
    ),
    name="custom-boi",
    schedule=IntervalSchedule(interval=timedelta(days=7)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"],
)

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    flow_runner=SubprocessFlowRunner(),
    name="not-a-k8s",
    schedule=IntervalSchedule(interval=timedelta(days=1)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"],
)
