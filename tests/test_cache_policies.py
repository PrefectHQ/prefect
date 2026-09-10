import itertools
import os
import subprocess
import sys
import threading
from collections import deque, namedtuple
from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Callable
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr

import prefect.tasks as tasks_module
from prefect import task
from prefect.cache_policies import (
    DEFAULT,
    NO_CACHE,
    CachePolicy,
    CompoundCachePolicy,
    Inputs,
    RunId,
    TaskSource,
    _None,
)
from prefect.context import TaskRunContext
from prefect.settings import PREFECT_TASKS_DISABLE_CACHING, temporary_settings
from prefect.utilities.hashing import hash_objects


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

    def test_key_applies_stabilizing_transformations(self, monkeypatch):
        patched = {dict: lambda val: "foobar"}
        monkeypatch.setattr("prefect.cache_policies.STABLE_TRANSFORMS", patched)

        policy = Inputs()

        # confirm dictionaries hash to the same because of the transform
        key = policy.compute_key(
            task_ctx=None, inputs={"y": dict(x="string")}, flow_parameters=None
        )
        other_key = policy.compute_key(
            task_ctx=None, inputs={"y": dict(z="otherstring")}, flow_parameters=None
        )

        assert key == other_key

        # confirm no changes to other types of inputs
        key = policy.compute_key(task_ctx=None, inputs={"x": 42}, flow_parameters=None)
        other_key = policy.compute_key(
            task_ctx=None, inputs={"x": 43}, flow_parameters=None
        )

        assert key != other_key

    def test_key_registers_transforms_for_already_imported_modules(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeDataFrame:
            def __init__(self, columns: dict[str, str]):
                self._columns = columns

            @property
            def columns(self) -> list[str]:
                return list(self._columns)

            def __getitem__(self, column: str) -> str:
                return self._columns[column]

        fake_pandas = ModuleType("pandas")
        fake_pandas.DataFrame = FakeDataFrame  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
        monkeypatch.setattr("prefect.cache_policies.STABLE_TRANSFORMS", {})

        policy = Inputs()

        # column ordering is stabilized by the registered transform
        key = policy.compute_key(
            task_ctx=None,
            inputs={"df": FakeDataFrame({"a": "1", "b": "2"})},
            flow_parameters=None,
        )
        other_key = policy.compute_key(
            task_ctx=None,
            inputs={"df": FakeDataFrame({"b": "2", "a": "1"})},
            flow_parameters=None,
        )

        assert key == other_key

    def test_importing_module_does_not_import_optional_dependencies(
        self, tmp_path: Path
    ):
        # a stub package that fails if imported, to detect an eager import of pandas
        (tmp_path / "pandas.py").write_text(
            "raise AssertionError('pandas was eagerly imported')"
        )

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import prefect.cache_policies;"
                " assert 'pandas' not in sys.modules",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

    def test_subtraction_results_in_new_policy_for_inputs(self):
        policy = Inputs()
        new_policy = policy - "foo"
        assert policy != new_policy
        assert policy.exclude != new_policy.exclude

    @pytest.mark.parametrize("policy", [RunId(), RunId() + TaskSource()])
    def test_subtraction_is_noop_for_non_inputs_policies(self, policy):
        new_policy = policy - "foo"
        assert policy is new_policy
        assert policy.compute_key(
            task_ctx=None,
            inputs={"foo": 42, "y": "changing-value"},
            flow_parameters=None,
        ) == policy.compute_key(
            task_ctx=None, inputs={"foo": 42, "y": "changed"}, flow_parameters=None
        )

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

    def test_subtraction_creates_new_policies_if_input_dependency(self):
        policy = CompoundCachePolicy(policies=[Inputs()])
        new_policy = policy - "foo"
        assert isinstance(new_policy, CompoundCachePolicy)
        assert policy != new_policy
        assert policy.policies != new_policy.policies

    def test_creation_via_subtraction(self):
        one = DEFAULT
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

    def test_adding_two_compound_policies_merges_policies(self):
        one = CompoundCachePolicy(policies=[Inputs(), TaskSource()])
        two = CompoundCachePolicy(policies=[RunId()])
        policy = one + two
        assert isinstance(policy, CompoundCachePolicy)
        assert len(policy.policies) == 3
        assert Inputs() in policy.policies
        assert RunId() in policy.policies
        assert TaskSource() in policy.policies

    def test_nested_compound_policies_are_flattened(self):
        policy = CompoundCachePolicy(
            policies=[
                CompoundCachePolicy(policies=[Inputs(), TaskSource()]),
                CompoundCachePolicy(policies=[RunId()]),
            ]
        )
        assert isinstance(policy, CompoundCachePolicy)
        assert len(policy.policies) == 3
        assert Inputs() in policy.policies
        assert RunId() in policy.policies
        assert TaskSource() in policy.policies

    def test_compound_policy_deduplicates_inputs_on_subtraction(self):
        """Regression test for https://github.com/PrefectHQ/prefect/issues/16773"""
        # Create a compound policy with multiple Inputs policies
        policy = CompoundCachePolicy(
            policies=[
                Inputs(),
                TaskSource(),
                Inputs(exclude=["x"]),
                Inputs(exclude=["y"]),
            ]
        )
        # Inputs get combined into a single policy
        assert len(policy.policies) == 2

        # Subtract a new key
        new_policy = policy - "z"

        # Verify that all Inputs policies were merged into one
        inputs_policies = [p for p in new_policy.policies if isinstance(p, Inputs)]
        assert len(inputs_policies) == 1

        # Verify that all excludes were preserved
        assert sorted(inputs_policies[0].exclude) == ["x", "y", "z"]

        # Each non-Inputs policy gets converted to a CompoundCachePolicy with an Inputs policy
        # So we should have one merged Inputs policy and one CompoundCachePolicy containing TaskSource
        assert len(new_policy.policies) == 2
        assert any(
            isinstance(p, CompoundCachePolicy) or isinstance(p, TaskSource)
            for p in new_policy.policies
        )


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

    def test_uses_stored_source_code(self):
        """Test that TaskSource uses stored source_code attribute when available."""
        policy = TaskSource()

        mock_task_a = MagicMock()
        mock_task_b = MagicMock()

        # Set different source code on each mock task
        mock_task_a.source_code = "def task_a():\n    return 'a'"
        mock_task_b.source_code = "def task_b():\n    return 'b'"

        task_ctx_a = TaskRunContext.model_construct(task=mock_task_a)
        task_ctx_b = TaskRunContext.model_construct(task=mock_task_b)

        key_a = policy.compute_key(
            task_ctx=task_ctx_a, inputs=None, flow_parameters=None
        )
        key_b = policy.compute_key(
            task_ctx=task_ctx_b, inputs=None, flow_parameters=None
        )

        # Keys should be generated and different for different source code
        assert key_a is not None
        assert key_b is not None
        assert key_a != key_b

    def test_closure_values_change_key(self):
        """Tasks with identical source but different captured values get different keys."""
        policy = TaskSource()

        def make_scaler(factor: int):
            @task
            def scale(x: int) -> int:
                return x * factor

            return scale

        double, triple, another_double = (
            make_scaler(2),
            make_scaler(3),
            make_scaler(2),
        )
        assert double.source_code == triple.source_code

        keys = [
            policy.compute_key(
                task_ctx=TaskRunContext.model_construct(task=t),
                inputs=None,
                flow_parameters=None,
            )
            for t in (double, triple, another_double)
        ]

        assert keys[0] != keys[1]
        assert keys[0] == keys[2]

    def test_referenced_global_values_change_key(self):
        policy = TaskSource()

        def scale(x: int) -> int:
            return x * FACTOR  # type: ignore[name-defined]  # noqa: F821

        def make_task(factor: int):
            fn = FunctionType(
                scale.__code__,
                {"__builtins__": __builtins__, "FACTOR": factor},
                scale.__name__,
            )
            return task(fn)

        double, triple, another_double = make_task(2), make_task(3), make_task(2)
        assert double.source_code == triple.source_code

        keys = [
            policy.compute_key(
                task_ctx=TaskRunContext.model_construct(task=t),
                inputs=None,
                flow_parameters=None,
            )
            for t in (double, triple, another_double)
        ]

        assert keys[0] != keys[1]
        assert keys[0] == keys[2]

    def test_unreferenced_globals_do_not_change_key(self):
        def constant() -> int:
            return 1

        one = task(
            FunctionType(
                constant.__code__,
                {"__builtins__": __builtins__, "UNUSED": 1},
                constant.__name__,
            )
        )
        two = task(
            FunctionType(
                constant.__code__,
                {"__builtins__": __builtins__, "UNUSED": 2},
                constant.__name__,
            )
        )

        assert one._task_source_context_hash is None
        assert TaskSource().compute_key(
            task_ctx=TaskRunContext.model_construct(task=one),
            inputs=None,
            flow_parameters=None,
        ) == TaskSource().compute_key(
            task_ctx=TaskRunContext.model_construct(task=two),
            inputs=None,
            flow_parameters=None,
        )

    @pytest.mark.parametrize(
        "first,second",
        [
            (lambda x: x + 1, lambda x: x + 2),
            (ModuleType("first"), ModuleType("second")),
        ],
    )
    def test_callable_and_module_globals_are_excluded(
        self, first: object, second: object
    ):
        def uses_helper(x: int) -> object:
            return HELPER(x)  # type: ignore[name-defined]  # noqa: F821

        one = task(
            FunctionType(
                uses_helper.__code__,
                {"__builtins__": __builtins__, "HELPER": first},
                uses_helper.__name__,
            )
        )
        two = task(
            FunctionType(
                uses_helper.__code__,
                {"__builtins__": __builtins__, "HELPER": second},
                uses_helper.__name__,
            )
        )

        assert one._task_source_context_hash is None
        assert two._task_source_context_hash is None

    def test_unhashable_closure_values_are_ignored(self):
        policy = TaskSource()

        def make_task(resource: threading.Lock):
            @task
            def locked() -> None:
                with resource:
                    pass

            return locked

        one, two = make_task(threading.Lock()), make_task(threading.Lock())

        key_one = policy.compute_key(
            task_ctx=TaskRunContext.model_construct(task=one),
            inputs=None,
            flow_parameters=None,
        )
        key_two = policy.compute_key(
            task_ctx=TaskRunContext.model_construct(task=two),
            inputs=None,
            flow_parameters=None,
        )

        assert key_one is not None
        assert key_one == key_two

    def test_empty_closure_cell_does_not_break_task_definition(self):
        def make_task():
            captured = "value"

            def uses_capture() -> str:
                return captured  # noqa: F821

            del captured
            return task(uses_capture)

        captured_task = make_task()

        assert captured_task._task_source_context_hash is not None

    def test_empty_closure_cell_does_not_hide_referenced_globals(self):
        def make_task(value: int):
            captured = "unused"

            def template(use_capture: bool = False) -> int:
                if use_capture:
                    return captured  # noqa: F821
                return VALUE  # type: ignore[name-defined]  # noqa: F821

            fn = FunctionType(
                template.__code__,
                {"__builtins__": __builtins__, "VALUE": value},
                template.__name__,
                closure=template.__closure__,
            )
            del captured
            return task(fn)

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_empty_closure_cell_differs_from_captured_none(self):
        def make_task(empty: bool):
            captured = None

            def read() -> None:
                return captured  # noqa: F821

            if empty:
                del captured
            return task(read)

        empty, populated = make_task(True), make_task(False)

        assert empty._task_source_context_hash != populated._task_source_context_hash

    def test_empty_closure_cell_marker_cannot_collide_with_user_value(self):
        def make_task(empty: bool):
            captured: object = ("empty",)

            def read() -> object:
                return captured  # noqa: F821

            if empty:
                del captured
            return task(read)

        empty, populated = make_task(True), make_task(False)

        assert empty._task_source_context_hash != populated._task_source_context_hash

    def test_globals_referenced_by_nested_code_change_key(self):
        def outer() -> int:
            def inner() -> int:
                return VALUE  # type: ignore[name-defined]  # noqa: F821

            return inner()

        def make_task(value: int):
            return task(
                FunctionType(
                    outer.__code__,
                    {"__builtins__": __builtins__, "VALUE": value},
                    outer.__name__,
                )
            )

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    @pytest.mark.parametrize(
        "first,second",
        [
            (lambda value: value + 1, lambda value: value + 2),
            (ModuleType("first"), ModuleType("second")),
        ],
    )
    def test_callable_and_module_closure_values_are_excluded(
        self, first: object, second: object
    ):
        def make_task(helper: object):
            @task
            def uses_helper(value: int) -> object:
                return helper(value)  # type: ignore[operator]

            return uses_helper

        one, two = make_task(first), make_task(second)

        assert one._task_source_context_hash is None
        assert two._task_source_context_hash is None

    @pytest.mark.parametrize(
        "first,second",
        [
            ({"alpha", "beta"}, {"beta", "alpha"}),
            (frozenset({1, 2}), frozenset({2, 1})),
        ],
    )
    def test_unordered_closure_values_have_stable_keys(
        self, first: object, second: object
    ):
        def make_task(value: object):
            @task
            def captured() -> object:
                return value

            return captured

        one, two = make_task(first), make_task(second)

        assert one._task_source_context_hash == two._task_source_context_hash

    def test_unordered_closure_values_are_stable_across_hash_seeds(self):
        script = """
from prefect.tasks import _hash_task_source_context

def make_task():
    value = {"alpha", "beta", "gamma"}
    def captured():
        return value
    return captured

print(_hash_task_source_context(make_task()))
"""
        hashes = [
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            ).stdout
            for seed in ("1", "2")
        ]

        assert hashes[0] == hashes[1]

    def test_hashable_mapping_siblings_survive_unhashable_values(self):
        def make_task(factor: int):
            captured = {"factor": factor, "lock": threading.Lock()}

            @task
            def scale(value: int) -> int:
                return value * captured["factor"]  # type: ignore[operator]

            return scale

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_recursive_closure_values_retain_distinguishing_context(self):
        def make_task(prefix: list[object]):
            prefix.append(prefix)

            @task
            def captured() -> int:
                return len(prefix)

            return captured

        one, two = make_task([]), make_task([1])

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_recursive_mappings_are_independent_of_insertion_order(self):
        def make_task(reverse: bool):
            captured: dict[str, object] = {}
            pairs = [("factor", 2), ("self", captured)]
            captured.update(reversed(pairs) if reverse else pairs)

            @task
            def read() -> int:
                return captured["factor"]  # type: ignore[return-value]

            return read

        one, two = make_task(False), make_task(True)

        assert one._task_source_context_hash == two._task_source_context_hash

    def test_alias_relationships_change_context_identity(self):
        def make_task(shared: bool):
            first: list[object] = []
            second = first if shared else []
            captured = [first, second]

            @task
            def values_are_shared() -> bool:
                return captured[0] is captured[1]

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_alias_relationships_across_closure_cells_change_identity(self):
        def make_task(shared: bool):
            first: list[object] = []
            second = first if shared else []

            @task
            def values_are_shared() -> bool:
                return first is second

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_mutable_leaf_aliases_change_context_identity(self):
        def make_task(shared: bool):
            first = bytearray(b"value")
            second = first if shared else bytearray(b"value")

            @task
            def values_are_shared() -> bool:
                return first is second

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_alias_relationships_cross_unordered_containers(self):
        @dataclass(frozen=True)
        class Value:
            number: int

        def make_task(shared: bool):
            first = Value(1)
            member = first if shared else Value(1)
            items = frozenset({member})

            @task
            def value_is_shared() -> bool:
                return next(iter(items)) is first

            return value_is_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_model_fields_with_sets_are_stable_across_hash_seeds(self):
        script = """
from pydantic import BaseModel
from prefect.tasks import _hash_task_source_context

class Model(BaseModel):
    values: set[str]

def make_task():
    value = Model(values={"alpha", "beta", "gamma"})
    def captured():
        return value
    return captured

print(_hash_task_source_context(make_task()))
"""
        hashes = [
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            ).stdout
            for seed in ("1", "2")
        ]

        assert hashes[0] == hashes[1]

    def test_container_subclasses_retain_state(self):
        class TaggedList(list[object]):
            def __init__(self, tag: str):
                super().__init__([1])
                self.tag = tag

        def make_task(tag: str):
            captured = TaggedList(tag)

            @task
            def read_tag() -> str:
                return captured.tag

            return read_tag

        one, two = make_task("one"), make_task("two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_dict_subclasses_use_base_storage(self):
        class OverriddenMapping(dict[str, int]):
            def __iter__(self):
                return iter(("synthetic",))

            def keys(self):
                return {"synthetic": 0}.keys()

            def __getitem__(self, key: str) -> int:
                return 0

        def make_task(value: int):
            captured = OverriddenMapping(actual=value)

            @task
            def read_value() -> int:
                return dict.__getitem__(captured, "actual")

            return read_value

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_bytearray_contents_change_context_identity(self):
        def make_task(value: bytes):
            captured = bytearray(value)

            @task
            def read_value() -> bytes:
                return bytes(captured)

            return read_value

        one, two = make_task(b"one"), make_task(b"two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_bytearray_subclasses_retain_base_storage(self):
        class TaggedBytearray(bytearray):
            pass

        def make_task(value: bytes):
            captured = TaggedBytearray(value)

            @task
            def read_value() -> bytes:
                return bytes(bytearray.__iter__(captured))

            return read_value

        one, two = make_task(b"one"), make_task(b"two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_datetime_time_fold_changes_context_identity(self):
        def make_task(fold: int):
            captured = time(1, 2, fold=fold)

            @task
            def read_fold() -> int:
                return captured.fold

            return read_fold

        earlier, later = make_task(0), make_task(1)

        assert earlier._task_source_context_hash != later._task_source_context_hash

    def test_standard_value_subclasses_retain_state(self):
        class TaggedDate(date):
            pass

        def make_task(tag: str):
            captured = TaggedDate(2026, 9, 10)
            captured.tag = tag

            @task
            def read_tag() -> str:
                return captured.tag

            return read_tag

        one, two = make_task("one"), make_task("two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_standard_value_subclasses_retain_aliases(self):
        class TaggedDate(date):
            pass

        def make_task(shared: bool):
            first = TaggedDate(2026, 9, 10)
            first.tag = "value"
            second = first if shared else TaggedDate(2026, 9, 10)
            second.tag = "value"

            @task
            def values_are_shared() -> bool:
                return first is second

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_nested_unordered_values_are_prepared_linearly(self, monkeypatch):
        original_stabilize = tasks_module._stabilize
        calls = 0

        def counted_stabilize(value):
            nonlocal calls
            calls += 1
            return original_stabilize(value)

        monkeypatch.setattr(tasks_module, "_stabilize", counted_stabilize)
        captured: object = "leaf"
        depth = 12
        for _ in range(depth):
            captured = frozenset({captured})

        @task
        def read_value() -> object:
            return captured

        assert read_value._task_source_context_hash is not None
        assert calls < depth * 4

    def test_container_subclasses_retain_slotted_state(self):
        class TaggedList(list[object]):
            __slots__ = ("tag",)

            def __init__(self, tag: str):
                super().__init__([1])
                self.tag = tag

        def make_task(tag: str):
            captured = TaggedList(tag)

            @task
            def read_tag() -> str:
                return captured.tag

            return read_tag

        one, two = make_task("one"), make_task("two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_container_subclasses_retain_private_slotted_state(self):
        class TaggedList(list[object]):
            __slots__ = ("__tag",)

            def __init__(self, tag: str):
                super().__init__([1])
                self.__tag = tag

            def tag(self) -> str:
                return self.__tag

        def make_task(tag: str):
            captured = TaggedList(tag)

            @task
            def read_tag() -> str:
                return captured.tag()

            return read_tag

        one, two = make_task("one"), make_task("two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_list_subclasses_use_base_storage(self):
        class OverriddenIteration(list[int]):
            def __iter__(self):
                return iter([0])

        def make_task(value: int):
            captured = OverriddenIteration([value])

            @task
            def read_value() -> int:
                return list.__getitem__(captured, 0)

            return read_value

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_set_subclasses_use_base_storage(self):
        class OverriddenIteration(set[int]):
            def __iter__(self):
                return iter([0])

        def make_task(value: int):
            captured = OverriddenIteration({value})

            @task
            def contains_one() -> bool:
                return set.__contains__(captured, 1)

            return contains_one

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_tuple_subclasses_retain_state(self):
        class TaggedTuple(tuple[object, ...]):
            def __new__(cls, tag: str):
                value = super().__new__(cls, (1,))
                value.tag = tag
                return value

        def make_task(tag: str):
            captured = TaggedTuple(tag)

            @task
            def read_tag() -> str:
                return captured.tag  # type: ignore[attr-defined]

            return read_tag

        one, two = make_task("one"), make_task("two")

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_namedtuple_values_retain_elements_without_instance_state(self):
        Point = namedtuple("Point", "value")

        def make_task(value: int):
            captured = Point(value)

            @task
            def read_value() -> int:
                return captured.value

            return read_value

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_pydantic_private_attributes_change_context_identity(self):
        class Model(BaseModel):
            _factor: int = PrivateAttr()

        def make_task(factor: int):
            captured = Model()
            captured._factor = factor

            @task
            def read_factor() -> int:
                return captured._factor

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_pydantic_excluded_fields_change_context_identity(self):
        class Model(BaseModel):
            factor: int = Field(exclude=True)

        def make_task(factor: int):
            captured = Model(factor=factor)

            @task
            def read_factor() -> int:
                return captured.factor

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_pydantic_extra_fields_change_context_identity(self):
        class Model(BaseModel):
            model_config = ConfigDict(extra="allow")

        def make_task(factor: int):
            captured = Model(factor=factor)

            @task
            def read_factor() -> int:
                return captured.factor  # type: ignore[attr-defined, no-any-return]

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_pydantic_fields_set_changes_context_identity(self):
        class Model(BaseModel):
            value: int = 1

        def make_task(explicit: bool):
            captured = Model(value=1) if explicit else Model()

            @task
            def fields_set() -> set[str]:
                return captured.model_fields_set

            return fields_set

        implicit, explicit = make_task(False), make_task(True)

        assert implicit._task_source_context_hash != explicit._task_source_context_hash

    def test_additional_dataclass_state_changes_context_identity(self):
        @dataclass
        class Config:
            value: int

        def make_task(factor: int):
            captured = Config(1)
            captured.factor = factor  # type: ignore[attr-defined]

            @task
            def read_factor() -> int:
                return captured.factor  # type: ignore[attr-defined, no-any-return]

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_missing_dataclass_field_does_not_hide_readable_fields(self):
        @dataclass
        class Config:
            factor: int
            missing: int = field(init=False)

        def make_task(factor: int):
            captured = Config(factor)

            @task
            def read_factor() -> int:
                return captured.factor

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_dataclass_fields_use_stored_values(self):
        @dataclass
        class Config:
            factor: int

            def __getattribute__(self, name: str):
                if name == "factor":
                    return 0
                return super().__getattribute__(name)

        def make_task(factor: int):
            captured = Config(factor)

            @task
            def read_factor() -> int:
                return vars(captured)["factor"]

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_secrets_nested_in_opaque_objects_are_not_distinguishing(self):
        class Wrapper:
            def __init__(self, value: str):
                self.secret = SecretStr(value)

        def make_task(value: str):
            captured = Wrapper(value)

            @task
            def read_secret() -> str:
                return captured.secret.get_secret_value()

            return read_secret

        one = make_task("tenant-a-password")
        two = make_task("tenant-b-password")

        assert one._task_source_context_hash == two._task_source_context_hash
        assert "tenant-a-password" not in repr(one._task_source_context_hash)
        assert "tenant-b-password" not in repr(two._task_source_context_hash)

    def test_secrets_nested_in_unhashable_leaves_are_not_distinguishing(self):
        def make_task(value: str):
            captured = deque([SecretStr(value)])

            @task
            def read_secret() -> str:
                return captured[0].get_secret_value()

            return read_secret

        one = make_task("tenant-a-password")
        two = make_task("tenant-b-password")

        assert one._task_source_context_hash == two._task_source_context_hash
        assert "tenant-a-password" not in repr(one._task_source_context_hash)
        assert "tenant-b-password" not in repr(two._task_source_context_hash)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="type statements need 3.12")
    def test_type_alias_scopes_include_referenced_globals(self):
        namespace: dict[str, object] = {}
        exec(
            "def template():\n"
            "    class Namespace:\n"
            "        type Alias = VALUE\n"
            "    return Namespace.Alias.__value__\n",
            namespace,
        )
        template = namespace["template"]
        assert isinstance(template, FunctionType)

        def make_task(value: int):
            return task(
                FunctionType(
                    template.__code__,
                    {"__builtins__": __builtins__, "VALUE": value},
                    template.__name__,
                )
            )

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_leaf_types_change_context_identity(self):
        class Value(str, Enum):
            ITEM = "value"

        def make_task(captured: object):
            @task
            def read_type() -> type[object]:
                return type(captured)

            return read_type

        enum_value, string_value = make_task(Value.ITEM), make_task("value")

        assert (
            enum_value._task_source_context_hash
            != string_value._task_source_context_hash
        )

    def test_standard_hashable_values_change_context_identity(self):
        def make_task(captured: Path):
            @task
            def read_path() -> Path:
                return captured

            return read_path

        one, two = make_task(Path("/one")), make_task(Path("/two"))

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_nested_class_module_name_does_not_change_context_identity(self):
        def template() -> int:
            class Unused:
                pass

            return 1

        one = task(
            FunctionType(
                template.__code__,
                {"__builtins__": __builtins__, "__name__": "__main__"},
                template.__name__,
            )
        )
        two = task(
            FunctionType(
                template.__code__,
                {"__builtins__": __builtins__, "__name__": "imported"},
                template.__name__,
            )
        )

        assert one._task_source_context_hash is None
        assert two._task_source_context_hash is None

    def test_nested_class_local_names_are_not_global_context(self):
        def template() -> int:
            class Namespace:
                VALUE = 1
                ALIAS = VALUE

            return Namespace.ALIAS

        def make_task(value: int):
            return task(
                FunctionType(
                    template.__code__,
                    {"__builtins__": __builtins__, "VALUE": value},
                    template.__name__,
                )
            )

        one, two = make_task(2), make_task(3)

        assert one._task_source_context_hash is None
        assert two._task_source_context_hash is None

    @pytest.mark.parametrize(
        "class_body",
        [
            "before = VALUE\n        VALUE = 100",
            "VALUE = 100\n        del VALUE\n        before = VALUE",
        ],
    )
    def test_nested_class_global_reads_follow_execution_order(self, class_body: str):
        namespace: dict[str, object] = {}
        exec(
            "def template():\n"
            "    class Namespace:\n"
            f"        {class_body}\n"
            "    return Namespace.before\n",
            namespace,
        )
        template = namespace["template"]
        assert isinstance(template, FunctionType)

        def make_task(value: int):
            return task(
                FunctionType(
                    template.__code__,
                    {"__builtins__": __builtins__, "VALUE": value},
                    template.__name__,
                )
            )

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_conditional_class_assignment_keeps_global_fallthrough(self):
        def template() -> int:
            class Namespace:
                if FLAG:  # type: ignore[name-defined]  # noqa: F821
                    VALUE = 100
                before = VALUE  # type: ignore[name-defined]  # noqa: F821

            return Namespace.before

        def make_task(value: int):
            return task(
                FunctionType(
                    template.__code__,
                    {
                        "__builtins__": __builtins__,
                        "FLAG": False,
                        "VALUE": value,
                    },
                    template.__name__,
                )
            )

        one, two = make_task(1), make_task(2)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_closure_mutation_after_definition_does_not_change_key(self):
        policy = TaskSource()
        run_count = 0

        @task
        def counted() -> None:
            nonlocal run_count
            run_count += 1

        def key() -> str | None:
            return policy.compute_key(
                task_ctx=TaskRunContext.model_construct(task=counted),
                inputs=None,
                flow_parameters=None,
            )

        before = key()
        counted.fn()
        assert run_count == 1
        assert key() == before

    def test_global_mutation_after_definition_does_not_change_key(self):
        policy = TaskSource()

        def get_value() -> int:
            return VALUE  # type: ignore[name-defined]  # noqa: F821

        namespace = {"__builtins__": __builtins__, "VALUE": 1}
        captured = task(FunctionType(get_value.__code__, namespace, get_value.__name__))
        before = policy.compute_key(
            task_ctx=TaskRunContext.model_construct(task=captured),
            inputs=None,
            flow_parameters=None,
        )

        namespace["VALUE"] = 2

        assert (
            policy.compute_key(
                task_ctx=TaskRunContext.model_construct(task=captured),
                inputs=None,
                flow_parameters=None,
            )
            == before
        )

    def test_task_without_closure_key_is_unchanged(self):
        policy = TaskSource()

        @task
        def plain() -> int:
            return 1

        key = policy.compute_key(
            task_ctx=TaskRunContext.model_construct(task=plain),
            inputs=None,
            flow_parameters=None,
        )

        assert key == hash_objects(plain.source_code, raise_on_failure=True)

    def test_masked_secrets_do_not_expose_or_distinguish_values(self):
        def make_task(secret: SecretStr):
            @task
            def uses_secret() -> str:
                return secret.get_secret_value()

            return uses_secret

        one = make_task(SecretStr("tenant-a-password"))
        two = make_task(SecretStr("tenant-b-password"))

        assert one._task_source_context_hash == two._task_source_context_hash
        assert "tenant-a-password" not in repr(one._task_source_context_hash)
        assert "tenant-b-password" not in repr(two._task_source_context_hash)

    def test_task_source_context_hash_survives_cloudpickle(self):
        import cloudpickle

        captured = "value"

        @task
        def uses_capture() -> str:
            return captured

        restored = cloudpickle.loads(cloudpickle.dumps(uses_capture))

        assert (
            restored._task_source_context_hash == uses_capture._task_source_context_hash
        )

    def test_context_hashing_only_runs_for_effective_task_source_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        context_hash = MagicMock(return_value="context-hash")
        monkeypatch.setattr("prefect.tasks._hash_task_source_context", context_hash)

        def make_fn(value: int):
            return lambda: value

        task(make_fn(1), cache_policy=NO_CACHE)
        task(make_fn(2), cache_policy=Inputs())
        task(make_fn(3), cache_key_fn=lambda *_: "custom")
        task(make_fn(4), cache_policy=TaskSource(), persist_result=False)
        task(make_fn(5), result_storage_key="custom-key")
        with temporary_settings({PREFECT_TASKS_DISABLE_CACHING: True}):
            task(make_fn(6), cache_policy=TaskSource())

        context_hash.assert_not_called()

        source_task = task(make_fn(7), cache_policy=TaskSource())
        default_task = task(make_fn(8))

        assert context_hash.call_count == 2
        assert source_task._task_source_context_hash == "context-hash"
        assert default_task._task_source_context_hash == "context-hash"

    def test_with_options_recomputes_context_for_effective_policy(self):
        captured = "value"

        @task(cache_policy=NO_CACHE)
        def no_cache() -> str:
            return captured

        with_source = no_cache.with_options(cache_policy=TaskSource())
        without_source = with_source.with_options(cache_policy=NO_CACHE)

        assert no_cache._task_source_context_hash is None
        assert with_source._task_source_context_hash is not None
        assert without_source._task_source_context_hash is None

    def test_closure_values_use_stable_transforms(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeDataFrame:
            def __init__(self, columns: dict[str, str]):
                self._columns = columns

            @property
            def columns(self) -> list[str]:
                return list(self._columns)

            def __getitem__(self, column: str) -> str:
                return self._columns[column]

        fake_pandas = ModuleType("pandas")
        fake_pandas.DataFrame = FakeDataFrame  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
        monkeypatch.setattr("prefect.cache_policies.STABLE_TRANSFORMS", {})

        def make_task(df: FakeDataFrame):
            @task
            def uses_df() -> list[str]:
                return df.columns

            return uses_df

        policy = TaskSource()
        keys = [
            policy.compute_key(
                task_ctx=TaskRunContext.model_construct(task=t),
                inputs=None,
                flow_parameters=None,
            )
            for t in (
                make_task(FakeDataFrame({"a": "1", "b": "2"})),
                make_task(FakeDataFrame({"b": "2", "a": "1"})),
            )
        ]

        assert keys[0] is not None
        assert keys[0] == keys[1]

    def test_pandas_stable_transform_preserves_distinct_contents(self):
        pd = pytest.importorskip("pandas")

        def make_task(factor: int):
            captured = pd.DataFrame({"factor": [factor]})

            @task
            def read_factor() -> int:
                return int(captured["factor"].iloc[0])

            return read_factor

        double, triple = make_task(2), make_task(3)

        assert double._task_source_context_hash != triple._task_source_context_hash

    def test_zero_column_dataframes_retain_index_context(self):
        pd = pytest.importorskip("pandas")

        def make_task(index: list[int]):
            captured = pd.DataFrame(index=index)

            @task
            def read_index() -> list[int]:
                return list(captured.index)

            return read_index

        one, two = make_task([1]), make_task([2])

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_dataframe_aliases_change_context_identity(self):
        pd = pytest.importorskip("pandas")

        def make_task(shared: bool):
            first = pd.DataFrame({"value": [1]})
            second = first if shared else pd.DataFrame({"value": [1]})

            @task
            def values_are_shared() -> bool:
                return first is second

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_series_aliases_change_context_identity(self):
        pd = pytest.importorskip("pandas")

        def make_task(shared: bool):
            first = pd.Series([1])
            second = first if shared else pd.Series([1])

            @task
            def values_are_shared() -> bool:
                return first is second

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_allocating_transforms_do_not_create_false_aliases(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class AllocatingTransform:
            def __init__(self, value: int):
                self.value = value

        monkeypatch.setattr(
            "prefect.cache_policies.STABLE_TRANSFORMS",
            {AllocatingTransform: lambda value: [value.value]},
        )

        def make_task(second_value: int):
            first = AllocatingTransform(1)
            second = AllocatingTransform(second_value)

            @task
            def values() -> tuple[int, int]:
                return first.value, second.value

            return values

        one, two = make_task(2), make_task(3)

        assert one._task_source_context_hash != two._task_source_context_hash

    def test_allocating_transforms_preserve_original_aliases(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class AllocatingTransform:
            def __init__(self, value: int):
                self.value = value

        monkeypatch.setattr(
            "prefect.cache_policies.STABLE_TRANSFORMS",
            {AllocatingTransform: lambda value: [value.value]},
        )

        def make_task(shared: bool):
            first = AllocatingTransform(1)
            second = first if shared else AllocatingTransform(1)

            @task
            def values_are_shared() -> bool:
                return first is second

            return values_are_shared

        aliased, distinct = make_task(True), make_task(False)

        assert aliased._task_source_context_hash != distinct._task_source_context_hash

    def test_failing_stable_transform_does_not_break_task_definition(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeDataFrame:
            columns: list[object] = ["a", 1]

        fake_pandas = ModuleType("pandas")
        fake_pandas.DataFrame = FakeDataFrame  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
        monkeypatch.setattr("prefect.cache_policies.STABLE_TRANSFORMS", {})

        df = FakeDataFrame()

        @task
        def uses_df() -> list[object]:
            return df.columns

        key = TaskSource().compute_key(
            task_ctx=TaskRunContext.model_construct(task=uses_df),
            inputs=None,
            flow_parameters=None,
        )
        assert key is not None


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
