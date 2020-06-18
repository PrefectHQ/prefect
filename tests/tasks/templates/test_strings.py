import pytest

from prefect import Flow, context
from prefect.tasks.templates import StringFormatter


def test_string_formatter_simply_formats():
    task = StringFormatter(template="{name} is from {place}")
    with Flow(name="test") as f:
        ans = task(name="Ford", place="Betelgeuse")
    res = f.run()
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from Betelgeuse"


def test_string_formatter_can_be_provided_template_at_runtime():
    task = StringFormatter()
    with Flow(name="test") as f:
        ans = task(template="{name} is from {place}", name="Ford", place="Betelgeuse")
    res = f.run()
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from Betelgeuse"


def test_string_formatter_formats_from_context():
    task = StringFormatter(template="I am {task_name}", name="foo")
    f = Flow(name="test", tasks=[task])
    res = f.run()
    assert res.is_successful()
    assert res.result[task].result == "I am foo"


def test_string_formatter_fails_in_expected_ways():
    t1 = StringFormatter(template="{name} is from {place}")
    t2 = StringFormatter(template="{0} is from {1}")
    f = Flow(name="test", tasks=[t1, t2])
    res = f.run()

    assert res.is_failed()
    assert isinstance(res.result[t1].result, KeyError)
    assert isinstance(res.result[t2].result, IndexError)
