import json
import logging

from prefect import Flow
from prefect.tasks.jupyter import ExecuteNotebook


def test_jupyter_html_output():
    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        output_format="html",
    )
    output = task.run()
    assert "a*b=10" in output
    assert "# This cell contains commented Python code" in output


def test_jupyter_html_output_with_exporter_kwargs():
    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        output_format="html",
        exporter_kwargs={"exclude_input": True},
    )
    output = task.run()
    assert "a*b=10" in output
    assert "# This cell contains commented Python code" not in output


def test_jupyter_json_output():
    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        output_format="json",
    )
    output = task.run()
    _ = json.loads(output)  # try loading the JSON string
    assert "a*b=10" in output


def test_jupyter_notebook_output():
    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        output_format="notebook",
    )
    output = task.run()
    _ = json.loads(output)  # try loading the JSON string
    assert "a*b=10" in output


def test_jupyter_cell_logging(caplog):
    caplog.set_level(level=logging.INFO, logger="papermill")

    with Flow("Jupyter test") as flow:
        ExecuteNotebook(
            "tests/tasks/jupyter/sample_notebook.ipynb",
            parameters=dict(a=5),
            output_format="notebook",
        )()

    flow.run()
    assert "papermill:execute.py" in caplog.text
