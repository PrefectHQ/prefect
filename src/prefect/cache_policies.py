import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from prefect.context import TaskRunContext
from prefect.filesystems import WritableFileSystem
from prefect.utilities.hashing import hash_objects

CacheStorage = Union[WritableFileSystem, Path, str]


@dataclass
class CachePolicy:
    """
    Base class for all cache policies.
    """

    def __add__(self, other: "CachePolicy") -> "CachePolicy":
        raise NotImplementedError


class CacheKeyPolicy(CachePolicy):
    """
    Base class for all cache key policies.
    """

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

    def __add__(self, other: "CachePolicy") -> "CachePolicy":
        if isinstance(other, _None):
            return self
        elif isinstance(other, CompoundCachePolicy):
            return CompoundCachePolicy(policies=[self] + other.policies)
        elif isinstance(other, CacheStoragePolicy):
            return CompoundCachePolicy(policies=[self], storage=other.storage)
        elif isinstance(other, CacheKeyPolicy):
            return CompoundCachePolicy(policies=[self, other])
        else:
            raise TypeError(f"Cannot add {type(self)} and {type(other)}")

    def __sub__(self, other: str) -> "CachePolicy":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        new = Inputs(exclude=[other])
        return CompoundCachePolicy(policies=[self, new])


@dataclass
class CacheStoragePolicy(CachePolicy):
    """
    Policy that defines a storage location for a cache.
    """

    storage: CacheStorage

    def __add__(self, other: "CachePolicy") -> "CachePolicy":
        if isinstance(other, _None):
            return self
        elif isinstance(other, CacheStoragePolicy):
            raise ValueError("Cannot add two storage policies.")
        elif isinstance(other, CompoundCachePolicy):
            if other.storage is not None:
                raise ValueError("Policy already has cache storage defined.")
            return CompoundCachePolicy(policies=other.policies, storage=self.storage)
        elif isinstance(other, CacheKeyPolicy):
            return CompoundCachePolicy(policies=[other], storage=self.storage)
        else:
            raise TypeError(f"Cannot add CacheStoragePolicy and {type(other)}")


@dataclass
class CacheKeyFnPolicy(CacheKeyPolicy):
    """
    This policy accepts a custom function with signature f(task_run_context, task_parameters, flow_parameters) -> str
    and uses it to compute a task run cache key.
    """

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
class CompoundCachePolicy(CacheKeyPolicy):
    """
    This policy is constructed from two or more other cache policies and works by computing the keys
    for each policy individually, and then hashing a sorted tuple of all computed keys.

    Any keys that return `None` will be ignored.
    """

    policies: List[CacheKeyPolicy] = field(default_factory=list)
    storage: Optional[CacheStorage] = None

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        keys = []
        for policy in self.policies or []:
            policy_key = policy.compute_key(
                task_ctx=task_ctx,
                inputs=inputs,
                flow_parameters=flow_parameters,
                **kwargs,
            )
            if policy_key is not None:
                keys.append(policy_key)
        if not keys:
            return None
        return hash_objects(*keys)

    def __add__(self, other: "CachePolicy") -> "CachePolicy":
        if isinstance(other, _None):
            return self
        elif isinstance(other, CompoundCachePolicy):
            return CompoundCachePolicy(policies=self.policies + other.policies)
        elif isinstance(other, CacheStoragePolicy):
            return CompoundCachePolicy(policies=self.policies, storage=other.storage)
        elif isinstance(other, CacheKeyPolicy):
            return CompoundCachePolicy(policies=self.policies + [other])
        else:
            raise TypeError(f"Cannot add {type(self)} and {type(other)}")

    def __sub__(self, other: str) -> "CompoundCachePolicy":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        new = Inputs(exclude=[other])
        policies = self.policies or []
        return CompoundCachePolicy(policies=policies + [new])


@dataclass
class _None(CacheKeyPolicy):
    """
    Policy that always returns `None` for the computed cache key.
    This policy prevents persistence.
    """

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        return None


@dataclass
class TaskSource(CacheKeyPolicy):
    """
    Policy for computing a cache key based on the source code of the task.
    """

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Optional[Dict[str, Any]],
        flow_parameters: Optional[Dict[str, Any]],
        **kwargs,
    ) -> Optional[str]:
        if not task_ctx:
            return None
        try:
            lines = inspect.getsource(task_ctx.task)
        except TypeError:
            lines = inspect.getsource(task_ctx.task.fn.__class__)
        except OSError as exc:
            if "could not get source code" in str(exc):
                lines = task_ctx.task.fn.__code__.co_code
            else:
                raise

        return hash_objects(lines)


@dataclass
class FlowParameters(CacheKeyPolicy):
    """
    Policy that computes the cache key based on a hash of the flow parameters.
    """

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        if not flow_parameters:
            return None
        return hash_objects(flow_parameters)


@dataclass
class RunId(CacheKeyPolicy):
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
        if not task_ctx:
            return None
        run_id = task_ctx.task_run.flow_run_id
        if run_id is None:
            run_id = task_ctx.task_run.id
        return str(run_id)


@dataclass
class Inputs(CacheKeyPolicy):
    """
    Policy that computes a cache key based on a hash of the runtime inputs provided to the task..
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

        if not inputs:
            return None

        for key, val in inputs.items():
            if key not in exclude:
                hashed_inputs[key] = val

        return hash_objects(hashed_inputs)

    def __sub__(self, other: str) -> "Inputs":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        exclude = self.exclude or []
        return Inputs(exclude=exclude + [other])


INPUTS = Inputs()
NONE = _None()
TASK_SOURCE = TaskSource()
FLOW_PARAMETERS = FlowParameters()
RUN_ID = RunId()
DEFAULT = INPUTS + TASK_SOURCE + RUN_ID
