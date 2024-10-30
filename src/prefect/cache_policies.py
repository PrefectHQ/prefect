import inspect
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, Union

from typing_extensions import Self

from prefect.context import TaskRunContext
from prefect.utilities.hashing import hash_objects

if TYPE_CHECKING:
    from prefect.filesystems import WritableFileSystem
    from prefect.locking.protocol import LockManager
    from prefect.transactions import IsolationLevel


@dataclass
class CachePolicy:
    """
    Base class for all cache policies.
    """

    key_storage: Union["WritableFileSystem", str, Path, None] = None
    isolation_level: Union[
        Literal["READ_COMMITTED", "SERIALIZABLE"],
        "IsolationLevel",
        None,
    ] = None
    lock_manager: Optional["LockManager"] = None

    @classmethod
    def from_cache_key_fn(
        cls, cache_key_fn: Callable[["TaskRunContext", Dict[str, Any]], Optional[str]]
    ) -> "CacheKeyFnPolicy":
        """
        Given a function generates a key policy.
        """
        return CacheKeyFnPolicy(cache_key_fn=cache_key_fn)

    def configure(
        self,
        key_storage: Union["WritableFileSystem", str, Path, None] = None,
        lock_manager: Optional["LockManager"] = None,
        isolation_level: Union[
            Literal["READ_COMMITTED", "SERIALIZABLE"], "IsolationLevel", None
        ] = None,
    ) -> Self:
        """
        Configure the cache policy with the given key storage, lock manager, and isolation level.

        Args:
            key_storage: The storage to use for cache keys. If not provided,
                the current key storage will be used.
            lock_manager: The lock manager to use for the cache policy. If not provided,
                the current lock manager will be used.
            isolation_level: The isolation level to use for the cache policy. If not provided,
                the current isolation level will be used.

        Returns:
            A new cache policy with the given key storage, lock manager, and isolation level.
        """
        new = deepcopy(self)
        if key_storage is not None:
            new.key_storage = key_storage
        if lock_manager is not None:
            new.lock_manager = lock_manager
        if isolation_level is not None:
            new.isolation_level = isolation_level
        return new

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        raise NotImplementedError

    def __sub__(self, other: str) -> "CachePolicy":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        new = Inputs(exclude=[other])
        return CompoundCachePolicy(policies=[self, new])

    def __add__(self, other: "CachePolicy") -> "CachePolicy":
        # adding _None is a no-op
        if isinstance(other, _None):
            return self

        if (
            other.key_storage is not None
            and self.key_storage is not None
            and other.key_storage != self.key_storage
        ):
            raise ValueError(
                "Cannot add CachePolicies with different storage locations."
            )
        if (
            other.isolation_level is not None
            and self.isolation_level is not None
            and other.isolation_level != self.isolation_level
        ):
            raise ValueError(
                "Cannot add CachePolicies with different isolation levels."
            )
        if (
            other.lock_manager is not None
            and self.lock_manager is not None
            and other.lock_manager != self.lock_manager
        ):
            raise ValueError(
                "Cannot add CachePolicies with different lock implementations."
            )

        return CompoundCachePolicy(
            policies=[self, other],
            key_storage=self.key_storage or other.key_storage,
            isolation_level=self.isolation_level or other.isolation_level,
            lock_manager=self.lock_manager or other.lock_manager,
        )


@dataclass
class CacheKeyFnPolicy(CachePolicy):
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
class CompoundCachePolicy(CachePolicy):
    """
    This policy is constructed from two or more other cache policies and works by computing the keys
    for each policy individually, and then hashing a sorted tuple of all computed keys.

    Any keys that return `None` will be ignored.
    """

    policies: List[CachePolicy] = field(default_factory=list)

    def compute_key(
        self,
        task_ctx: TaskRunContext,
        inputs: Dict[str, Any],
        flow_parameters: Dict[str, Any],
        **kwargs,
    ) -> Optional[str]:
        keys = []
        for policy in self.policies:
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
        return hash_objects(*keys, raise_on_failure=True)


@dataclass
class _None(CachePolicy):
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

    def __add__(self, other: "CachePolicy") -> "CachePolicy":
        # adding _None is a no-op
        return other


@dataclass
class TaskSource(CachePolicy):
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
            if "source code" in str(exc):
                lines = task_ctx.task.fn.__code__.co_code
            else:
                raise

        return hash_objects(lines, raise_on_failure=True)


@dataclass
class FlowParameters(CachePolicy):
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
        return hash_objects(flow_parameters, raise_on_failure=True)


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
        if not task_ctx:
            return None
        run_id = task_ctx.task_run.flow_run_id
        if run_id is None:
            run_id = task_ctx.task_run.id
        return str(run_id)


@dataclass
class Inputs(CachePolicy):
    """
    Policy that computes a cache key based on a hash of the runtime inputs provided to the task..
    """

    exclude: List[str] = field(default_factory=list)

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

        return hash_objects(hashed_inputs, raise_on_failure=True)

    def __sub__(self, other: str) -> "CachePolicy":
        if not isinstance(other, str):
            raise TypeError("Can only subtract strings from key policies.")
        return Inputs(exclude=self.exclude + [other])


INPUTS = Inputs()
NONE = _None()
TASK_SOURCE = TaskSource()
FLOW_PARAMETERS = FlowParameters()
RUN_ID = RunId()
DEFAULT = INPUTS + TASK_SOURCE + RUN_ID
