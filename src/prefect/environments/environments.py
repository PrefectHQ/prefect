import json

import prefect

class Environment:
    """"""
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
        raise NotImplementedError()

    def run(self) -> None:
        raise NotImplementedError()

    def setup(self) -> None:
        raise NotImplementedError()

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