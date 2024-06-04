import itertools
import pytest
from prefect.records.key_policies import (
    KeyPolicy,
    Default,
    Inputs,
    CompoundKeyPolicy,
    _None,
)


class TestBaseClass:
    def test_key_policy_initializes(self):
        policy = KeyPolicy()
        assert isinstance(policy, KeyPolicy)

    def test_compute_key_not_implemented(self):
        policy = KeyPolicy()
        with pytest.raises(NotImplementedError):
            policy.compute_key(task=None, run=None, inputs=None, flow_parameters=None)


class TestNonePolicy:
    def test_initializes(self):
        policy = _None()
        assert isinstance(policy, KeyPolicy)

    def test_doesnt_compute_a_key(self):
        policy = _None()
        key = policy.compute_key(task=None, run=None, inputs=None, flow_parameters=None)
        assert key is None


class TestDefaultPolicy:
    def test_initializes(self):
        policy = Default()
        assert isinstance(policy, KeyPolicy)

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
        assert isinstance(policy, KeyPolicy)

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

    def test_excluded_can_be_manipulated_via_subtraction(self):
        policy = Inputs() - "y"

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
        policy = CompoundKeyPolicy()
        assert isinstance(policy, KeyPolicy)

    def test_creation_via_addition(self):
        one, two = Inputs(), Default()
        policy = one + two
        assert isinstance(policy, CompoundKeyPolicy)

    def test_creation_via_subtraction(self):
        one = Default()
        policy = one - "foo"
        assert isinstance(policy, CompoundKeyPolicy)
