import pytest

from prefect.engine.result import Result, NoResult
from prefect.engine.result_handlers import ResultHandler, JSONResultHandler


class TestInitialization:
    def test_noresult_inits_with_no_args(self):
        n = NoResult()

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


@pytest.mark.parametrize("attr", ["value", "handled", "result_handler"])
def test_noresult_has_no_result_attrs(attr):
    n = NoResult()
    with pytest.raises(AttributeError):
        getattr(n, attr)


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
