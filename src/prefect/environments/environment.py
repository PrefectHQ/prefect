"""
Environments are JSON-serializable objects that fully describe how to run a flow. Serialization
schemas are contained in `prefect.serialization.environment.py`.

Different Environment objects correspond to different computation environments -- for
example, a `LocalEnvironment` runs a flow in the local process; a `DockerEnvironment`
runs a flow in a Docker container.

Environments that are written on top of a type of infrastructure also define how to
set up and execute that environment. e.g. DockerOnKubernetes is an environment which
runs a flow on Kubernetes using the DockerEnvironment.

Some of the information that the environment requires to run a flow -- such as the flow
itself -- may not available when the Environment class is instantiated. Therefore, Environments
may be created with a subset of their (ultimate) required information, and the rest can be
provided when the environment's `build()` method is called.

The most basic Environment is a `LocalEnvironment`. This class stores a serialized version
of a Flow and deserializes it to run it. It is expected that most other Environments
will manipulate LocalEnvironments to actually run their flows. For example, the
`DockerEnvironment` builds a Docker image with all necessary dependencies installed
and also a serialized `LocalEnvironment`. When the `DockerEnvironment` is deployed,
the container in turn runs the `LocalEnvironment`.
"""

import json

import prefect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import prefect.engine.state


class Environment:
    """
    Base class for Environments.

    An environment is an object that can be instantiated in a way that makes it possible to
    call `environment.run()` and run a flow.

    Because certain `__init__` parameters may not be known when the Environment is first
    created, including which Flow to run, Environments have a `build()` method that takes
    a `Flow` argument and returns an Environment with all `__init__` parameters specified.

    The setup and execute functions are limited to environments which have an infrastructure
    requirement. However the build and run functions are limited to base environments such
    as (LocalEnvironment and DockerEnvironment) from which infrastructure dependent environments
    inherit from.
    """

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Environment":
        """
        Builds the environment for a specific flow. A new environment is returned.

        Args:
            - flow (prefect.Flow): the Flow for which the environment will be built

        Returns:
            - Environment: a new environment that can run the provided Flow.
        """
        raise NotImplementedError()

    def execute(self) -> None:
        """
        Executes the environment on any infrastructure created during setup
        """
        pass

    def run(self) -> "prefect.engine.state.State":
        """
        Runs the `Flow` represented by this environment.

        Returns:
            - prefect.engine.state.State: the state of the flow run
        """
        raise NotImplementedError()

    def setup(self) -> None:
        """
        Sets up the infrastructure needed for this environment
        """
        pass

    def serialize(self) -> dict:
        """
        Returns a serialized version of the Environment

        Returns:
            - dict: the serialized Environment
        """
        schema = prefect.serialization.environment.EnvironmentSchema()
        return schema.dump(self)

    def to_file(self, path: str) -> None:
        """
        Serialize the environment to a file.

        Args:
            - path (str): the file path to which the environment will be written
        """
        with open(path, "w") as f:
            json.dump(self.serialize(), f)
