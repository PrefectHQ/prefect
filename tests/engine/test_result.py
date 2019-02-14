import cloudpickle
import pytest

from prefect.engine.result import Result, NoResult, NoResultType, SafeResult
from prefect.engine.result_handlers import ResultHandler, JSONResultHandler


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


def test_basic_noresult_repr():
    assert repr(NoResult) == "<No result>"


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


class Test:
    def test_write_writes(self):
        r = Result(value=4, result_handler=JSONResultHandler())
        assert r.handled is False
        s = r.write()
        assert s.handled is True
        assert s.value == "4"
        assert s.result_handler is r.result_handler

    def test_write_doesnt_write(self):
        r = Result(value=4, handled=True, result_handler=JSONResultHandler())
        assert r.handled is True
        s = r.write()
        assert s is r

    def test_write_reads(self):
        r = Result(value="4", handled=True, result_handler=JSONResultHandler())
        assert r.handled is True
        s = r.read()
        assert s.handled is False
        assert s.value == 4
        assert s.result_handler is r.result_handler

    def test_write_doesnt_read(self):
        r = Result(value="4", handled=False, result_handler=JSONResultHandler())
        assert r.handled is False
        s = r.read()
        assert s is r
