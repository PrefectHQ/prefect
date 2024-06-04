from typing import Optional

from prefect.utilities.hashing import hash_objects


class KeyPolicy:
    def from_function(cls, fn) -> "KeyPolicy":
        """
        Given a function generates a key policy.
        """
        pass

    def from_cache_key_fn(cls, fn) -> "KeyPolicy":
        """
        Given a function generates a key policy.
        """
        pass

    def compute_key(
        self, task, run, inputs, flow_parameters, **kwargs
    ) -> Optional[str]:
        raise NotImplementedError


class Default(KeyPolicy):
    "Execution run ID only"

    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> str:
        return str(run.id)


class _None(KeyPolicy):
    "ignore key policies altogether, always run - prevents persistence"

    def compute_key(self, task, run, parameters, flow_parameters, **kwargs) -> None:
        return None


class TaskDef(KeyPolicy):
    pass


class FlowParameters(KeyPolicy):
    pass


class Inputs(KeyPolicy):
    """
    Exposes flag for whether to include flow parameters as well.

    And exclude/include config.
    """

    def compute_key(self, task, run, parameters, flow_parameters, **kwargs) -> None:
        # to_hash = flow_parameters.values() if self.include_flow_params

        for parameter in parameters:
            pass

        return hash_objects()


DEFAULT = Default()
