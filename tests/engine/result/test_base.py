import cloudpickle
import pytest

import prefect
from prefect.engine.result import Result, NoResultType
from prefect.engine.result.base import ResultNotImplementedError


class TestInitialization:
    def test_result_does_not_require_a_value(self):
        assert Result().value is None

    def test_result_inits_with_value(self):
        r = Result(3)
        assert r.value == 3
        assert r.location is None

        s = Result(value=5)
        assert s.value == 5
        assert s.location is None


@pytest.mark.parametrize("abstract_interface", ["exists", "read", "write"])
def test_has_abstract_interfaces(abstract_interface: str):
    """
    Tests to make sure that calling the abstract interfaces directly
    on the base `Result` class results in `ResultNotImplementedError`s.
    """
    r = Result(value=3)

    func = getattr(r, abstract_interface)
    with pytest.raises(ResultNotImplementedError):
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

    def test_no_results_are_equal(self):
        r, s = NoResultType(), NoResultType()
        assert r == s

    def test_no_results_are_not_equal_to_results(self):
        r, s = NoResultType(), Result()
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
