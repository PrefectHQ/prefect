from typing import Iterable, Set  # noqa

import prefect


class RunConfig:
    """
    Base class for RunConfigs.

    An "run config" is an object for configuring a flow run, which maps to a
    specific agent backend.

    Args:
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work
    """

    def __init__(self, labels: Iterable[str] = None):
        self.labels = set(labels) if labels else set()  # Set[str]

    def serialize(self) -> dict:
        """
        Returns a serialized version of the RunConfig.

        Returns:
            - dict: the serialized RunConfig
        """
        schema = prefect.serialization.run_config.RunConfigSchema()
        return schema.dump(self)
