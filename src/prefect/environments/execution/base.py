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

    def setup(self, storage: "prefect.environments.storage.Storage") -> None:
        """
        Sets up the infrastructure needed for this environment
        """
        pass

    def execute(self, storage: "prefect.environments.storage.Storage") -> None:
        """
        Executes the environment on any infrastructure created during setup
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
