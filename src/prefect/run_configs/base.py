from typing import Iterable, Set, Any  # noqa

import prefect


class RunConfig:
    """
    Base class for RunConfigs.

    A "run config" is an object for configuring a flow run, which maps to a
    specific agent backend.

    Args:
        - env (dict, optional): Additional environment variables to set
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work
    """

    def __init__(self, env: dict = None, labels: Iterable[str] = None):
        self.env = env
        self.labels = set(labels) if labels else set()  # Set[str]

    def serialize(self) -> dict:
        """
        Returns a serialized version of the RunConfig.

        Returns:
            - dict: the serialized RunConfig
        """
        schema = prefect.serialization.run_config.RunConfigSchema()
        return schema.dump(self)

    def __eq__(self, other: Any) -> Any:
        """This equality check is _only_ exposed for testing"""
        if not isinstance(other, RunConfig):
            return NotImplemented
        return self.serialize() == other.serialize()


class UniversalRun(RunConfig):
    """
    Configure a flow-run to run universally on any Agent.

    Unlike the other agent-specific `RunConfig` classes (e.g. `LocalRun` for
    the Local Agent), the `UniversalRun` run config is compatible with any
    agent. This can be useful for flows that don't require any custom
    configuration other than flow labels, allowing for transitioning a flow
    between agent types without any config changes.

    Args:
        - env (dict, optional): Additional environment variables to set
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work

    Examples:

    Use the defaults set on the agent:

    ```python
    flow.run_config = UniversalRun()
    ```

    Configure additional labels:

    ```python
    flow.run_config = UniversalRun(env={"SOME_VAR": "value"}, labels=["label-1", "label-2"])
    ```
    """
