import logging

import cloudpickle
import pytest

from unittest.mock import MagicMock

import prefect
from prefect.engine.result import Result


class TestInitialization:
    def test_result_does_not_require_a_value(self):
        assert Result().value is None

    def test_result_inits_with_value(self):
        r = Result(3)
        assert r.value == 3
        assert r.validators is None
        assert r.location is None
        assert r.run_validators is True

        s = Result(value=5)
        assert s.value == 5
        assert s.validators is None
        assert s.location is None
        assert r.run_validators is True


@pytest.mark.parametrize("abstract_interface", ["exists", "read", "write"])
def test_has_abstract_interfaces(abstract_interface: str):
    """
    Tests to make sure that calling the abstract interfaces directly
    on the base `Result` class results in `NotImplementedError`s.
    """
    r = Result(value=3)

    func = getattr(r, abstract_interface)
    with pytest.raises(NotImplementedError):
        func(None)


def test_basic_result_repr():
    r = Result(2)
    assert repr(r) == "<Result: 2>"


class TestResultEquality:
    @pytest.mark.parametrize("val", [1, "2", object, lambda: None])
    def test_boring_results_are_the_same_if_values_are(self, val):
        r, s = Result(val), Result(val)
        assert r == s

    def test_boring_results_are_different_if_one_has_location(self):
        r, s = Result(), Result(location="s")
        assert r != s


@pytest.mark.parametrize(
    "obj",
    [
        Result(3),
        Result(object, location=lambda: None),
    ],
)
def test_everything_is_pickleable_after_init(obj):
    assert cloudpickle.loads(cloudpickle.dumps(obj)) == obj


def test_result_format_template_from_context():
    res = Result(location="{this}/{works}/yes?")
    with prefect.context(this="indeed", works="functional"):
        new = res.format(**prefect.context)
        assert new.location == "indeed/functional/yes?"
        assert res.location == "{this}/{works}/yes?"
        assert new != res


class TestResultValidate:
    def test_result_validate_calls_validate_functions_from_attribute(self):
        _example_function = MagicMock(return_value=True)

        r = Result(value=None, validators=[_example_function])
        r.validate()

        _example_function.assert_called_once_with(r)

    def test_result_validate_returns_false_on_any_invalid(self):
        one_false_validators_fns = [lambda r: True, lambda r: False]

        r = Result(value=None, validators=one_false_validators_fns)
        is_valid = r.validate()

        assert is_valid is False

    def test_result_validate_returns_true_on_none_invalid(self):
        no_false_validators_fns = [lambda r: True, lambda r: True]

        r = Result(value=None, validators=no_false_validators_fns)
        is_valid = r.validate()

        assert is_valid is True

    @pytest.mark.parametrize(
        "r", [Result(value=None), Result(value=None, validators=[])]
    )
    def test_result_validate_ok_when_none_provided(self, r):
        is_valid = r.validate()
        assert is_valid is True

    def test_result_validate_raises_exceptions(self):
        def _example_function(result):
            raise TypeError

        r = Result(value=None, validators=[_example_function])
        with pytest.raises(TypeError):
            r.validate()

    def test_result_validate_warns_when_run_without_run_validators_flag(self, caplog):
        _example_function = MagicMock(return_value=True)

        r = Result(value=None, validators=[_example_function], run_validators=False)
        with caplog.at_level(logging.WARNING, "prefect.Result"):
            is_valid = r.validate()

        # it should have acted normal and called the validate functions
        _example_function.assert_called_once_with(r)
        assert is_valid is True

        # but ALSO it should published a warning log, going on about run_validators not being set
        assert caplog.text.find("WARNING") > -1
        assert caplog.text.find("run_validators") > -1
