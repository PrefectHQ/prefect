import cloudpickle
import pytest

from prefect.engine.result import Result, NoResult, NoResultType, SafeResult
from prefect.engine.result_handlers import (
    ResultHandler,
    JSONResultHandler,
    LocalResultHandler,
)


class TestInitialization:
    def test_noresult_is_already_init(self):
        n = NoResult
        assert isinstance(n, NoResultType)
        with pytest.raises(TypeError):
            n()

    def test_result_requires_value(self):
        with pytest.raises(TypeError) as exc:
            r = Result()
        assert "value" in str(exc.value)

    def test_result_inits_with_value(self):
        r = Result(3)
        assert r.value == 3
        assert r.safe_value is NoResult
        assert r.result_handler is None

        s = Result(value=5)
        assert s.value == 5
        assert s.safe_value is NoResult
        assert s.result_handler is None

    def test_result_inits_with_handled_and_result_handler(self):
        handler = JSONResultHandler()
        r = Result(value=3, result_handler=handler)
        assert r.value == 3
        assert r.safe_value is NoResult
        assert r.result_handler == handler

    def test_safe_result_requires_both_init_args(self):
        with pytest.raises(TypeError) as exc:
            res = SafeResult()
        assert "2 required positional arguments" in str(exc.value)

        with pytest.raises(TypeError) as exc:
            res = SafeResult(value="3")
        assert "1 required positional argument" in str(exc.value)

        with pytest.raises(TypeError) as exc:
            res = SafeResult(result_handler=JSONResultHandler())
        assert "1 required positional argument" in str(exc.value)

    def test_safe_result_inits_with_both_args(self):
        res = SafeResult(value="3", result_handler=JSONResultHandler())
        assert res.value == "3"
        assert res.result_handler == JSONResultHandler()
        assert res.safe_value is res


def test_basic_noresult_repr():
    assert repr(NoResult) == "<No result>"


def test_basic_safe_result_repr():
    r = SafeResult(2, result_handler=JSONResultHandler())
    assert repr(r) == "<SafeResult: 2>"


def test_basic_result_repr():
    r = Result(2)
    assert repr(r) == "<Result: 2>"


def test_noresult_has_no_handler_attrs():
    n = NoResult
    with pytest.raises(AttributeError):
        n.result_handler


def test_noresult_returns_itself_for_safe_value():
    n = NoResult
    assert n is n.safe_value


def test_noresult_returns_itself_for_value():
    n = NoResult
    assert n is n.value


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
