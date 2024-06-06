import itertools

import pytest

from prefect.records.cache_policies import (
    CachePolicy,
    CompoundCachePolicy,
    Default,
    Inputs,
    TaskDef,
    _None,
)


class TestBaseClass:
    def test_cache_policy_initializes(self):
        policy = CachePolicy()
        assert isinstance(policy, CachePolicy)

    def test_compute_key_not_implemented(self):
        policy = CachePolicy()
        with pytest.raises(NotImplementedError):
            policy.compute_key(task=None, run=None, inputs=None, flow_parameters=None)


class TestNonePolicy:
    def test_initializes(self):
        policy = _None()
        assert isinstance(policy, CachePolicy)

    def test_doesnt_compute_a_key(self):
        policy = _None()
        key = policy.compute_key(task=None, run=None, inputs=None, flow_parameters=None)
        assert key is None

    @pytest.mark.parametrize("typ", CachePolicy.__subclasses__())
    def test_addition_of_none_is_noop(self, typ):
        policy = _None()
        other = typ()
        assert policy + other == other


class TestDefaultPolicy:
    def test_initializes(self):
        policy = Default()
        assert isinstance(policy, CachePolicy)

    def test_returns_run_id(self):
        class Run:
            id = "foo"

        policy = Default()
        key = policy.compute_key(
            task=None, run=Run(), inputs=None, flow_parameters=None
        )
        assert key == "foo"


class TestInputsPolicy:
    def test_initializes(self):
        policy = Inputs()
        assert isinstance(policy, CachePolicy)

    def test_key_varies_on_inputs(self):
        policy = Inputs()
        none_key = policy.compute_key(
            task=None, run=None, inputs=None, flow_parameters=None
        )
        x_key = policy.compute_key(
            task=None, run=None, inputs={"x": 42}, flow_parameters=None
        )
        y_key = policy.compute_key(
            task=None, run=None, inputs={"y": 42}, flow_parameters=None
        )

        assert x_key != y_key
        assert x_key != none_key
        assert y_key != none_key

        z_key = policy.compute_key(
            task=None, run=None, inputs={"z": "foo"}, flow_parameters=None
        )

        assert z_key not in [x_key, y_key]

    def test_key_doesnt_vary_on_other_kwargs(self):
        policy = Inputs()
        key = policy.compute_key(
            task=None, run=None, inputs={"x": 42}, flow_parameters=None
        )

        other_keys = []
        for kwarg_vals in itertools.permutations([None, 1, "foo", {}]):
            kwargs = dict(zip(["task", "run", "flow_parameters", "other"], kwarg_vals))

            other_keys.append(policy.compute_key(inputs={"x": 42}, **kwargs))

        assert all([key == okey for okey in other_keys])

    def test_key_excludes_excluded_inputs(self):
        policy = Inputs(exclude=["y"])

        key = policy.compute_key(
            task=None, run=None, inputs={"x": 42}, flow_parameters=None
        )

        for val in [42, "foo", None]:
            new_key = policy.compute_key(
                task=None, run=None, inputs={"x": 42, "y": val}, flow_parameters=None
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

        key = policy.compute_key(
            task=None, run=None, inputs={"x": 42}, flow_parameters=None
        )

        for val in [42, "foo", None]:
            new_key = policy.compute_key(
                task=None, run=None, inputs={"x": 42, "y": val}, flow_parameters=None
            )
            assert new_key == key


class TestCompoundPolicy:
    def test_initializes(self):
        policy = CompoundCachePolicy()
        assert isinstance(policy, CachePolicy)

    def test_creation_via_addition(self):
        one, two = Inputs(), Default()
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
        one = Default()
        policy = one - "foo"
        assert isinstance(policy, CompoundCachePolicy)


class TestTaskDefPolicy:
    def test_initializes(self):
        policy = TaskDef()
        assert isinstance(policy, CachePolicy)

    def test_changes_in_def_change_key(self):
        policy = TaskDef()

        def my_func():
            pass

        key = policy.compute_key(
            task=my_func, run=None, inputs=None, flow_parameters=None
        )

        def my_func(x):
            pass

        new_key = policy.compute_key(
            task=my_func, run=None, inputs=None, flow_parameters=None
        )

        assert key != new_key
