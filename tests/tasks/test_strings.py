import os
import pytest
import subprocess
import tempfile

from prefect import Flow
from prefect.engine import signals
from prefect.tasks.templates import StringFormatterTask, JinjaTemplateTask
from prefect.utilities.tests import raise_on_exception


def test_string_formatter_simply_formats():
    task = StringFormatterTask(template="{name} is from {place}")
    with Flow() as f:
        ans = task(name="Ford", place="Betelgeuse")
    res = f.run(return_tasks=[ans])
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from Betelgeuse"


def test_string_formatter_can_be_provided_template_at_runtime():
    task = StringFormatterTask()
    with Flow() as f:
        ans = task(template="{name} is from {place}", name="Ford", place="Betelgeuse")
    res = f.run(return_tasks=[ans])
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from Betelgeuse"


def test_string_formatter_formats_from_context():
    task = StringFormatterTask(template="I am {_task_name}", name="foo")
    f = Flow(tasks=[task])
    res = f.run(return_tasks=[task])
    assert res.is_successful()
    assert res.result[task].result == "I am foo"


def test_string_formatter_fails_in_expected_ways():
    t1 = StringFormatterTask(template="{name} is from {place}")
    t2 = StringFormatterTask(template="{0} is from {1}")
    f = Flow(tasks=[t1, t2])
    res = f.run(return_tasks=[t1, t2])

    assert res.is_failed()
    assert isinstance(res.result[t1].message, KeyError)
    assert isinstance(res.result[t2].message, IndexError)


def test_jinja_template_simply_formats():
    task = JinjaTemplateTask(template="{{ name }} is from {{ place }}")
    with Flow() as f:
        ans = task(name="Ford", place="Betelgeuse")
    res = f.run(return_tasks=[ans])
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from Betelgeuse"


def test_jinja_template_can_be_provided_template_at_runtime():
    task = JinjaTemplateTask()
    with Flow() as f:
        ans = task(
            template="{{ name }} is from {{ place }}", name="Ford", place="Betelgeuse"
        )
    res = f.run(return_tasks=[ans])
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from Betelgeuse"


def test_jinja_template_formats_from_context():
    task = JinjaTemplateTask(template="I am {{ _task_name }}", name="foo")
    f = Flow(tasks=[task])
    res = f.run(return_tasks=[task])
    assert res.is_successful()
    assert res.result[task].result == "I am foo"


def test_jinja_template_partially_formats():
    task = JinjaTemplateTask(template="{{ name }} is from {{ place }}")
    with Flow() as f:
        ans = task(name="Ford")
    res = f.run(return_tasks=[ans])
    assert res.is_successful()
    assert res.result[ans].result == "Ford is from "
