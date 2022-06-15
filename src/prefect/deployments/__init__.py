"""
Objects for specifying deployments and utilities for loading flows from deployments.

The primary object is the `DeploymentSpecification` which can be used to define a deployment.
Once a specification is written, it can be used with the Orion client or CLI to create
a deployment in the backend.

There are several types of deployment specifications, each with a different method for
packaging your flow. Currently available types include:

- ScriptDeploymentSpecification


Examples:
    Define a flow
    >>> from prefect import flow
    >>> @flow
    >>> def hello_world(name="world"):
    >>>     print(f"Hello, {name}!")

    Write a deployment specification that sets a new parameter default
    >>> from prefect.deployments import ScriptDeploymentSpecification
    >>> ScriptDeploymentSpecification(
    >>>     flow=hello_world,
    >>>     name="my-first-deployment",
    >>>     parameters={"name": "Earth"},
    >>>     tags=["foo", "bar"],
    >>> )

    Add a schedule to the deployment specification to run the flow hourly
    >>> from prefect.orion.schemas.schedules import IntervalSchedule
    >>> from datetime import timedelta
    >>> ScriptDeploymentSpecification(
    >>>     ...
    >>>     schedule=IntervalSchedule(interval=timedelta(hours=1))
    >>> )

    Deployment specifications can also be written in YAML and refer to the flow's
    location instead of the `Flow` object.
    ```yaml
    type: ScriptDeploymentSpecification
    name: my-first-deployment
    flow_location: ./path-to-the-flow-script.py
    flow_name: hello-world
    tags:
    - foo
    - bar
    parameters:
      name: "Earth"
    schedule:
      interval: 3600
    ```
"""
from .script import ScriptDeploymentSpecification


class DeploymentSpec(ScriptDeploymentSpecification):
    def __init__(self, **data) -> None:
        # TODO: Enable this deprecation warning once we have made a determination on
        #       the desired interface for deployment declaration
        # warnings.warn(
        #     "'DeploymentSpec' has been renamed to 'ScriptDeploymentSpecification'.",
        #     DeprecationWarning,
        # )
        return super().__init__(**data)
