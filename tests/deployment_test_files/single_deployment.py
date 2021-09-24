import pathlib
from prefect.deployments import DeploymentSpec
from prefect.orion.schemas.schedules import IntervalSchedule
from datetime import timedelta

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "single_flow.py",
    name="hello-world-daily",
    schedule=IntervalSchedule(interval=timedelta(days=1)),
    parameters={"foo": "bar"},
    tags=["foo", "bar"]
)
