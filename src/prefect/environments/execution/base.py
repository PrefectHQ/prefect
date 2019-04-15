import json
from typing import TYPE_CHECKING

import prefect

if TYPE_CHECKING:
    import prefect.engine.state


class Environment:
    """
    """

    def __init__(self) -> None:
        pass

    def process(self, storage: "prefect.environments.storage.Storage") -> None:
        """"""
        pass

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
