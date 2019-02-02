import pytest

from prefect.engine.result import Result, NoResult, NoResultType
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

        s = Result(value=5)
        assert s.value == 5

    def test_result_inits_with_handled_and_result_handler(self):
        handler = ResultHandler()
        r = Result(value=3, handled=False, result_handler=handler)
        assert r.value == 3
        assert r.handled is False
        assert r.result_handler == handler

    def test_result_does_allow_handled_false_without_result_handler(self):
        r = Result(value=2, handled=False)
        assert r.value == 2
        assert r.handled is False

    def test_result_doesnt_allow_handled_without_result_handler(self):
        with pytest.raises(ValueError):
            r = Result(value=3, handled=True)

    def test_result_assumes_nonhandled_at_init(self):
        r = Result(10)
        assert r.handled is False
        assert r.result_handler is None


@pytest.mark.parametrize("attr", ["handled", "result_handler"])
def test_noresult_has_no_handler_attrs(attr):
    n = NoResult
    with pytest.raises(AttributeError):
        getattr(n, attr)


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
        r = Result("3", handled=True, result_handler=JSONResultHandler())
        s = Result("3", handled=False, result_handler=JSONResultHandler())
        assert s != r

    def test_results_are_same_if_handled(self):
        r = Result("3", handled=True, result_handler=JSONResultHandler())
        s = Result("3", handled=True, result_handler=JSONResultHandler())
        assert s == r


class TestSerialization:
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
