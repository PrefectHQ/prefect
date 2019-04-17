import prefect


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
        Executes the flow for this environment
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
