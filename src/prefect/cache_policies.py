import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from prefect.context import TaskRunContext
from prefect.utilities.hashing import hash_objects


@dataclass
class CachePolicy:
    @classmethod
    def from_cache_key_fn(
        cls, cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]]
    ) -> "CacheKeyFnPolicy":
        """
        Given a function generates a key policy.
        """
        return CacheKeyFnPolicy(cache_key_fn=cache_key_fn)

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
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
class CacheKeyFnPolicy(CachePolicy):
    # making it optional for tests
    cache_key_fn: Optional[
        Callable[["TaskRunContext", Dict[str, Any]], Optional[str]]
    ] = None

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        if self.cache_key_fn:
            return self.cache_key_fn(task_ctx, inputs)


@dataclass
class CompoundCachePolicy(CachePolicy):
    policies: Optional[list] = None

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        keys = []
        for policy in self.policies or []:
            keys.append(
                policy.compute_key(
                    task_ctx=task_ctx,
                    inputs=inputs,
                    flow_parameters=flow_parameters,
                    **kwargs,
                )
            )
        return hash_objects(*keys)


@dataclass
class _None(CachePolicy):
    "ignore key policies altogether, always run - prevents persistence"

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        return None


@dataclass
class TaskSource(CachePolicy):
    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        try:
            lines = inspect.getsource(task_ctx.task)
        except TypeError:
            lines = inspect.getsource(task_ctx.task.fn.__class__)

        return hash_objects(lines)


@dataclass
class FlowParameters(CachePolicy):
    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        return hash_objects(flow_parameters)


@dataclass
class RunId(CachePolicy):
    """
    Returns either the prevailing flow run ID, or if not found, the prevailing task
    run ID.
    """

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        run_id = task_ctx.task_run.flow_run_id
        if run_id is None:
            run_id = task_ctx.task_run.id
        return str(run_id)


@dataclass
class Inputs(CachePolicy):
    """
    Exposes flag for whether to include flow parameters as well.

    And exclude/include config.
    """

    exclude: Optional[list] = None

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        hashed_inputs = {}
        inputs = inputs or {}
        exclude = self.exclude or []

        for key, val in inputs.items():
            if key not in exclude:
                hashed_inputs[key] = val

        return hash_objects(hashed_inputs)


INPUTS = Inputs()
NONE = _None()
TASK_SOURCE = TaskSource()
FLOW_PARAMETERS = FlowParameters()
RUN_ID = RunId()
DEFAULT = INPUTS + TASK_SOURCE + RUN_ID
