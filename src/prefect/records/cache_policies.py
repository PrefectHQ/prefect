import inspect
from dataclasses import dataclass
from typing import Optional

from prefect.utilities.hashing import hash_objects


@dataclass
class CachePolicy:
    def from_function(cls, fn) -> "CachePolicy":
        """
        Given a function generates a key policy.
        """
        pass

    def from_cache_key_fn(cls, fn) -> "CachePolicy":
        """
        Given a function generates a key policy.
        """
        pass

    def compute_key(
        self, task, run, inputs, flow_parameters, **kwargs
    ) -> Optional[str]:
        raise NotImplementedError

    def __sub__(self, other: str) -> "CompoundCachePolicy":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        if isinstance(self, Inputs):
            exclude = self.exclude or []
            return Inputs(exclude=exclude + [other])
        elif isinstance(self, CompoundCachePolicy):
            new = Inputs(exclude=[other])
            policies = self.policies or []
            return CompoundCachePolicy(policies=policies + [new])
        else:
            new = Inputs(exclude=[other])
            return CompoundCachePolicy(policies=[self, new])

    def __add__(self, other: "CachePolicy") -> "CompoundCachePolicy":
        # adding _None is a no-op
        if isinstance(other, _None):
            return self
        elif isinstance(self, _None):
            return other

        if isinstance(self, CompoundCachePolicy):
            policies = self.policies or []
            return CompoundCachePolicy(policies=policies + [other])
        elif isinstance(other, CompoundCachePolicy):
            policies = other.policies or []
            return CompoundCachePolicy(policies=policies + [self])
        else:
            return CompoundCachePolicy(policies=[self, other])


@dataclass
class CompoundCachePolicy(CachePolicy):
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
class Default(CachePolicy):
    "Execution run ID only"

    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> str:
        return str(run.id)


@dataclass
class _None(CachePolicy):
    "ignore key policies altogether, always run - prevents persistence"

    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> None:
        return None


@dataclass
class TaskDef(CachePolicy):
    def compute_key(self, task, run, inputs, flow_parameters, **kwargs) -> None:
        lines = inspect.getsource(task)
        return hash_objects(lines)


@dataclass
class FlowParameters(CachePolicy):
    pass


@dataclass
class Inputs(CachePolicy):
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
TASKDEF = TaskDef()
