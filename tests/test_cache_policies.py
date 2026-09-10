import itertools
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Callable
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from prefect import task
from prefect.cache_policies import (
    DEFAULT,
    INPUTS,
    NO_CACHE,
    TASK_SOURCE,
    CachePolicy,
    CompoundCachePolicy,
    Inputs,
    RunId,
    TaskSource,
    _None,
    _uses_task_source,
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
        def template() -> int:
            return VALUE  # type: ignore[name-defined]  # noqa: F821

        def make_task(value: int):
            fn = FunctionType(template.__code__, {"VALUE": value}, "template")
            return task(fn)

        one, two, another_one = make_task(1), make_task(2), make_task(1)

        assert one._task_source_context_hash != two._task_source_context_hash
        assert one._task_source_context_hash == another_one._task_source_context_hash

    def test_unreferenced_globals_and_callable_helpers_are_ignored(self):
        def template() -> int:
            return helper()  # type: ignore[name-defined]  # noqa: F821

        one = task(
            FunctionType(
                template.__code__,
                {"helper": lambda: 1, "UNUSED": "one"},
                "template",
            )
        )
        two = task(
            FunctionType(
                template.__code__,
                {"helper": lambda: 2, "UNUSED": "two"},
                "template",
            )
        )

        assert one._task_source_context_hash is None
        assert two._task_source_context_hash is None

    def test_global_mutation_after_definition_does_not_change_key(self):
        def template() -> int:
            return VALUE  # type: ignore[name-defined]  # noqa: F821

        namespace = {"VALUE": 1}
        captured = task(FunctionType(template.__code__, namespace, "template"))
        before = captured._task_source_context_hash

        namespace["VALUE"] = 2

        assert captured._task_source_context_hash == before

    def test_masked_secrets_are_not_distinguishing(self):
        def make_task(value: str):
            secret = SecretStr(value)

            @task
            def read_secret() -> str:
                return secret.get_secret_value()

            return read_secret

        one = make_task("first-password")
        two = make_task("second-password")

        assert one._task_source_context_hash == two._task_source_context_hash

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

    def test_context_hash_survives_cloudpickle(self):
        import cloudpickle

        captured = "value"

        @task
        def read() -> str:
            return captured

        restored = cloudpickle.loads(cloudpickle.dumps(read))

        assert restored._task_source_context_hash == read._task_source_context_hash

    def test_effective_policy_detection(self):
        assert _uses_task_source(TASK_SOURCE)
        assert _uses_task_source(INPUTS + TASK_SOURCE)
        assert not _uses_task_source(NO_CACHE)
        assert not _uses_task_source(INPUTS)

    @pytest.mark.parametrize(
        "options",
        [
            {"cache_policy": NO_CACHE},
            {"cache_policy": INPUTS},
            {"cache_key_fn": lambda context, parameters: "key"},
            {"persist_result": False},
            {"result_storage_key": "result"},
        ],
    )
    def test_context_hash_is_gated_by_effective_policy(self, options):
        captured = "value"

        @task(**options)
        def read() -> str:
            return captured

        assert read._task_source_context_hash is None

    def test_with_options_recomputes_context_for_effective_policy(self):
        captured = "value"

        @task(cache_policy=NO_CACHE)
        def read() -> str:
            return captured

        with_source = read.with_options(cache_policy=TASK_SOURCE)
        without_source = with_source.with_options(cache_policy=NO_CACHE)

        assert read._task_source_context_hash is None
        assert with_source._task_source_context_hash is not None
        assert without_source._task_source_context_hash is None

    def test_context_hash_is_skipped_when_caching_is_disabled(self):
        captured = "value"

        with temporary_settings({PREFECT_TASKS_DISABLE_CACHING: True}):

            @task
            def read() -> str:
                return captured

        assert read._task_source_context_hash is None

    def test_failing_stable_transform_does_not_break_task_definition(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            "prefect._internal.task_source._stabilize",
            MagicMock(side_effect=ValueError),
        )
        captured = object()

        @task
        def read() -> object:
            return captured

        assert read._task_source_context_hash is not None


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
