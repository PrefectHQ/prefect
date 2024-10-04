import itertools
from dataclasses import dataclass
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from prefect.cache_policies import (
    DEFAULT,
    CachePolicy,
    CompoundCachePolicy,
    Inputs,
    RunId,
    TaskSource,
    _None,
)
from prefect.context import TaskRunContext


class TestBaseClass:
    def test_cache_policy_initializes(self):
        policy = CachePolicy()
        assert isinstance(policy, CachePolicy)

    def test_compute_key_not_implemented(self):
        policy = CachePolicy()
        with pytest.raises(NotImplementedError):
            policy.compute_key(task_ctx=None, inputs=None, flow_parameters=None)


class TestNonePolicy:
    def test_initializes(self):
        policy = _None()
        assert isinstance(policy, CachePolicy)

    def test_doesnt_compute_a_key(self):
        policy = _None()
        key = policy.compute_key(task_ctx=None, inputs=None, flow_parameters=None)
        assert key is None

    @pytest.mark.parametrize("typ", CachePolicy.__subclasses__())
    def test_addition_of_none_is_noop(self, typ):
        policy = _None()
        other = typ()
        assert policy + other == other


class TestInputsPolicy:
    def test_initializes(self):
        policy = Inputs()
        assert isinstance(policy, CachePolicy)

    def test_key_varies_on_inputs(self):
        policy = Inputs()
        none_key = policy.compute_key(task_ctx=None, inputs=None, flow_parameters=None)
        x_key = policy.compute_key(
            task_ctx=None, inputs={"x": 42}, flow_parameters=None
        )
        y_key = policy.compute_key(
            task_ctx=None, inputs={"y": 42}, flow_parameters=None
        )

        assert x_key != y_key
        assert x_key != none_key
        assert y_key != none_key

        z_key = policy.compute_key(
            task_ctx=None, inputs={"z": "foo"}, flow_parameters=None
        )

        assert z_key not in [x_key, y_key]

    def test_key_doesnt_vary_on_other_kwargs(self):
        policy = Inputs()
        key = policy.compute_key(task_ctx=None, inputs={"x": 42}, flow_parameters=None)

        other_keys = []
        for kwarg_vals in itertools.permutations([None, 1, "foo", {}]):
            kwargs = dict(zip(["task_ctx", "flow_parameters", "other"], kwarg_vals))

            other_keys.append(policy.compute_key(inputs={"x": 42}, **kwargs))

        assert all([key == okey for okey in other_keys])

    def test_key_excludes_excluded_inputs(self):
        policy = Inputs(exclude=["y"])

        key = policy.compute_key(task_ctx=None, inputs={"x": 42}, flow_parameters=None)

        for val in [42, "foo", None]:
            new_key = policy.compute_key(
                task_ctx=None, inputs={"x": 42, "y": val}, flow_parameters=None
            )
            assert new_key == key

    def test_subtraction_results_in_new_policy(self):
        policy = Inputs()
        new_policy = policy - "foo"
        assert policy != new_policy
        assert policy.exclude != new_policy.exclude

    def test_excluded_can_be_manipulated_via_subtraction(self):
        policy = Inputs() - "y"
        assert policy.exclude == ["y"]

        key = policy.compute_key(task_ctx=None, inputs={"x": 42}, flow_parameters=None)

        for val in [42, "foo", None]:
            new_key = policy.compute_key(
                task_ctx=None, inputs={"x": 42, "y": val}, flow_parameters=None
            )
            assert new_key == key


class TestCompoundPolicy:
    def test_initializes(self):
        policy = CompoundCachePolicy()
        assert isinstance(policy, CachePolicy)

    def test_creation_via_addition(self):
        one, two = Inputs(), TaskSource()
        policy = one + two
        assert isinstance(policy, CompoundCachePolicy)

    def test_addition_creates_new_policies(self):
        one, two = Inputs(), CompoundCachePolicy()
        policy = one + two
        assert isinstance(policy, CompoundCachePolicy)
        assert policy != two
        assert policy.policies != two.policies

    def test_subtraction_creates_new_policies(self):
        policy = CompoundCachePolicy(policies=[])
        new_policy = policy - "foo"
        assert isinstance(new_policy, CompoundCachePolicy)
        assert policy != new_policy
        assert policy.policies != new_policy.policies

    def test_creation_via_subtraction(self):
        one = RunId()
        policy = one - "y"
        assert isinstance(policy, CompoundCachePolicy)

        assert policy.compute_key(
            task_ctx=None, inputs={"x": 42, "y": "foo"}, flow_parameters=None
        ) == (RunId() + Inputs(exclude=["y"])).compute_key(
            task_ctx=None, inputs={"x": 42, "y": "foo"}, flow_parameters=None
        )

    def test_nones_are_ignored(self):
        one, two = _None(), _None()
        policy = CompoundCachePolicy(policies=[one, two])
        assert isinstance(policy, CompoundCachePolicy)

        fparams = dict(x=42, y="foo")
        compound_key = policy.compute_key(
            task_ctx=None, inputs=dict(z=[1, 2]), flow_parameters=fparams
        )
        assert compound_key is None


class TestTaskSourcePolicy:
    def test_initializes(self):
        policy = TaskSource()
        assert isinstance(policy, CachePolicy)

    def test_changes_in_def_change_key(self):
        policy = TaskSource()

        class TaskCtx:
            pass

        task_ctx = TaskCtx()

        def my_func():
            pass

        task_ctx.task = my_func

        key = policy.compute_key(task_ctx=task_ctx, inputs=None, flow_parameters=None)

        task_ctx = TaskCtx()

        def my_func(x):
            pass

        task_ctx.task = my_func

        new_key = policy.compute_key(
            task_ctx=task_ctx, inputs=None, flow_parameters=None
        )

        assert key != new_key

    def test_source_fallback_behavior(self):
        policy = TaskSource()

        def task_a_fn():
            pass

        def task_b_fn():
            return 1

        mock_task_a = MagicMock()
        mock_task_b = MagicMock()

        mock_task_a.fn = task_a_fn
        mock_task_b.fn = task_b_fn

        task_ctx_a = TaskRunContext.model_construct(task=mock_task_a)
        task_ctx_b = TaskRunContext.model_construct(task=mock_task_b)

        for os_error_msg in {"could not get source code", "source code not available"}:
            with patch("inspect.getsource", side_effect=OSError(os_error_msg)):
                fallback_key_a = policy.compute_key(
                    task_ctx=task_ctx_a, inputs=None, flow_parameters=None
                )
                fallback_key_b = policy.compute_key(
                    task_ctx=task_ctx_b, inputs=None, flow_parameters=None
                )

            assert fallback_key_a and fallback_key_b
            assert fallback_key_a != fallback_key_b


class TestDefaultPolicy:
    def test_changing_the_inputs_busts_the_cache(self):
        inputs = dict(x=42)
        key = DEFAULT.compute_key(task_ctx=None, inputs=inputs, flow_parameters=None)

        inputs = dict(x=43)
        new_key = DEFAULT.compute_key(
            task_ctx=None, inputs=inputs, flow_parameters=None
        )

        assert key != new_key

    def test_changing_the_run_id_busts_the_cache(self):
        @dataclass
        class Run:
            id: str
            flow_run_id: str = None

        def my_task():
            pass

        @dataclass
        class TaskCtx:
            task_run: Run
            task = my_task

        task_run_a = Run(id="a", flow_run_id="a")
        task_run_b = Run(id="b", flow_run_id="b")
        task_run_c = Run(id="c", flow_run_id=None)
        task_run_d = Run(id="d", flow_run_id=None)

        key_a = DEFAULT.compute_key(
            task_ctx=TaskCtx(task_run=task_run_a), inputs=None, flow_parameters=None
        )
        key_b = DEFAULT.compute_key(
            task_ctx=TaskCtx(task_run=task_run_b), inputs=None, flow_parameters=None
        )
        key_c = DEFAULT.compute_key(
            task_ctx=TaskCtx(task_run=task_run_c), inputs=None, flow_parameters=None
        )
        key_d = DEFAULT.compute_key(
            task_ctx=TaskCtx(task_run=task_run_d), inputs=None, flow_parameters=None
        )

        assert key_a not in [key_b, key_c, key_d]
        assert key_b not in [key_a, key_c, key_d]
        assert key_c not in [key_a, key_b, key_d]
        assert key_d not in [key_a, key_b, key_c]

    def test_changing_the_source_busts_the_cache(self):
        @dataclass
        class Run:
            id: str
            flow_run_id: str = None

        @dataclass
        class TaskCtx:
            task_run: Run
            task: Callable = None

        task_run = Run(id="a", flow_run_id="b")
        ctx_one = TaskCtx(task_run=task_run, task=lambda: "foo")
        ctx_two = TaskCtx(task_run=task_run, task=lambda: "bar")

        key_one = DEFAULT.compute_key(
            task_ctx=ctx_one, inputs=None, flow_parameters=None
        )
        key_two = DEFAULT.compute_key(
            task_ctx=ctx_two, inputs=None, flow_parameters=None
        )

        assert key_one != key_two


class TestPolicyConfiguration:
    def test_configure_changes_storage(self):
        policy = Inputs().configure(key_storage="/path/to/storage")
        assert policy.key_storage == "/path/to/storage"

    def test_configure_changes_locks(self):
        policy = Inputs().configure(lock_manager="/path/to/locks")
        assert policy.lock_manager == "/path/to/locks"

    def test_configure_changes_isolation_level(self):
        policy = Inputs().configure(isolation_level="SERIALIZABLE")
        assert policy.isolation_level == "SERIALIZABLE"

    def test_configure_changes_all_attributes(self):
        policy = Inputs().configure(
            key_storage="/path/to/storage",
            lock_manager="/path/to/locks",
            isolation_level="SERIALIZABLE",
        )
        assert policy.key_storage == "/path/to/storage"
        assert policy.lock_manager == "/path/to/locks"
        assert policy.isolation_level == "SERIALIZABLE"

    def test_configure_with_none_is_noop(self):
        policy = Inputs().configure(
            key_storage=None, lock_manager=None, isolation_level=None
        )
        assert policy == Inputs()

    def test_add_policy_with_configuration(self):
        policy = Inputs() + TaskSource().configure(
            lock_manager="/path/to/locks",
            isolation_level="SERIALIZABLE",
            key_storage="/path/to/storage",
        )
        assert policy.lock_manager == "/path/to/locks"
        assert policy.isolation_level == "SERIALIZABLE"
        assert policy.key_storage == "/path/to/storage"

    def test_add_policy_with_conflict_raises(self):
        policy = Inputs() + TaskSource().configure(
            lock_manager="original_locks",
            key_storage="original_storage",
            isolation_level="SERIALIZABLE",
        )
        with pytest.raises(
            ValueError,
            match="Cannot add CachePolicies with different lock implementations.",
        ):
            _policy = policy + TaskSource().configure(lock_manager="other_locks")

        with pytest.raises(
            ValueError,
            match="Cannot add CachePolicies with different storage locations.",
        ):
            _policy = policy + TaskSource().configure(key_storage="other_storage")

        with pytest.raises(
            ValueError,
            match="Cannot add CachePolicies with different isolation levels.",
        ):
            _policy = policy + TaskSource().configure(isolation_level="READ_COMMITTED")

    def test_configure_returns_new_policy(self):
        policy = Inputs()
        new_policy = policy.configure(key_storage="new_storage")
        assert policy is not new_policy
