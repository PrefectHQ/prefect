from dataclasses import dataclass
from typing import Optional

from prefect.utilities.hashing import hash_objects


@dataclass
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

    def __rsub__(self, other: str) -> "CompoundKeyPolicy":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        if isinstance(self, Inputs):
            if self.exclude is None:
                self.exclude = [other]
            else:
                self.exclude.append(other)

    def __add__(self, other: "KeyPolicy") -> "CompoundKeyPolicy":
        if isinstance(self, CompoundKeyPolicy):
            self.merge(other)
            return self
        elif isinstance(other, CompoundKeyPolicy):
            other.merge(self)
            return other
        else:
            return CompoundKeyPolicy(policies=[self, other])


@dataclass
class CompoundKeyPolicy:
    policies: list = None

    def merge(self, other):
        """
        Inplace addition of another policy to this compound policy
        """
        if not isinstance(other, _None):
            # ignore _None policies
            if self.policies is None:
                self.policies = [other]
            else:
                self.policies.append(other)

    def compute_key(
        self, task, run, inputs, flow_parameters, **kwargs
    ) -> Optional[str]:
        keys = []
        for policy in self.policies:
            keys.append(
                policy.compute_key(
                    task=task,
                    run=run,
                    inputs=inputs,
                    flow_parameters=flow_parameters,
                    **kwargs,
                )
            )
        return hash_objects(*keys)


@dataclass
class Default(KeyPolicy):
    "Execution run ID only"

    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> str:
        return str(run.id)


@dataclass
class _None(KeyPolicy):
    "ignore key policies altogether, always run - prevents persistence"

    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> None:
        return None


class TaskDef(KeyPolicy):
    pass


class FlowParameters(KeyPolicy):
    pass


@dataclass
class Inputs(KeyPolicy):
    """
    Exposes flag for whether to include flow parameters as well.

    And exclude/include config.
    """

    exclude: list = None

    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> None:
        hashed_inputs = {}
        inputs = inputs or {}
        exclude = self.exclude or []

        for key, val in inputs.items():
            if key not in exclude:
                hashed_inputs[key] = val

        return hash_objects(hashed_inputs)


DEFAULT = Default()
INPUTS = Inputs()
NONE = _None()
