import datetime
import logging

import cloudpickle
import pytest

from unittest.mock import MagicMock

import prefect
from prefect.engine.result import NoResult, NoResultType, Result, SafeResult
from prefect.engine.result_handlers import (
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
)


class TestInitialization:
    def test_noresult_is_already_init(self):
        n = NoResult
        assert isinstance(n, NoResultType)
        with pytest.raises(TypeError):
            n()

    def test_result_does_not_require_a_value(self):
        assert Result().value is None

    def test_result_inits_with_value(self):
        r = Result(3)
        assert r.value == 3
        assert r.safe_value is NoResult
        assert r.result_handler is None
        assert r.validators is None
        assert r.location is None
        assert r.run_validators is True

        s = Result(value=5)
        assert s.value == 5
        assert s.safe_value is NoResult
        assert s.result_handler is None
        assert s.validators is None
        assert s.location is None
        assert r.run_validators is True

    def test_result_inits_with_handled_and_result_handler(self):
        handler = JSONResultHandler()
        r = Result(value=3, result_handler=handler)
        assert r.value == 3
        assert r.safe_value is NoResult
        assert r.result_handler == handler

    def test_result_ignores_none_values(self):
        handler = JSONResultHandler()
        r = Result(value=None, result_handler=handler)
        assert r.value is None
        assert r.safe_value is NoResult
        r.store_safe_value()
        assert r.safe_value is NoResult
        assert r.value is None

    def test_safe_result_requires_both_init_args(self):
        with pytest.raises(TypeError, match="2 required positional arguments"):
            SafeResult()

        with pytest.raises(TypeError, match="1 required positional argument"):
            SafeResult(value="3")

        with pytest.raises(TypeError, match="1 required positional argument"):
            SafeResult(result_handler=JSONResultHandler())

    def test_safe_result_inits_with_both_args(self):
        res = SafeResult(value="3", result_handler=JSONResultHandler())
        assert res.value == "3"
        assert res.result_handler == JSONResultHandler()
        assert res.safe_value is res


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


def test_noresult_is_safe():
    assert isinstance(NoResult, SafeResult)


def test_basic_noresult_repr():
    assert repr(NoResult) == "<No result>"


def test_basic_noresult_str():
    assert str(NoResult) == "NoResult"


def test_basic_safe_result_repr():
    r = SafeResult(2, result_handler=JSONResultHandler())
    assert repr(r) == "<SafeResult: 2>"


def test_basic_result_repr():
    r = Result(2)
    assert repr(r) == "<Result: 2>"


def test_noresult_has_base_handler():
    n = NoResult
    n.result_handler == ResultHandler()


def test_noresult_returns_itself_for_safe_value():
    n = NoResult
    assert n is n.safe_value


def test_noresult_returns_none_for_value():
    n = NoResult
    assert n.value is None


def test_no_results_are_all_the_same():
    n = NoResult
    q = NoResultType()
    assert n == q
    q.new_attr = 99
    assert n == q


def test_no_results_are_not_the_same_as_result():
    n = NoResult
    r = Result(None)
    assert n != r


class TestResultEquality:
    @pytest.mark.parametrize("val", [1, "2", object, lambda: None])
    def test_boring_results_are_the_same_if_values_are(self, val):
        r, s = Result(val), Result(val)
        assert r == s

    def test_results_are_different_if_handled(self):
        r = Result("3", result_handler=JSONResultHandler())
        s = Result("3", result_handler=JSONResultHandler())
        s.store_safe_value()
        assert s != r

    def test_results_are_same_if_handled(self):
        r = Result("3", result_handler=JSONResultHandler())
        s = Result("3", result_handler=JSONResultHandler())
        r.store_safe_value()
        s.store_safe_value()
        assert s == r

    def test_safe_results_are_same(self):
        r = SafeResult("3", result_handler=JSONResultHandler())
        s = SafeResult("3", result_handler=JSONResultHandler())
        assert r == s

    def test_safe_results_with_different_values_are_not_same(self):
        r = SafeResult("3", result_handler=JSONResultHandler())
        s = SafeResult("4", result_handler=JSONResultHandler())
        assert r != s

    def test_safe_results_with_different_handlers_are_not_same(self):
        r = SafeResult("3", result_handler=JSONResultHandler())
        s = SafeResult("3", result_handler=LocalResultHandler())
        assert r != s

    def test_safe_results_to_results_remain_the_same(self):
        r = SafeResult("3", result_handler=JSONResultHandler())
        s = SafeResult("3", result_handler=JSONResultHandler())
        assert r.to_result() == s.to_result()


class TestStoreSafeValue:
    def test_store_safe_value_for_results(self):
        r = Result(value=4, result_handler=JSONResultHandler())
        assert r.safe_value is NoResult
        output = r.store_safe_value()
        assert output is None
        assert isinstance(r.safe_value, SafeResult)
        assert r.value == 4

    def test_store_safe_value_for_safe_results(self):
        r = SafeResult(value=4, result_handler=JSONResultHandler())
        output = r.store_safe_value()
        assert output is None
        assert isinstance(r.safe_value, SafeResult)
        assert r.value == 4

    def test_store_safe_value_for_no_results(self):
        output = NoResult.store_safe_value()
        assert output is None

    def test_storing_happens_once(self):
        r = Result(value=4, result_handler=JSONResultHandler())
        safe_value = SafeResult(value="123", result_handler=JSONResultHandler())
        r.safe_value = safe_value
        r.store_safe_value()
        assert r.safe_value is safe_value

    def test_error_when_storing_with_no_handler(self):
        r = Result(value=42)
        with pytest.raises(AssertionError):
            r.store_safe_value()


class TestToResult:
    def test_to_result_returns_self_for_results(self):
        r = Result(4)
        assert r.to_result() is r

    def test_to_result_returns_self_for_no_results(self):
        assert NoResult.to_result() is NoResult

    def test_to_result_returns_hydrated_result_for_safe(self):
        s = SafeResult("3", result_handler=JSONResultHandler())
        res = s.to_result()
        assert isinstance(res, Result)
        assert res.value == 3
        assert res.safe_value is s
        assert res.result_handler is s.result_handler

    def test_to_result_resets_with_provided_result_handler(self):
        class WeirdHandler(ResultHandler):
            def read(self, loc):
                return 99

        r = Result("4", result_handler=JSONResultHandler())
        out = r.to_result(result_handler=WeirdHandler())
        assert out is r
        assert isinstance(out.result_handler, WeirdHandler)

    def test_to_result_uses_provided_result_handler(self):
        class WeirdHandler(ResultHandler):
            def read(self, loc):
                return 99

        r = SafeResult("4", result_handler=JSONResultHandler())
        out = r.to_result(result_handler=WeirdHandler())
        assert isinstance(out, Result)
        assert isinstance(out.result_handler, WeirdHandler)
        assert out.value == 99
        assert isinstance(out.safe_value.result_handler, WeirdHandler)


@pytest.mark.parametrize(
    "obj",
    [
        Result(3),
        Result(object, result_handler=LocalResultHandler()),
        NoResult,
        SafeResult("3", result_handler=JSONResultHandler()),
    ],
)
def test_everything_is_pickleable_after_init(obj):
    assert cloudpickle.loads(cloudpickle.dumps(obj)) == obj


def test_results_are_pickleable_with_their_safe_values():
    res = Result(3, result_handler=JSONResultHandler())
    res.store_safe_value()
    assert cloudpickle.loads(cloudpickle.dumps(res)) == res


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
