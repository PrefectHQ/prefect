from typing import List, Optional

from prefect.utilities.hashing import hash_objects


class KeyPolicy:
    def compute_key(
        self, task, run, parameters, flow_parameters, **kwargs
    ) -> Optional[str]:
        raise NotImplementedError


class DEFAULT(KeyPolicy):
    "Execution run ID only"

    def compute_key(self, task, run, parameters, flow_parameters, **kwargs) -> str:
        return str(run.id)


RUN_ID = DEFAULT


class NONE(KeyPolicy):
    "ignore key policies altogether, always run - prevents persistence"

    def compute_key(self, task, run, parameters, flow_parameters, **kwargs) -> None:
        return None


class TASK_DEF(KeyPolicy):
    pass


class INPUTS(KeyPolicy):
    """
    Exposes flag for whether to include flow parameters as well.

    And exclude/include config.
    """

    def __init__(self, include_flow_params: bool = False, exclude: List[str] = None):
        self.include_flow_params = include_flow_params
        self.exclude = exclude or []
        super().__init__()

    def compute_key(self, task, run, parameters, flow_parameters, **kwargs) -> None:
        # to_hash = flow_parameters.values() if self.include_flow_params

        for parameter in parameters:
            pass

        return hash_objects()


class CUSTOM(KeyPolicy):
    """
    Can provide a key_fn
    """
